"""Artigo-satelite: a nota rapida que puxa a atualidade para o texto ancora.

Tres guarda-corpos que o mantem defensavel (o fato e' de terceiro, nao nosso):
  1. O gancho da noticia entra CITADO e ATRIBUIDO a fonte, com link — nunca
     afirmado como apuracao propria. Erro da fonte fica com a fonte.
  2. O corpo tem valor PROPRIO: o dado da nossa base (PTAX, variacao).
  3. Fecha com link para o texto ancora do hub — a finalidade do satelite.

Sem LLM (o radar nao tem chave de texto): titulo e corpo sao template,
derivados do dado + hub. Por isso o fluxo limita a um satelite por hub por
dia — varios sobre o mesmo dado viraria o conteudo em escala que queremos
evitar.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from . import llm
from .gerador_dolar import DIAS, MESES, brl, pct, _rumo

FUSO_SP = timezone(timedelta(hours=-3))


def _data_extenso(d) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"

# Por hub: (titulo do satelite, texto do link ancora). Titulos distintos por
# hub para dois satelites do dia nao saírem com a mesma cara. {quando} vira
# "nesta sexta-feira" ou "no fechamento de sexta-feira" conforme o dia real.
ENQUADRE_HUB = {
    "cotacao": ("Dólar a {v} {quando}: cotação, variação e quanto custa comprar",
                "quanto custa comprar dólar hoje"),
    "viagem": ("Dólar a {v}: o que muda para quem vai viajar",
               "quanto custa o dólar para a sua viagem"),
    "politica-monetaria": ("Dólar a {v} {quando}: o câmbio do dia em números",
                           "quanto custa comprar dólar hoje"),
    "indicadores": ("Dólar a {v} {quando}: o número e o que ele mostra",
                    "quanto custa comprar dólar hoje"),
}


def _veiculo_limpo(item: dict) -> str:
    v = (item or {}).get("veiculo") or ""
    # news.google.com nao e' um veiculo — e' o agregador. Vira "veiculos de
    # imprensa" quando nao da' para nomear a fonte real.
    if not v or "google" in v.lower():
        return ""
    return v


def _manchete(item: dict) -> str:
    """O titulo da noticia sem o sufixo ' - Veiculo' que o feed cola."""
    t = ((item or {}).get("titulo") or "").strip()
    return t.rsplit(" - ", 1)[0].strip() if " - " in t else t


def _variacao(serie: list[dict], pregoes: int) -> float | None:
    if len(serie) <= pregoes:
        return None
    return (serie[-1]["venda"] / serie[-1 - pregoes]["venda"] - 1) * 100


def _numeros(serie: list[dict]) -> dict:
    """Os numeros da base que o corpo (template ou LLM) usa. A serie pode
    ter ate um ano — quanto mais longa, mais contexto honesto o texto tem
    (era a reclamacao de 01/09: posts rasos)."""
    venda = serie[-1]["venda"]
    anterior = serie[-2]["venda"] if len(serie) >= 2 else None
    var_dia = ((venda / anterior - 1) * 100) if anterior else None
    ult30 = serie[-22:]
    janela = [l["venda"] for l in ult30]
    var_janela = ((venda / janela[0] - 1) * 100) if len(janela) >= 2 else None

    # sequencia de pregoes na mesma direcao (0.5 centavo de tolerancia)
    seq, direcao = 0, 0
    for i in range(len(serie) - 1, 0, -1):
        d = serie[i]["venda"] - serie[i - 1]["venda"]
        passo = 1 if d > 0.005 else -1 if d < -0.005 else 0
        if seq == 0:
            direcao = passo
        if passo == 0 or passo != direcao:
            break
        seq += 1

    tudo = [l["venda"] for l in serie]
    max_ano, min_ano = max(tudo), min(tudo)
    max_quando = serie[tudo.index(max_ano)]["data"]
    min_quando = serie[tudo.index(min_ano)]["data"]
    return {"venda": venda, "var_dia": var_dia, "var_janela": var_janela,
            "maior": max(janela), "menor": min(janela), "n": len(janela),
            "var_semana": _variacao(serie, 5), "var_mes": _variacao(serie, 21),
            "seq": seq, "direcao": direcao,
            "max_ano": max_ano, "min_ano": min_ano,
            "max_quando": max_quando, "min_quando": min_quando,
            "pregoes_serie": len(serie), "data": serie[-1]["data"]}


def _apendices(site: dict, serie: list[dict], leia_tambem: list[dict],
               evitar_url: str | None) -> str:
    """Blocos determinISTICOS (fora do LLM, zero invencao): a conversao do
    dia com IOF e os links internos. E' o que da corpo de servico ao post."""
    venda = serie[-1]["venda"]
    iof = float((site.get("iof") or {}).get("cartao_credito", 3.5))
    linhas = "\n".join(
        f"| US$ {v:,.0f}".replace(",", ".")
        + f" | {brl(v * venda)} | {brl(v * venda * (1 + iof / 100))} |"
        for v in (100, 500, 1000))
    partes = [
        "\n\n## O dólar na prática, hoje\n\n"
        "| Valor | Pela PTAX | No cartão (com IOF de "
        f"{pct(iof)}) |\n|---|---|---|\n{linhas}\n\n"
        f"*Conversão pela PTAX de venda de {brl(venda, 4)}; casas de câmbio "
        "e bancos somam o próprio spread.*"]
    # Variedade no Leia tambem: 1 por tipo (guia evergreen > artigo do dia >
    # nota), senao saem tres notas gemeas da mesma cotacao.
    candidatos = [a for a in (leia_tambem or [])
                  if a.get("url_publicada") and a["url_publicada"] != evitar_url]
    uteis, tipos_vistos = [], set()
    for tipo in ("ancora", "calendario", "satelite", "reserva"):
        for a in candidatos:
            if (a.get("tipo") or "satelite") == tipo and tipo not in tipos_vistos:
                uteis.append(a)
                tipos_vistos.add(tipo)
                break
    urls_usadas = {a["url_publicada"] for a in uteis}
    for a in candidatos:      # completa ate 3 se faltou variedade
        if len(uteis) >= 3:
            break
        if a["url_publicada"] not in urls_usadas:
            uteis.append(a)
            urls_usadas.add(a["url_publicada"])
    uteis = uteis[:3]
    if uteis:
        partes.append("\n\n**Leia também**\n" + "\n".join(
            f"- [{a['titulo']}]({a['url_publicada']})" for a in uteis))
    partes.append("\n\n*Números apurados pela Doll a partir da PTAX do "
                  "Banco Central.*")
    return "".join(partes)


