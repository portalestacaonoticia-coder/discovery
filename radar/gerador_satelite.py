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
from datetime import datetime

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


def monta(pauta: dict, serie: list[dict], url_ancora: str | None,
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
