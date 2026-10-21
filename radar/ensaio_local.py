"""Ensaio do modelo local: reescreve pautas JA' PUBLICADAS e poe o texto novo
ao lado do que foi ao ar (16/10/2026).

    python -m radar.ensaio_local --site doll --limite 10

So' le o banco; nao grava nada e nao publica. Para cada pauta publicada mais
recente (guia do motor Discover ou satelite), escreve com o modelo do
ambiente (no Mac, o exo) pela MESMA esteira da producao — pesquisa/checagem
no guia, serie de cotacoes no satelite — e salva em saida/ensaio/:

    <site>-<ref>-local.md      o que o modelo local escreveu (+ veredito)
    <site>-<ref>-no-ar.md      o que esta' publicado (titulo, URL, corpo)

E' a revisao dos "10 primeiros posts": mesma pauta, dois textos, sem
esperar o dia ter pauta nova e sem interferir no que o GitHub publica.
"""
from __future__ import annotations

import argparse
import sys
import time

from . import llm
from .banco import Banco
from .config import RAIZ, carrega_sites, env

PASTA = RAIZ / "saida" / "ensaio"
_TITULOS_DA_RODADA: list[str] = []


def pautas_publicadas(banco: Banco, site: str, limite: int) -> list[dict]:
    r = (banco.cliente.table("pautas")
         .select("id,item_id,angulo,hub,titulo_sug,dado_proprio,pontuacao,"
                 "horario_sugerido,tipo,topico_id,brief,evidencias,"
                 "itens(titulo,url,veiculo,publicado_em)")
         .eq("site", site).eq("status", "publicada")
         .order("selecionada_em", desc=True).limit(limite).execute())
    return list(r.data or [])


def escreve_guia(pt: dict, nome: str, site: dict, banco: Banco) -> tuple[dict | None, str]:
    from . import checagem as mod_checagem
    from .gerador_artigo import corrige, monta
    from .ideias import resolve_hub
    from .oportunidade import criterios_discover
    meta = banco.meta_do_site(nome) or {}
    pesquisa = criterios_discover(meta.get("criterios"))["pesquisa"]
    pt["_hub"] = resolve_hub(site, pt.get("hub") or "", pesquisa)
    art = monta(pt, site, banco.artigos_recentes(nome))
    if not art:
        return None, "o modelo nao escreveu (ver linhas [llm] acima)"
    ev, hub = pt.get("evidencias") or {}, pt.get("_hub") or {}
    res = mod_checagem.checa(art, pt["brief"], ev, hub, site)
    if not res["aprovado"] and res["corrigivel"]:
        corrigido = corrige(art, res["estrutural"], pt["brief"], ev, site, hub)
        if corrigido:
            art = corrigido
            res = mod_checagem.checa(art, pt["brief"], ev, hub, site)
    return art, ("APROVADO" if res["aprovado"] else "REPROVADO") + f" — {res['motivo']}"


def escreve_satelite(pt: dict, nome: str, site: dict, banco: Banco) -> tuple[dict | None, str]:
    from .gerador_satelite import monta
    serie = banco.serie_cotacoes(nome, dias=370)
    url_ancora = (banco.ancora_do_hub(nome, pt.get("hub") or "cotacao")
                  or banco.ancora_do_hub(nome, "cotacao"))
    llm.limpa_falhas()
    pt.setdefault("_recorte", 0)
    # titulos desta rodada contam como recentes, como na esteira (satelites.py)
    art = monta(pt, serie, url_ancora, site,
                [{"titulo": t} for t in _TITULOS_DA_RODADA] + banco.artigos_recentes(nome))
    _TITULOS_DA_RODADA.insert(0, art["titulo"])
    # monta cai no TEMPLATE quando o modelo falha OU quando o conferente
    # reprova duas vezes: o rotulo vem do proprio artigo, nao das falhas do
    # llm (JSON curto ou reprovado nao registra falha nenhuma).
    if art.get("por") == "llm":
        return art, (f"escrito por: modelo local ({art.get('motivo')}; "
                     f"dado: {art.get('dado')})")
    return art, f"escrito por: TEMPLATE — {art.get('motivo') or 'o modelo falhou'}"


