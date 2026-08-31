"""Piso de publicacao: SEMPRE sai post, obrigatoriamente.

    python -m radar.reserva --seco    # mostra a decisao e a nota, nao publica
    python -m radar.reserva           # cobra o piso do dia (roda no cron)

Regra do Filipe (31/08/2026): nenhum dia — fim de semana incluso — termina
sem post no site. Este fluxo roda a cada ciclo do radar e e' quase sempre um
nao-fazer: antes da hora limite, ou com o dia ja' abastecido, ele so' conta e
sai. Quando o dia esta' zerado depois da hora limite, publica a NOTA-RESERVA:
um resumo do cambio gerado 100% da base propria (a serie PTAX sempre existe,
ate' domingo). Uma reserva por dia, no maximo — o piso garante o minimo de 1,
nao substitui o dia normal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from . import llm
from .alerta import avisa
from .banco import Banco
from .config import RAIZ, carrega_sites
from .gerador_dolar import DIAS, MESES, brl, pct

SITE = "doll"
SAIDA = RAIZ / "saida"
FUSO_SP = timezone(timedelta(hours=-3))
# Cloudflare bloqueia o urllib pelado (erro 1010); mesmo UA do Studio.
UA = "Mozilla/5.0 (compatible; TiheeRadar/1.0; +https://tihee.com.br)"


def posts_publicos_hoje(dominio: str, hoje_iso: str) -> int | None:
    """Quantos posts publicos o site soltou hoje (X-WP-Total). None = nao deu
    para contar — e ai' NAO publicamos reserva no escuro."""
    url = (f"https://{dominio}/wp-json/wp/v2/posts?per_page=1"
           f"&after={hoje_iso}T00:00:00")
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            total = resposta.headers.get("X-WP-Total")
            return int(total) if total is not None else None
    except Exception:
        return None


def _numeros(serie: list[dict]) -> dict:
    venda = serie[-1]["venda"]
    anterior = serie[-2]["venda"] if len(serie) >= 2 else None
    janela = [l["venda"] for l in serie]
    return {
        "venda": venda,
        "var_dia": ((venda / anterior - 1) * 100) if anterior else None,
        "var_janela": ((venda / janela[0] - 1) * 100) if len(janela) >= 2 else None,
        "maior": max(janela), "menor": min(janela), "n": len(janela),
        "data": serie[-1]["data"],
    }


def _extenso(d) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def monta_reserva(serie: list[dict], site: dict, url_ancora: str | None,
                  hoje) -> dict:
    """Nota-reserva do dia: so' numeros da base. Claude quando ha' chave;
    template deterministico como fallback."""
    n = _numeros(serie)
    mov = ("subiu" if (n["var_dia"] or 0) > 0.005
           else "caiu" if (n["var_dia"] or 0) < -0.005 else "ficou estavel")

    dado = (f"PTAX de venda: {brl(n['venda'], 4)} (pregao de {_extenso(n['data'])})")
    if n["var_dia"] is not None:
        dado += f"; no pregao o dolar {mov} {pct(abs(n['var_dia']))}"
    if n["var_janela"] is not None:
        rumo = "subiu" if n["var_janela"] > 0 else "caiu"
        dado += (f"; nos ultimos {n['n']} pregoes {rumo} "
                 f"{pct(abs(n['var_janela']))}, entre {brl(n['menor'], 4)} e "
                 f"{brl(n['maior'], 4)}")

    via_llm = None
    if llm.tem_chave():
        sistema = (
            "Voce e' redator de um portal brasileiro de cambio (doll.com.br). "
            "Escreve a NOTA DIARIA de servico sobre o dolar usando SOMENTE os "
            "numeros fornecidos — nada de causa, previsao ou fato externo. "
            "Se hoje e o pregao forem dias diferentes (noite, fim de semana), "
            "deixe claro que o numero e' do ultimo fechamento. Termine "
            "convidando a ler a pagina-guia com o link em markdown. Portugues "
            "do Brasil, 100-160 palavras. Responda SO um JSON: "
            "{\"titulo\": \"...\", \"corpo_md\": \"...\"} — titulo ate 90 "
            "caracteres, corpo sem repetir o titulo como H1.")
        prompt = (
            f"HOJE e': {_extenso(hoje)}.\n"
            f"Dados da base (unica fonte permitida): {dado}.\n"
            f"Pagina-guia para o fecho: "
            + (f"[quanto custa comprar dolar hoje]({url_ancora})" if url_ancora
               else "(nenhuma — feche sem link)") + "\n\nEscreva a nota.")
        saida = llm.gera(prompt, sistema=sistema, max_tokens=900)
        if saida:
            bruto = re.search(r"\{.*\}", saida, re.S)
            if bruto:
                try:
                    d = json.loads(bruto.group(0))
                    titulo = str(d.get("titulo") or "").strip()[:110]
                    corpo = str(d.get("corpo_md") or "").strip()
                    if titulo and len(corpo) >= 80:
                        via_llm = (titulo, corpo)
                except json.JSONDecodeError:
                    pass

    if via_llm:
        titulo, corpo = via_llm
    else:
        mesmo_dia = n["data"] == hoje
        quando = ("hoje" if mesmo_dia
                  else f"no fechamento de {DIAS[n['data'].weekday()]}")
        titulo = (f"Dólar {quando}: {brl(n['venda'], 4)} na PTAX — "
                  f"o essencial em números")[:110]
        corpo = (
            f"Na referência oficial do Banco Central, a PTAX de venda "
            f"{'desta ' + DIAS[hoje.weekday()] if mesmo_dia else 'do pregão de ' + _extenso(n['data'])} "
            f"ficou em **{brl(n['venda'], 4)}**"
            + (f", com o dólar em {mov} de {pct(abs(n['var_dia']))}."
               if n["var_dia"] is not None else ".")
            + (f" Nos últimos {n['n']} pregões, a moeda "
               f"{'acumula alta' if n['var_janela'] > 0 else 'acumula queda'} de "
               f"{pct(abs(n['var_janela']))}, oscilando entre {brl(n['menor'], 4)} "
               f"e {brl(n['maior'], 4)}." if n["var_janela"] is not None else "")
            + (f"\n\n👉 Antes de comprar, veja **[quanto custa comprar dólar "
               f"hoje]({url_ancora})** — com tabela de conversão e o IOF de "
               f"cada forma de levar dólar." if url_ancora else ""))

    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": titulo, "datePublished": agora, "dateModified": agora,
        "inLanguage": site.get("idioma", "pt-BR"), "isAccessibleForFree": True,
        "publisher": {"@type": "NewsMediaOrganization", "name": site["entidade"]},
        "about": {"@type": "Thing", "name": "Cotação do dólar"},
    }, ensure_ascii=False, indent=2)
    markdown = f"# {titulo}\n\n{corpo}\n"
    return {"titulo": titulo, "markdown": markdown,
            "resumo": corpo.split("\n\n")[0][:280], "jsonld": jsonld}


