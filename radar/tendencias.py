"""Trend Engine: agrupa os sinais de um hub em TOPICOS e mede a velocidade
de cada um.

Um topico e' um assunto que aparece em mais de um lugar: a manchete de
varios veiculos, a query que subiu no Trends, a pergunta do People Also Ask,
o video da semana. O agrupamento e' por palavras (mesma base da dedup do
radar antigo, radar/normaliza.py): grosseiro, mas suficiente com os termos
do hub. Se um dia precisar de sinonimo e flexao, troca-se aqui por
embeddings sem mexer no resto.

Tres velocidades saem daqui, todas em 0..1:
  velocidade_tendencia  quanto o Trends diz que o assunto subiu
  velocidade_noticias   quantos veiculos cobriram nas ultimas 24h, contra a
                        media da semana
  frescor               quanto tempo faz que o assunto apareceu pela ultima
                        vez (o Discover vive ~72h)
"""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone

from .normaliza import normaliza_titulo

# Ordem em que os sinais abrem cluster: manchete primeiro (e' o texto mais
# completo), depois o que o Trends diz que sobe, depois o resto.
ORDEM_TIPO = {"noticia": 0, "trend_rising": 1, "relacionada": 2, "paa": 3,
              "organico": 4, "trend_top": 5, "social": 6}
JACCARD_MINIMO = 0.34
TOKENS_COMUNS_MINIMO = 2
TOKEN_MINIMO = 4        # letras; "de", "com", "para" ja' saem na normalizacao


def tokens(texto: str) -> set[str]:
    return {t for t in normaliza_titulo(texto or "").split() if len(t) >= TOKEN_MINIMO}


def _quando(sinal: dict, agora: datetime) -> datetime:
    bruto = sinal.get("publicado_em") or sinal.get("coletado_em")
    if not bruto:
        return agora
    if isinstance(bruto, datetime):
        return bruto if bruto.tzinfo else bruto.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return agora


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def chave_do_topico(contagem: Counter) -> str:
    principais = sorted(t for t, _ in contagem.most_common(5))
    return hashlib.sha1(" ".join(principais).encode()).hexdigest()[:20]


def agrupa_topicos(sinais: list[dict], hub: dict, agora: datetime) -> list[dict]:
    """Clustering guloso: cada sinal entra no primeiro cluster com que
    compartilha vocabulario; senao abre um. Devolve topicos com os
    agregados que a pontuacao usa. Cluster de um sinal so' fica se for
    manchete ou query em alta (o resto e' ruido)."""
    ordenados = sorted(
        (s for s in sinais if s.get("texto")),
        key=lambda s: (ORDEM_TIPO.get(s.get("tipo"), 9), -(s.get("valor") or 0)))
    clusters: list[dict] = []
    for s in ordenados:
        toks = tokens(s["texto"])
        if not toks:
            continue
        alvo = None
        for c in clusters:
            if (_jaccard(toks, c["tokens"]) >= JACCARD_MINIMO
                    or len(toks & c["tokens"]) >= TOKENS_COMUNS_MINIMO):
                alvo = c
                break
        if alvo is None:
            alvo = {"tokens": set(), "contagem": Counter(), "sinais": []}
            clusters.append(alvo)
        alvo["tokens"] |= toks
        alvo["contagem"].update(toks)
        alvo["sinais"].append(s)

    topicos = []
    for c in clusters:
        tipos = Counter(s.get("tipo") for s in c["sinais"])
        if len(c["sinais"]) < 2 and not (tipos["noticia"] or tipos["trend_rising"]):
            continue
        topicos.append(_monta_topico(c, hub, agora, tipos))
    return topicos


