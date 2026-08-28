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
from datetime import datetime

from . import llm
from .gerador_dolar import DIAS, MESES, brl, pct, _rumo

# Por hub: (titulo do satelite, texto do link ancora). Titulos distintos por
# hub para dois satelites do dia nao saírem com a mesma cara.
ENQUADRE_HUB = {
    "cotacao": ("Dólar a {v} nesta {dia}: cotação, variação e quanto custa comprar",
                "quanto custa comprar dólar hoje"),
    "viagem": ("Dólar a {v}: o que muda para quem vai viajar",
               "quanto custa o dólar para a sua viagem"),
    "politica-monetaria": ("Dólar a {v} nesta {dia}: o câmbio do dia em números",
                           "quanto custa comprar dólar hoje"),
    "indicadores": ("Dólar a {v} nesta {dia}: o número e o que ele mostra",
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


def _numeros(serie: list[dict]) -> dict:
    """Os numeros da base que o corpo (template ou LLM) usa."""
    venda = serie[-1]["venda"]
    anterior = serie[-2]["venda"] if len(serie) >= 2 else None
    var_dia = ((venda / anterior - 1) * 100) if anterior else None
    janela = [l["venda"] for l in serie]
    var_janela = ((venda / janela[0] - 1) * 100) if len(janela) >= 2 else None
    return {"venda": venda, "var_dia": var_dia, "var_janela": var_janela,
            "maior": max(janela), "menor": min(janela), "n": len(janela),
            "data": serie[-1]["data"]}


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

    dado = f"PTAX de venda do DOLAR: {brl(n['venda'], 4)}"
    if n["var_dia"] is not None:
        dado += f"; no dia o dolar {_mov(n['var_dia'])} {pct(abs(n['var_dia']))}"
    if n["var_janela"] is not None:
        dado += (f"; nos ultimos {n['n']} pregoes o dolar "
                 f"{_mov(n['var_janela'])} {pct(abs(n['var_janela']))}, "
                 f"oscilando entre {brl(n['menor'], 4)} e {brl(n['maior'], 4)}")

    sistema = (
        "Voce e' redator de um portal brasileiro de cambio (doll.com.br). "
        "Escreve NOTAS CURTAS de atualidade que puxam o leitor para as "
        "paginas-guia do site. Regras inegociaveis:\n"
        "- O fato da noticia de terceiro entra SEMPRE atribuido a fonte "
        "('segundo a X', 'a X noticiou') — nunca afirmado como apuracao "
        "propria. Voce NAO tem o texto da materia, so' a manchete: nao "
        "invente numero, data, causa ou detalhe que nao esteja nos dados "
        "fornecidos.\n"
        "- O valor proprio da nota e' o DADO da base (PTAX, variacao) — use-o. "
        "Atencao: quando o DOLAR sobe, o real cai (e vice-versa) — respeite a "
        "direcao exata dos dados, nunca inverta quem subiu.\n"
        "- Termine convidando a ler a pagina-guia, com o link em markdown.\n"
        "- Portugues do Brasil, tom jornalistico e direto, 120-180 palavras.\n"
        "Responda SO um JSON: {\"titulo\": \"...\", \"corpo_md\": \"...\"} — "
        "titulo ate 90 caracteres, corpo em markdown (sem repetir o titulo "
        "como H1).")
    prompt = (
        f"Hub da pauta: {hub}.\n"
        f"Gancho (manchete de terceiro): \"{manchete or 'dolar no noticiario'}\"\n"
        f"Fonte: {veiculo or 'imprensa (veiculo nao identificado)'}"
        + (f" — link: {fonte_url}" if fonte_url else "") + "\n"
        f"Dado proprio (nossa base, PTAX do Banco Central): {dado}.\n"
        f"Data de hoje (use exatamente esta, nao invente o dia da semana): "
        f"{DIAS[n['data'].weekday()]}, {n['data'].day} de "
        f"{MESES[n['data'].month - 1]} de {n['data'].year}.\n"
        f"Pagina-guia para linkar no fecho: "
        + (f"[{servico}]({url_ancora})" if url_ancora
           else "(nenhuma disponivel — feche sem link)") + "\n\n"
        "Escreva a nota.")

    saida = llm.gera(prompt, sistema=sistema, max_tokens=1200)
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
    if not titulo or len(corpo) < 80:
        return None  # saida pobre: cai no template

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
          site: dict) -> dict:
    """Satelite pelo Claude quando ha' chave; senao, pelo template. Ambos
    respeitam os mesmos guarda-corpos (fonte atribuida, dado proprio, link)."""
    via_llm = _monta_llm(pauta, serie, url_ancora, site)
    if via_llm:
        return via_llm
    return _monta_template(pauta, serie, url_ancora, site)


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

    titulo = molde_titulo.format(v=brl(venda, 4), dia=DIAS[d.weekday()])[:110]

    item = pauta.get("itens") or {}
    veiculo = _veiculo_limpo(item)
    manchete = _manchete(item)
    fonte_url = item.get("url") or ""

    # 1. o gancho, CITADO e atribuido — nunca afirmado como nosso
    if manchete and fonte_url:
        atrib = (f"a {veiculo}" if veiculo else "a imprensa especializada")
        gancho = (f"O dólar voltou ao noticiário: {atrib} destacou nesta "
                  f"{DIAS[d.weekday()]} a manchete “{manchete}” "
                  f"([leia na fonte]({fonte_url})). A checagem do fato é da "
                  f"publicação de origem; aqui, o que trazemos é o número.")
    else:
        gancho = (f"O dólar segue no centro das atenções do mercado nesta "
                  f"{DIAS[d.weekday()]}.")

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