def _monta_llm(pauta: dict, serie: list[dict], url_ancora: str | None,
               site: dict) -> dict | None:
    """Escreve o satelite com o Claude. None se nao houver chave/SDK ou falhar
    — quem chama cai no template. Os guarda-corpos vao no prompt: gancho
    atribuido a fonte, corpo ancorado no dado, fecho com link ancora."""
    if not llm.tem_chave():
        return None
    n = _numeros(serie)
    item = pauta.get("itens") or {}
    veiculo = _veiculo_limpo(item)
    manchete = _manchete(item)
    fonte_url = item.get("url") or ""
    hub = pauta.get("hub") or "cotacao"
    _, servico = ENQUADRE_HUB.get(hub, ENQUADRE_HUB["cotacao"])

    def _mov(v):
        return "subiu" if v > 0.005 else "caiu" if v < -0.005 else "ficou estavel"

    fatos = [f"PTAX de venda do DOLAR: {brl(n['venda'], 4)}"]
    if n["var_dia"] is not None:
        fatos.append(f"no pregao o dolar {_mov(n['var_dia'])} {pct(abs(n['var_dia']))}")
    if n["var_semana"] is not None:
        fatos.append(f"na semana (5 pregoes) {_mov(n['var_semana'])} "
                     f"{pct(abs(n['var_semana']))}")
    if n["var_mes"] is not None:
        fatos.append(f"no mes (21 pregoes) {_mov(n['var_mes'])} "
                     f"{pct(abs(n['var_mes']))}")
    if n["var_janela"] is not None:
        fatos.append(f"nos ultimos {n['n']} pregoes oscilou entre "
                     f"{brl(n['menor'], 4)} e {brl(n['maior'], 4)}")
    if n.get("seq", 0) >= 2:
        fatos.append(f"e' o {n['seq']}o pregao seguido de "
                     f"{'alta' if n['direcao'] > 0 else 'queda'}")
    if n.get("pregoes_serie", 0) >= 120:
        fatos.append(
            f"nos ultimos {n['pregoes_serie']} pregoes (~1 ano): maxima de "
            f"{brl(n['max_ano'], 4)} em {n['max_quando']:%d/%m/%Y} e minima "
            f"de {brl(n['min_ano'], 4)} em {n['min_quando']:%d/%m/%Y}")
    dado = "; ".join(fatos)

    sistema = (
        "Voce e' redator de um portal brasileiro de cambio (doll.com.br). "
        "Escreve NOTAS CURTAS de atualidade que puxam o leitor para as "
        "paginas-guia do site. Regras inegociaveis:\n"
        "- O fato da noticia de terceiro entra SEMPRE atribuido a fonte "
        "('segundo a X', 'a X noticiou') — nunca afirmado como apuracao "
        "propria. Voce NAO tem o texto da materia, so' a manchete: nao "
        "invente numero, data, causa ou detalhe que nao esteja nos dados "
        "fornecidos.\n"
        "- O valor proprio do texto e' o DADO da base (PTAX e variacoes) — "
        "use TODOS os numeros fornecidos, tecendo o contexto: o dia, a "
        "semana, o mes, a sequencia e a posicao frente aos extremos do ano "
        "(ex.: a que distancia esta da maxima). Atencao: quando o DOLAR "
        "sobe, o real cai (e vice-versa) — respeite a direcao exata, nunca "
        "inverta quem subiu.\n"
        "- Estruture em 3-4 paragrafos com UM subtitulo markdown (##) no "
        "meio; nada de lista de topicos.\n"
        "- Termine convidando a ler a pagina-guia, com o link em markdown.\n"
        "- Portugues do Brasil, tom jornalistico e direto, 250-350 palavras.\n"
        "Responda SO um JSON: {\"titulo\": \"...\", \"corpo_md\": \"...\"} — "
        "titulo ate 90 caracteres, corpo em markdown (sem repetir o titulo "
        "como H1).")
    prompt = (
        f"Hub da pauta: {hub}.\n"
        f"Gancho (manchete de terceiro): \"{manchete or 'dolar no noticiario'}\"\n"
        f"Fonte: {veiculo or 'imprensa (veiculo nao identificado)'}"
        + (f" — link: {fonte_url}" if fonte_url else "") + "\n"
        f"Dado proprio (nossa base, PTAX do Banco Central): {dado}.\n"
        f"HOJE e': {_data_extenso(datetime.now(FUSO_SP).date())}.\n"
        f"A cotacao e' do PREGAO de: {_data_extenso(n['data'])}.\n"
        "Se hoje e o pregao forem dias DIFERENTES (noite, fim de semana), "
        "deixe isso claro no texto (ex.: 'no fechamento de sexta-feira') e "
        "NUNCA chame o dia do pregao de hoje.\n"
        f"Pagina-guia para linkar no fecho: "
        + (f"[{servico}]({url_ancora})" if url_ancora
           else "(nenhuma disponivel — feche sem link)") + "\n\n"
        "Escreva a nota.")

    saida = llm.gera(prompt, sistema=sistema, max_tokens=1800)
    if not saida:
        return None
    bruto = re.search(r"\{.*\}", saida, re.S)
    if not bruto:
        return None
    try:
        d = json.loads(bruto.group(0))
    except json.JSONDecodeError:
        return None
    titulo = str(d.get("titulo") or "").strip()[:110]
    corpo = str(d.get("corpo_md") or "").strip()
    if not titulo or len(corpo) < 500:
        return None  # saida pobre/rasa: cai no template

    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": titulo, "datePublished": agora, "dateModified": agora,
        "inLanguage": site.get("idioma", "pt-BR"), "isAccessibleForFree": True,
        "publisher": {"@type": "NewsMediaOrganization", "name": site["entidade"]},
        "about": {"@type": "Thing", "name": "Cotação do dólar"},
    }, ensure_ascii=False, indent=2)
    markdown = f"# {titulo}\n\n{corpo}\n"
    resumo = corpo.split("\n\n")[0][:280]
    return {"titulo": titulo, "markdown": markdown, "resumo": resumo,
            "jsonld": jsonld, "por": "llm"}