def main() -> int:
    p = argparse.ArgumentParser(description="Piso de publicacao do doll")
    p.add_argument("--seco", action="store_true", help="decide e mostra, nao publica")
    args = p.parse_args()

    site = carrega_sites()[SITE]
    piso = (site.get("publicacao") or {}).get("piso")
    if not piso:
        print("site sem regra de piso — nada a fazer")
        return 0
    minimo = int(piso.get("minimo", 1))
    apos_hora = int(piso.get("apos_hora", 17))

    agora = datetime.now(FUSO_SP)
    hoje = agora.date()
    if agora.hour < apos_hora:
        print(f"[ok] dia em curso ({agora:%H:%M} SP); o piso cobra apos as {apos_hora}h")
        return 0

    banco = Banco(seco=args.seco)
    leitor = banco if not args.seco else Banco(seco=False)

    ref = f"reserva-{hoje.isoformat()}"
    existente = leitor.artigo_existente(SITE, "reserva", ref)
    if existente and existente.get("status") == "publicada":
        print("[ok] a reserva de hoje ja saiu")
        return 0

    total = posts_publicos_hoje(site["dominio"], hoje.isoformat())
    if total is None:
        print("nao consegui contar os posts de hoje — nao publico reserva no escuro")
        banco.registra_execucao({"fluxo": "reserva", "site": SITE,
                                 "status": "erro_contagem",
                                 "resumo": "WP nao respondeu a contagem",
                                 "inicio": datetime.now(timezone.utc).isoformat()})
        return 1
    if total >= minimo:
        print(f"[ok] piso cumprido: {total} post(s) hoje (minimo {minimo})")
        return 0

    print(f"[piso] dia zerado apos as {apos_hora}h ({total}/{minimo}) — publicando a reserva")
    serie = leitor.serie_cotacoes(SITE, dias=30)
    if len(serie) < 2:
        print("serie insuficiente para a nota-reserva")
        return 1
    art = monta_reserva(serie, site, leitor.ancora_do_hub(SITE, "cotacao"), hoje)

    if args.seco:
        print(f"[seco] {art['titulo']}\n\n{art['markdown']}")
        return 0

    banco.grava_artigo({
        "site": SITE, "tipo": "reserva", "hub": "cotacao",
        "titulo": art["titulo"], "resumo": art["resumo"],
        "corpo_md": art["markdown"], "jsonld": art["jsonld"],
        "status": "aprovada", "motivo_portao": "piso de publicacao (dia zerado)",
        "referencia": ref,
    })
    import os
    from .publicador_wp import ErroWordPress, publica
    wp = site.get("wordpress")
    try:
        resultado = publica({
            "titulo": art["titulo"], "corpo_md": art["markdown"],
            "resumo": art["resumo"], "jsonld": art["jsonld"],
            "status": "publicada", "hub": "cotacao",
            "wp_post_id": (existente or {}).get("wp_post_id"),
        }, {**wp,
            "usuario": os.environ[wp["usuario_env"]],
            "senha_app": os.environ[wp["senha_env"]]})
        banco.marca_publicado(SITE, "reserva", ref, resultado["id"],
                              resultado.get("link"), "publicada")
        banco.registra_execucao({"fluxo": "reserva", "site": SITE, "status": "ok",
                                 "resumo": f"piso agiu: reserva no ar ({resultado.get('link')})",
                                 "inicio": datetime.now(timezone.utc).isoformat()})
        avisa(f"**doll — piso de publicacao** o dia estava zerado; "
              f"a nota-reserva saiu: {resultado.get('link')}")
        print(f"  no ar: {resultado.get('link')}")
    except (ErroWordPress, KeyError) as erro:
        print(f"  falha ao publicar a reserva: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