def _monta_topico(c: dict, hub: dict, agora: datetime, tipos: Counter) -> dict:
    sinais = c["sinais"]
    noticias = [s for s in sinais if s.get("tipo") == "noticia"]
    janelas = {"24h": set(), "7d": set(), "30d": set()}
    for n in noticias:
        idade = agora - _quando(n, agora)
        v = n.get("veiculo") or "?"
        if idade <= timedelta(hours=24):
            janelas["24h"].add(v)
        if idade <= timedelta(days=7):
            janelas["7d"].add(v)
        if idade <= timedelta(days=30):
            janelas["30d"].add(v)

    def maior_valor(tipo):
        vals = [float(s.get("valor") or 0) for s in sinais if s.get("tipo") == tipo]
        return max(vals) if vals else 0.0

    candidatos_rotulo = ([s["texto"] for s in noticias]
                         or [s["texto"] for s in sinais if s.get("tipo") in ("trend_rising", "relacionada", "organico")]
                         or [s["texto"] for s in sinais])
    vistos = [_quando(s, agora) for s in sinais]
    social = [s for s in sinais if s.get("tipo") == "social"]
    return {
        "chave": chave_do_topico(c["contagem"]),
        "rotulo": min(candidatos_rotulo, key=len)[:160],
        "termos": [t for t, _ in c["contagem"].most_common(10)],
        "hub": hub.get("id"),
        "total_sinais": len(sinais),
        "por_tipo": dict(tipos),
        "sinais_ids": [s["id"] for s in sinais if s.get("id")],
        "veiculos_24h": sorted(janelas["24h"]),
        "veiculos_7d": sorted(janelas["7d"]),
        "veiculos_30d": sorted(janelas["30d"]),
        "trend_rising": maior_valor("trend_rising"),
        "trend_top": maior_valor("trend_top"),
        "perguntas": [s["texto"] for s in sinais if s.get("tipo") == "paa"][:10],
        "relacionadas": [s["texto"] for s in sinais if s.get("tipo") == "relacionada"][:10],
        "organicos": [{"titulo": s["texto"], "url": s.get("url"),
                       "snippet": (s.get("extra") or {}).get("snippet"),
                       "data": (s.get("extra") or {}).get("data")}
                      for s in sinais if s.get("tipo") == "organico"][:10],
        "manchetes": [{"titulo": s["texto"], "veiculo": s.get("veiculo"),
                       "url": s.get("url"), "publicado_em": s.get("publicado_em")}
                      for s in sorted(noticias, key=lambda n: _quando(n, agora), reverse=True)][:8],
        "social": [{"fonte": s.get("fonte"), "texto": s["texto"], "url": s.get("url"),
                    "valor": s.get("valor"), "publicado_em": s.get("publicado_em")}
                   for s in social][:10],
        "primeiro_visto": min(vistos).isoformat(),
        "ultimo_visto": max(vistos).isoformat(),
        "tem_miniatura": any((s.get("extra") or {}).get("tem_miniatura") for s in sinais),
    }


def velocidade_tendencia(topico: dict) -> float:
    rising = float(topico.get("trend_rising") or 0)
    if rising > 0:
        return min(1.0, rising / 500)
    top = float(topico.get("trend_top") or 0)
    if top > 0:
        return min(1.0, top / 100) * 0.5
    if topico.get("relacionadas"):
        return 0.2
    return 0.0


def velocidade_noticias(topico: dict) -> float:
    v24 = len(topico.get("veiculos_24h") or [])
    v7 = len(topico.get("veiculos_7d") or [])
    if v24 == 0:
        return 0.0
    razao = v24 / max(1.0, v7 / 7)
    return round(0.6 * min(1.0, razao / 3) + 0.4 * min(1.0, v24 / 8), 3)


def frescor(topico: dict, agora: datetime) -> float:
    ultimo = topico.get("ultimo_visto")
    if not ultimo:
        return 0.0
    horas = (agora - _quando({"publicado_em": ultimo}, agora)).total_seconds() / 3600
    if horas <= 6:
        return 1.0
    if horas <= 24:
        return 0.7
    if horas <= 48:
        return 0.4
    if horas <= 72:
        return 0.2
    return 0.0


def funde_com_historico(topicos: list[dict], anteriores: list[dict]) -> list[dict]:
    """Topico que ja' existia em dias anteriores herda o primeiro_visto e o
    status (pautado nao volta a ser candidato)."""
    por_chave: dict[str, dict] = {}
    for a in anteriores or []:
        chave = a.get("chave")
        if not chave:
            continue
        atual = por_chave.get(chave)
        if atual is None or (a.get("primeiro_visto") or "") < (atual.get("primeiro_visto") or ""):
            por_chave[chave] = a
    for t in topicos:
        a = por_chave.get(t["chave"])
        if not a:
            continue
        if a.get("primeiro_visto") and a["primeiro_visto"] < t["primeiro_visto"]:
            t["primeiro_visto"] = a["primeiro_visto"]
        if a.get("status") == "pautado":
            t["ja_pautado"] = True
            t["pauta_id"] = a.get("pauta_id")
    return topicos