def pautas_do_hub(banco: Banco, site: str, hub: str, limite: int) -> list[dict]:
    """Pautas recentes de UMA categoria (qualquer status, sem brief), uma por
    noticia: o ensaio do dado proprio por categoria (21/10/2026) precisa de
    pautas de indicadores/politica/viagem, que quase nunca chegaram a sair."""
    r = (banco.cliente.table("pautas")
         .select("id,item_id,angulo,hub,titulo_sug,dado_proprio,pontuacao,"
                 "horario_sugerido,tipo,topico_id,brief,evidencias,"
                 "itens(titulo,url,veiculo,publicado_em)")
         .eq("site", site).eq("hub", hub).is_("brief", "null")
         .order("id", desc=True).limit(limite * 8).execute())
    vistas, uteis = set(), []
    for pt in r.data or []:
        if pt.get("item_id") in vistas:
            continue
        vistas.add(pt.get("item_id"))
        uteis.append(pt)
    return uteis[:limite]


def main() -> int:
    p = argparse.ArgumentParser(description="Ensaio do modelo local sobre pautas ja' publicadas")
    p.add_argument("--site", default="doll")
    p.add_argument("--limite", type=int, default=10)
    p.add_argument("--hub", help="ensaia pautas de UMA categoria (qualquer status)")
    p.add_argument("--alternar", action="store_true",
                   help="alterna 1o e 2o recorte da categoria (pauta par = 2o)")
    args = p.parse_args()

    site = carrega_sites().get(args.site)
    if not site:
        print(f"Site '{args.site}' nao existe em config/sites.yaml")
        return 1
    if not llm.modo_local():
        print("LLM_LOCAL_URL vazio: o ensaio e' do modelo LOCAL (ver mac/LEIA-ME.md)")
        return 1
    banco = Banco(seco=False)     # so' leitura: nada abaixo grava
    PASTA.mkdir(parents=True, exist_ok=True)

    pautas = (pautas_do_hub(banco, args.site, args.hub, args.limite) if args.hub
              else pautas_publicadas(banco, args.site, args.limite))
    modelo = env("LLM_LOCAL_MODELO") or llm.MODELO_LOCAL_PADRAO
    print(f"{len(pautas)} pauta(s) publicada(s) para reescrever com {modelo}")
    for n, pt in enumerate(pautas, 1):
        guia = bool(pt.get("brief"))
        if args.alternar:
            pt["_recorte"] = (n - 1) % 2
        ref = f"guia-{pt['id']}" if guia else f"satelite-{pt['id']}"
        print(f"\n[{n}/{len(pautas)}] {ref}: {pt.get('titulo_sug') or ''}"[:140])
        inicio = time.monotonic()
        try:
            art, veredito = (escreve_guia if guia else escreve_satelite)(pt, args.site, site, banco)
        except Exception as erro:  # noqa: BLE001 — um caso quebrado nao para o ensaio
            art, veredito = None, f"erro: {type(erro).__name__}: {erro}"
        minutos = (time.monotonic() - inicio) / 60
        cabecalho = f"<!-- ensaio local | {veredito} | {minutos:.1f} min -->\n\n"
        if art:
            (PASTA / f"{args.site}-{ref}-local.md").write_text(
                cabecalho + art["markdown"], encoding="utf-8")
        no_ar = banco.artigo_existente(args.site, "guia" if guia else "satelite", ref)
        if no_ar:
            (PASTA / f"{args.site}-{ref}-no-ar.md").write_text(
                f"<!-- no ar: {no_ar.get('url_publicada') or '(sem URL)'} -->\n\n"
                f"{no_ar.get('corpo_md') or ''}", encoding="utf-8")
        print(f"  {veredito[:160]} ({minutos:.1f} min)")
    print(f"\npronto: {PASTA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
