"""Classificacao: a pauta interessa? de que hub e'? que angulo cabe?

Dois modos, na ordem: se ANTHROPIC_API_KEY existir, usa o modelo; se nao,
cai no modo por palavra-chave. O radar funciona sem chave nenhuma — a chave
so' melhora a qualidade da leitura.
"""
from __future__ import annotations

import json
import re

from .angulos import angulos_possiveis
from .config import env
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
    chave = env("ANTHROPIC_API_KEY")
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
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
    try:
        cliente = anthropic.Anthropic(api_key=chave)
        r = cliente.messages.create(model="claude-sonnet-4-5", max_tokens=300,
                                    messages=[{"role": "user", "content": prompt}])
        texto = r.content[0].text
        bruto = re.search(r"\{.*\}", texto, re.S)
        return json.loads(bruto.group(0)) if bruto else None
    except Exception:
        # Classificacao e' melhoria, nao dependencia: falhou, cai no modo por termo.
        return None


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