def monta(pauta: dict, serie: list[dict], url_ancora: str | None,
          site: dict, leia_tambem: list[dict] | None = None) -> dict:
    """Satelite pelo Claude quando ha' chave; senao, pelo template. Ambos
    respeitam os mesmos guarda-corpos (fonte atribuida, dado proprio, link)
    e ganham os apendices deterministicos: conversao do dia + Leia tambem."""
    art = _monta_llm(pauta, serie, url_ancora, site) \
        or _monta_template(pauta, serie, url_ancora, site)
    art["markdown"] = art["markdown"].rstrip() + _apendices(
        site, serie, leia_tambem or [], url_ancora)
    return art


def _monta_template(pauta: dict, serie: list[dict], url_ancora: str | None,
                    site: dict) -> dict:
    """Devolve {titulo, markdown, resumo, jsonld}. serie em ordem crescente."""
    venda = serie[-1]["venda"]
    anterior = serie[-2]["venda"] if len(serie) >= 2 else None
    var_dia = ((venda / anterior - 1) * 100) if anterior else None
    janela = [l["venda"] for l in serie]
    var_janela = ((venda / janela[0] - 1) * 100) if len(janela) >= 2 else None
    maior, menor = (max(janela), min(janela)) if janela else (venda, venda)
    d = serie[-1]["data"]
    data_extenso = f"{d.day} de {MESES[d.month - 1]} de {d.year}"

    hub = pauta.get("hub") or "cotacao"
    molde_titulo, servico = ENQUADRE_HUB.get(hub, ENQUADRE_HUB["cotacao"])

    # "nesta sexta-feira" so' quando o pregao E' hoje; de noite ou no fim de
    # semana o dado e' do fechamento anterior e o texto precisa dizer isso.
    mesmo_dia = d == datetime.now(FUSO_SP).date()
    quando = (f"nesta {DIAS[d.weekday()]}" if mesmo_dia
              else f"no fechamento de {DIAS[d.weekday()]}")
    titulo = molde_titulo.format(v=brl(venda, 4), quando=quando)[:110]

    item = pauta.get("itens") or {}
    veiculo = _veiculo_limpo(item)
    manchete = _manchete(item)
    fonte_url = item.get("url") or ""

    # 1. o gancho, CITADO e atribuido — nunca afirmado como nosso
    if manchete and fonte_url:
        atrib = (f"a {veiculo}" if veiculo else "a imprensa especializada")
        gancho = (f"O dólar voltou ao noticiário: {atrib} destacou a manchete "
                  f"“{manchete}” ([leia na fonte]({fonte_url})). A checagem do "
                  f"fato é da publicação de origem; aqui, o que trazemos é o "
                  f"número {quando.replace('nesta', 'desta')}.")
    else:
        gancho = "O dólar segue no centro das atenções do mercado."

    # 2. o dado PROPRIO — verificavel, da nossa base
    dado = (f"Na PTAX de venda, referência do Banco Central, a moeda está em "
            f"**{brl(venda, 4)}**")
    if var_dia is not None:
        dado += f" — {_rumo(var_dia)} de {pct(abs(var_dia))} ante o pregão anterior"
    dado += "."
    if var_janela is not None:
        dado += (f" Nos últimos {len(janela)} pregões, acumula "
                 f"{'alta' if var_janela > 0 else 'queda'} de "
                 f"{pct(abs(var_janela))}, entre {brl(menor, 4)} e {brl(maior, 4)}.")

    # 3. a ponte para o ancora — a finalidade do satelite
    if url_ancora:
        ponte = (f"👉 Antes de comprar, veja **[{servico}]({url_ancora})** — "
                 f"com tabela de conversão e o IOF de cada forma de levar dólar.")
    else:
        ponte = ""

    resumo = (f"O dólar aparece de novo no noticiário; na PTAX, a moeda está em "
              f"{brl(venda, 4)}"
              + (f", {_rumo(var_dia)} de {pct(abs(var_dia))} no dia" if var_dia is not None else "")
              + ".")

    markdown = f"""# {titulo}

{gancho}

{dado}

{ponte}

---

*Números apurados pela Doll a partir da PTAX de venda do Banco Central
({data_extenso}). A PTAX é a taxa de referência oficial; o preço ao consumidor
soma o spread da instituição e os tributos.*
"""

    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": titulo, "datePublished": agora, "dateModified": agora,
        "inLanguage": site.get("idioma", "pt-BR"), "isAccessibleForFree": True,
        "publisher": {"@type": "NewsMediaOrganization", "name": site["entidade"]},
        "about": {"@type": "Thing", "name": "Cotação do dólar"},
    }, ensure_ascii=False, indent=2)

    return {"titulo": titulo, "markdown": markdown, "resumo": resumo,
            "jsonld": jsonld}
