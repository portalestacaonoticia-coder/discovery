"""Coletores. Cada um devolve lista de dicionarios crus {titulo, url, publicado_em, resumo}.

Regra do projeto: o radar coleta TITULO, URL, DATA e o resumo que o proprio feed
publica. Nunca o texto integral do outro site. O radar serve para DESCOBRIR a
pauta; a apuracao acontece depois, na fonte primaria.
"""
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests
from lxml import etree

CABECALHO = {"User-Agent": "RadarPautas/1.0 (+contato@exemplo.com.br)"}
PAUSA = 1.0  # segundos entre requisicoes: educacao basica com o servidor alheio


def _data_do_feed(entrada) -> datetime | None:
    for campo in ("published_parsed", "updated_parsed"):
        valor = getattr(entrada, campo, None)
        if valor:
            return datetime.fromtimestamp(time.mktime(valor), tz=timezone.utc)
    return None


def coleta_rss(url: str) -> list[dict]:
    feed = feedparser.parse(url)
    itens = []
    for e in feed.entries:
        link = getattr(e, "link", None)
        titulo = getattr(e, "title", None)
        if not link or not titulo:
            continue
        itens.append({
            "titulo": titulo.strip(),
            "url": link,
            "publicado_em": _data_do_feed(e),
            "resumo": (getattr(e, "summary", "") or "")[:500],
        })
    return itens


def coleta_google_news(consulta: str, idioma: str = "pt-BR", pais: str = "BR") -> list[dict]:
    """Google News tem RSS publico por busca — e' a fonte mais barata de radar."""
    url = (f"https://news.google.com/rss/search?q={quote_plus(consulta)}"
           f"&hl={idioma}&gl={pais}&ceid={pais}:{idioma.split('-')[0]}")
    return coleta_rss(url)


def coleta_sitemap_news(url: str) -> list[dict]:
    """Sitemap de noticias de um concorrente. E' publico, atualiza em segundos e
    entrega titulo + data — radar mais rapido que qualquer feed."""
    resposta = requests.get(url, headers=CABECALHO, timeout=20)
    resposta.raise_for_status()
    raiz = etree.fromstring(resposta.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
          "n": "http://www.google.com/schemas/sitemap-news/0.9"}
    itens = []
    for url_no in raiz.findall("s:url", ns):
        loc = url_no.findtext("s:loc", namespaces=ns)
        titulo = url_no.findtext(".//n:title", namespaces=ns)
        data = url_no.findtext(".//n:publication_date", namespaces=ns)
        if not loc or not titulo:
            continue
        quando = None
        if data:
            try:
                quando = datetime.fromisoformat(data.replace("Z", "+00:00"))
            except ValueError:
                quando = None
        itens.append({"titulo": titulo.strip(), "url": loc,
                      "publicado_em": quando, "resumo": ""})
    return itens


def coleta(fonte: dict) -> list[dict]:
    tipo = fonte.get("tipo")
    time.sleep(PAUSA)
    if tipo == "rss":
        return coleta_rss(fonte["url"])
    if tipo == "google_news":
        return coleta_google_news(fonte["consulta"])
    if tipo == "sitemap_news":
        return coleta_sitemap_news(fonte["url"])
    raise ValueError(f"Tipo de fonte desconhecido: {tipo}")
