"""Busca na web SEM API paga, para o modo local do llm.py (16/10/2026).

Na nuvem, `llm.gera_com_busca` usa a busca da propria OpenAI: o modelo busca,
le as paginas e devolve o texto com citacoes. No Mac nao ha' isso — o modelo
local (Qwen no exo) nao navega. Entao o CODIGO faz a parte da busca:

  1. pesquisa no SearXNG (metabuscador gratis, rodando no proprio Mac);
  2. fica so' com resultados dos dominios permitidos (as fontes oficiais do hub);
  3. baixa as paginas e tira o texto visivel;
  4. entrega o texto ao modelo, que escreve citando as URLs que recebeu.

Cada pagina lida volta com o TEXTO junto (`texto`), para a pesquisa poder
conferir por codigo que o valor de um fato esta' mesmo na pagina citada
(pesquisa._valor_lido) — o modelo local inventa numero com toda a seguranca
(teste de 16/10: duas aliquotas de IOF diferentes para a mesma pergunta).

Sem SEARXNG_URL, nada e' buscado e quem chama recebe lista vazia.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import requests
from lxml import html as lxml_html

from .config import env

TIMEOUT_BUSCA_S = 20
TIMEOUT_PAGINA_S = 20
MAX_PAGINAS = 4                  # paginas lidas por pedido
MAX_CARACTERES_PAGINA = 6000     # ~1.500 tokens por pagina no prompt
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; radar-tihee/1.0)",
              "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6,es;q=0.5"}
# Tags que nunca sao texto do artigo.
_DESCARTA = ("script", "style", "noscript", "nav", "header", "footer", "aside",
             "form", "svg", "iframe")


def ligada() -> bool:
    return bool(env("SEARXNG_URL"))


def dominio(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def permitido(url: str, dominios: list[str]) -> bool:
    host = dominio(url)
    return any(host == d or host.endswith("." + d) for d in dominios)


def pesquisa(consulta: str, dominios: list[str], limite: int = 8) -> list[dict]:
    """Resultados [{url, titulo, trecho}] do SearXNG, so' dos dominios
    permitidos, sem URL repetida. O `site:` vai na consulta para os
    buscadores que o entendem; o filtro por dominio e' o que vale."""
    base = (env("SEARXNG_URL") or "").rstrip("/")
    if not base or not consulta.strip():
        return []
    dominios = [d.lower().removeprefix("www.") for d in dominios if d]
    filtro = " OR ".join(f"site:{d}" for d in dominios[:6])
    q = f"{consulta} ({filtro})" if filtro else consulta
    try:
        r = requests.get(f"{base}/search", params={"q": q, "format": "json",
                                                   "language": "pt-BR"},
                         headers=CABECALHOS, timeout=TIMEOUT_BUSCA_S)
        r.raise_for_status()
        dados = r.json()
    except (requests.RequestException, ValueError) as erro:
        print(f"  [busca local] SearXNG falhou: {erro}")
        return []
    vistos: set[str] = set()
    saida: list[dict] = []
    for item in dados.get("results") or []:
        url = str(item.get("url") or "").strip()
        if not url.startswith("http") or (dominios and not permitido(url, dominios)):
            continue
        chave = url.rstrip("/")
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append({"url": url, "titulo": str(item.get("title") or url).strip(),
                      "trecho": str(item.get("content") or "").strip()})
        if len(saida) >= limite:
            break
    return saida


def texto_da_pagina(conteudo: bytes | str) -> str:
    """Texto visivel de um HTML, sem menu/rodape/script, espacos colapsados."""
    if not conteudo:
        return ""
    try:
        arvore = lxml_html.fromstring(conteudo)
    except (ValueError, lxml_html.etree.ParserError):
        return ""
    # Lista antes de remover: tirar no' durante o iter() pula irmaos.
    for no in [n for n in arvore.iter(*_DESCARTA) if n.getparent() is not None]:
        no.drop_tree()
    # `or` nao serve aqui: elemento lxml sem filhos e' falso.
    corpo = arvore.find(".//main")
    if corpo is None:
        corpo = arvore.find(".//article")
    if corpo is None:
        corpo = arvore
    texto = corpo.text_content()
    return re.sub(r"\s+", " ", texto).strip()


def le_pagina(url: str) -> str:
    try:
        r = requests.get(url, headers=CABECALHOS, timeout=TIMEOUT_PAGINA_S)
    except requests.RequestException as erro:
        print(f"  [busca local] nao abriu {url}: {erro}")
        return ""
    tipo = r.headers.get("Content-Type", "")
    if not r.ok or ("html" not in tipo and "text" not in tipo):
        return ""
    return texto_da_pagina(r.content)[:MAX_CARACTERES_PAGINA]


def busca_e_le(consultas: list[str], dominios: list[str],
               max_paginas: int = MAX_PAGINAS) -> list[dict]:
    """Roda as consultas, junta os resultados e le as primeiras paginas.
    Devolve [{url, titulo, texto}] so' das paginas que tinham texto."""
    candidatos: list[dict] = []
    vistos: set[str] = set()
    for consulta in consultas:
        for r in pesquisa(consulta, dominios):
            chave = r["url"].rstrip("/")
            if chave not in vistos:
                vistos.add(chave)
                candidatos.append(r)
    lidas: list[dict] = []
    for c in candidatos:
        if len(lidas) >= max_paginas:
            break
        texto = le_pagina(c["url"])
        if len(texto) < 200:     # pagina vazia, PDF, bloqueio: nao serve de fonte
            continue
        lidas.append({"url": c["url"], "titulo": c["titulo"], "texto": texto})
    return lidas
