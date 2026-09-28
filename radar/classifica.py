"""Classificacao: a pauta interessa? de que hub e'? que angulo cabe?

Dois modos, na ordem: se OPENAI_API_KEY existir, usa o gpt-6-luna pela ponte
unica (llm.py); se nao, cai no modo por palavra-chave. O radar funciona sem chave nenhuma — a chave
so' melhora a qualidade da leitura.

A chamada ao modelo passa pela ponte `llm.py` (mesmo modelo e mesmo registro
de falhas do resto do radar). Ate 26/09/2026 este arquivo criava o proprio
cliente com um modelo mais caro e engolia a excecao — um 429 aqui sumia sem
deixar rastro.
"""
from __future__ import annotations

import json
import re

from . import llm
from .angulos import angulos_possiveis
from .normaliza import sem_acento


def _pontua_hub(titulo: str, hub: dict) -> int:
    alvo = sem_acento(titulo.lower())
    return sum(1 for termo in hub.get("termos", []) if sem_acento(termo.lower()) in alvo)


def classifica_por_termo(titulo: str, site: dict) -> tuple[str | None, int]:
    """Devolve (hub_id, pontuacao). Pontuacao 0 = provavelmente nao interessa."""
    melhor, pontos = None, 0
    for hub in site.get("hubs", []):
        p = _pontua_hub(titulo, hub)
        if p > pontos:
            melhor, pontos = hub["id"], p
    return melhor, pontos


def classifica_por_llm(titulo: str, resumo: str, site: dict) -> dict | None:
    """Leitura do modelo, ou None (sem chave, erro de API ou resposta sem
    JSON) — e ai' o chamador cai no modo por termo."""
    if not llm.tem_chave():
        return None

    hubs = "\n".join(f"- {h['id']}: {h['titulo']}" for h in site.get("hubs", []))
    prompt = (
        f"Site sobre: {site['entidade']}.\n"
        f"Hubs disponiveis:\n{hubs}\n\n"
        f"Noticia detectada:\nTitulo: {titulo}\nResumo: {resumo[:400]}\n\n"
        "Responda SO um JSON: {\"relevante\": bool, \"hub\": \"id ou null\", "
        "\"lugar\": \"cidade citada ou null\", \"publico\": \"quem e' afetado, "
        "em 3 palavras\", \"prioridade\": 0-10}"
    )
    texto = llm.gera(prompt, max_tokens=300, modelo=llm.MODELO_CLASSIFICA,
                     json_obj=True)
    if not texto:
        # Classificacao e' melhoria, nao dependencia: falhou, cai no modo por
        # termo. Avisa no log, senao a queda de qualidade passa despercebida
        # (o motivo da falha de API ja' saiu na linha [llm]).
        print(f"  classificacao por LLM falhou, usando palavra-chave: {titulo[:60]}")
        return None
    try:
        bruto = re.search(r"\{.*\}", texto, re.S)
        leitura = json.loads(bruto.group(0)) if bruto else None
    except (json.JSONDecodeError, AttributeError):
        leitura = None
    if not isinstance(leitura, dict):
        print(f"  classificacao por LLM veio sem JSON, usando palavra-chave: {titulo[:60]}")
        return None
    return leitura


def avalia(titulo: str, resumo: str, site: dict) -> dict:
    leitura = classifica_por_llm(titulo, resumo, site)
    if leitura:
        return {
            "relevante": bool(leitura.get("relevante")),
            "hub": leitura.get("hub"),
            "lugar": leitura.get("lugar"),
            "publico": leitura.get("publico") or "o publico do site",
            "prioridade": int(leitura.get("prioridade") or 0),
        }
    hub, pontos = classifica_por_termo(titulo, site)
    return {"relevante": pontos > 0, "hub": hub, "lugar": None,
            "publico": "o publico do site", "prioridade": pontos}


def sugere(titulo: str, leitura: dict, dado: dict | None,
           site: dict | None = None) -> list[dict]:
    """Monta as pautas a partir do fato + angulos possiveis + dado proprio.

    'dado' vem de radar.principal.dado_proprio: {"curto": "4a", "detalhe": "...",
    "texto": "..."} — 'curto' entra no titulo, 'texto' vai para a pauta como
    material de apuracao.
    """
    fato = titulo.rstrip(".")
    moldes = (site or {}).get("moldes", {})
    sugestoes = []
    for angulo in angulos_possiveis(bool(dado)):
        molde = moldes.get(angulo.id, angulo.molde_titulo)
        titulo_sug = (molde
                      .replace("{fato}", fato)
                      .replace("{dado_curto}", (dado or {}).get("curto", ""))
                      .replace("{lugar}", f"em {leitura['lugar']}" if leitura.get("lugar") else "")
                      .replace("{publico}", leitura.get("publico", "o leitor")))
        titulo_sug = re.sub(r"\s+([:,.])", r"\1", re.sub(r"\s{2,}", " ", titulo_sug)).strip()
        sugestoes.append({
            "angulo": angulo.id,
            "titulo_sug": titulo_sug,
            "dado_proprio": (dado or {}).get("texto") if angulo.exige_dado else None,
            "prioridade": leitura["prioridade"] + (3 if angulo.exige_dado else 0),
        })
    return sugestoes
