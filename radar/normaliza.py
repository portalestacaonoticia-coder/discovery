"""Normalizacao de titulo e URL — a base da deduplicacao.

A mesma noticia sai em 10 portais com titulos quase iguais e URLs cheias de
parametro de campanha. Sem normalizar, o radar entrega 10 pautas identicas.
"""
import hashlib
import re
import unicodedata
from datetime import date, datetime
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# Parametros de rastreamento nao mudam o conteudo da pagina.
LIXO_QUERY = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
              "fbclid", "gclid", "igshid", "ref", "amp"}

PALAVRAS_VAZIAS = {"a", "o", "os", "as", "de", "da", "do", "das", "dos", "e", "em",
                   "no", "na", "nos", "nas", "para", "por", "com", "um", "uma",
                   "que", "ao", "aos", "se", "sobre"}


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def normaliza_titulo(titulo: str) -> str:
    t = sem_acento(titulo.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    palavras = [p for p in t.split() if p and p not in PALAVRAS_VAZIAS]
    return " ".join(sorted(set(palavras)))


def canoniza_url(url: str) -> str:
    p = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in LIXO_QUERY]
    caminho = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc.lower().removeprefix("www."), caminho,
                       "", urlencode(query), ""))


def hash_dedup(titulo: str, quando: datetime | date | None) -> str:
    """Titulo normalizado + dia. Mesma noticia no dia seguinte conta como nova —
    e' de proposito: cobertura de desdobramento e' pauta legitima."""
    dia = ""
    if isinstance(quando, datetime):
        dia = quando.date().isoformat()
    elif isinstance(quando, date):
        dia = quando.isoformat()
    return hashlib.sha1(f"{normaliza_titulo(titulo)}|{dia}".encode()).hexdigest()


def veiculo_de(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")
