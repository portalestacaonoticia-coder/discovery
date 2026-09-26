"""Ponte unica com o Claude (Anthropic). Melhoria, nunca dependencia: sem
chave ou sem SDK, devolve None e quem chama cai no seu proprio fallback.

Toda chamada ao modelo passa por aqui — classificacao, satelites, guias,
reserva. Um lugar so' para trocar de modelo e para VER as falhas: a
excecao da API nao e' engolida em silencio, ela vai para o log da rodada
(stdout do Actions) e para o resumo gravado em `execucoes`, via
`resumo_falhas()`. Antes de 26/09/2026 uma chave vencida ou um credito
esgotado so' aparecia como "post nao saiu", sem motivo.
"""
from __future__ import annotations

from .config import env

# Sonnet: rapido e barato o bastante para volume diario, bom o bastante para
# reescrever uma nota curta. Trocar por claude-opus-5 aqui se quiser mais
# qualidade a mais custo.
MODELO_LLM = "claude-sonnet-5"

# Falhas da rodada, na ordem. Cada mensagem distinta e' impressa UMA vez
# (um 429 em 80 itens nao vira 80 linhas de log) mas contada todas.
_falhas: list[str] = []
_impressas: set[str] = set()


def tem_chave() -> bool:
    return bool(env("ANTHROPIC_API_KEY"))


def _registra_falha(mensagem: str) -> None:
    _falhas.append(mensagem)
    if mensagem not in _impressas:
        _impressas.add(mensagem)
        print(f"  [llm] {mensagem}")


def falhas() -> list[str]:
    """Todas as falhas da rodada (uma entrada por chamada que falhou)."""
    return list(_falhas)


def resumo_falhas() -> str:
    """Sufixo curto para o resumo de `execucoes`; vazio se nao houve falha.
    Ex.: ' | LLM: 3 falha(s): 429 rate_limit_error ...'"""
    if not _falhas:
        return ""
    return f" | LLM: {len(_falhas)} falha(s): {_falhas[-1][:160]}"


def limpa_falhas() -> None:
    _falhas.clear()
    _impressas.clear()


def gera(prompt: str, sistema: str | None = None, max_tokens: int = 1000) -> str | None:
    """Texto do Claude, ou None se nao der (sem chave, sem SDK, ou erro).

    Sem chave e sem SDK NAO e' falha — e' o modo sem LLM, por desenho.
    Erro da API e' falha: fica registrado (ver `resumo_falhas`)."""
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
    except anthropic.APIStatusError as erro:
        # 401 chave, 403 permissao, 429 limite, 400 pedido, 5xx servidor:
        # o codigo + tipo dizem o que fazer; o request-id serve para o suporte.
        corpo = getattr(erro, "body", None)
        detalhe = (corpo or {}).get("error") if isinstance(corpo, dict) else None
        if isinstance(detalhe, dict) and detalhe.get("type"):
            texto = f"{detalhe['type']}: {detalhe.get('message') or ''}".strip(": ")
        else:
            texto = str(getattr(erro, "message", erro))
        req = getattr(erro, "request_id", None) or ""
        _registra_falha(f"HTTP {erro.status_code} {texto}"
                        + (f" (request {req})" if req else ""))
        return None
    except anthropic.APIConnectionError as erro:
        _registra_falha(f"sem conexao com a API: {erro}")
        return None
    except Exception as erro:  # noqa: BLE001 — melhoria, nunca dependencia
        _registra_falha(f"{type(erro).__name__}: {erro}")
        return None

    if getattr(r, "stop_reason", None) == "refusal":
        _registra_falha("modelo recusou o pedido (stop_reason=refusal)")
        return None
    # Junta os blocos de texto — ignora blocos de thinking, se vierem.
    partes = [b.text for b in r.content if getattr(b, "type", None) == "text"]
    return ("".join(partes)).strip() or None
