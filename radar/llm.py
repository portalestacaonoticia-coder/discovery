"""Ponte unica com o Claude (Anthropic). Melhoria, nunca dependencia: sem
chave ou sem SDK, devolve None e quem chama cai no seu proprio fallback.

Mesmo padrao do classifica.py, num lugar so' para os dois usarem.
"""
from __future__ import annotations

from .config import env

# Sonnet: rapido e barato o bastante para volume diario, bom o bastante para
# reescrever uma nota curta. Trocar por claude-opus-5 aqui se quiser mais
# qualidade a mais custo.
MODELO_LLM = "claude-sonnet-5"


def tem_chave() -> bool:
    return bool(env("ANTHROPIC_API_KEY"))


def gera(prompt: str, sistema: str | None = None, max_tokens: int = 1000) -> str | None:
    """Texto do Claude, ou None se nao der (sem chave, sem SDK, ou erro)."""
    chave = env("ANTHROPIC_API_KEY")
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        # Chave vinculada a workspace exige o id do workspace no header; chave
        # de conta comum ignora. Passar so' quando existir cobre os dois casos.
        cabecalhos = {}
        ws = env("ANTHROPIC_WORKSPACE_ID")
        if ws:
            cabecalhos["anthropic-workspace-id"] = ws
        cliente = anthropic.Anthropic(api_key=chave,
                                      default_headers=cabecalhos or None)
        kwargs = {"model": MODELO_LLM, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        if sistema:
            kwargs["system"] = sistema
        r = cliente.messages.create(**kwargs)
        # Junta os blocos de texto — ignora blocos de thinking, se vierem.
        partes = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        return ("".join(partes)).strip() or None
    except Exception:
        return None
