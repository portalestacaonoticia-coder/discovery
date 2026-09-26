"""Ponte unica com o Claude (Anthropic). Melhoria, nunca dependencia: sem
chave ou sem SDK, devolve None e quem chama cai no seu proprio fallback.

Toda chamada ao modelo passa por aqui — classificacao, satelites, guias,
reserva. Um lugar so' para trocar de modelo e para VER as falhas: a
excecao da API nao e' engolida em silencio, ela vai para o log da rodada
(stdout do Actions) e para o resumo gravado em `execucoes`, via
`resumo_falhas()`. Antes de 26/09/2026 uma chave vencida ou um credito
esgotado so' aparecia como "post nao saiu", sem motivo.

Duas portas:
  gera()           texto puro, sem ferramenta.
  gera_com_busca() texto + CITACOES, com a busca na web da propria API
                   restrita a uma lista de dominios (as fontes oficiais do
                   hub). E' o que da' ao guia prazo, lei e valor de verdade,
                   e ao bloco "Fontes" URLs que o modelo realmente leu —
                   nunca referencia inventada.
"""
from __future__ import annotations

from .config import env

# Sonnet: rapido e barato o bastante para volume diario, bom o bastante para
# reescrever uma nota curta. Trocar por claude-opus-5 aqui se quiser mais
# qualidade a mais custo.
MODELO_LLM = "claude-sonnet-5"

# Busca na web da API (US$ 10 por 1.000 buscas + tokens das paginas lidas).
# Versao com filtragem dinamica; `allowed_callers: direct` chama a busca
# direto, sem o ambiente de execucao de codigo — mais simples e mais barato
# para "ache o prazo no site oficial".
FERRAMENTA_BUSCA = "web_search_20260209"
MAX_BUSCAS_PADRAO = 3
# pause_turn: a API pausa um turno longo de busca e pede para reenviar.
MAX_CONTINUACOES = 3

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


def _cliente():
    """Cliente da API, ou None (sem chave = modo sem LLM, por desenho)."""
    chave = env("ANTHROPIC_API_KEY")
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    # Chave vinculada a workspace exige o id do workspace no header; chave
    # de conta comum ignora. Passar so' quando existir cobre os dois casos.
    cabecalhos = {}
    ws = env("ANTHROPIC_WORKSPACE_ID")
    if ws:
        cabecalhos["anthropic-workspace-id"] = ws
    return anthropic.Anthropic(api_key=chave, default_headers=cabecalhos or None)


def _chama(cliente, **kwargs):
    """messages.create com a falha registrada. Devolve a resposta ou None."""
    import anthropic
    try:
        return cliente.messages.create(**kwargs)
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


def _texto_e_citacoes(blocos) -> tuple[str, list[dict]]:
    """Junta os blocos de texto (ignora thinking, busca e resultados) e
    recolhe as citacoes de busca: [{url, titulo}], sem repetir URL, na ordem
    em que apareceram. Erro de busca (vem com HTTP 200, dentro do resultado)
    e' registrado como falha, mas o texto segue."""
    partes: list[str] = []
    citacoes: list[dict] = []
    vistas: set[str] = set()
    for b in blocos:
        tipo = getattr(b, "type", None)
        if tipo == "text":
            partes.append(getattr(b, "text", "") or "")
            for c in getattr(b, "citations", None) or []:
                url = getattr(c, "url", None)
                if not url:
                    continue
                chave = url.rstrip("/")
                if chave in vistas:
                    continue
                vistas.add(chave)
                citacoes.append({"url": url,
                                 "titulo": (getattr(c, "title", None) or url).strip()})
        elif tipo == "web_search_tool_result":
            conteudo = getattr(b, "content", None)
            codigo = getattr(conteudo, "error_code", None)
            if codigo:
                _registra_falha(f"busca na web falhou: {codigo}")
    return "".join(partes).strip(), citacoes


def gera(prompt: str, sistema: str | None = None, max_tokens: int = 1000) -> str | None:
    """Texto do Claude, ou None se nao der (sem chave, sem SDK, ou erro).

    Sem chave e sem SDK NAO e' falha — e' o modo sem LLM, por desenho.
    Erro da API e' falha: fica registrado (ver `resumo_falhas`)."""
    cliente = _cliente()
    if cliente is None:
        return None
    kwargs = {"model": MODELO_LLM, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if sistema:
        kwargs["system"] = sistema
    r = _chama(cliente, **kwargs)
    if r is None:
        return None
    if getattr(r, "stop_reason", None) == "refusal":
        _registra_falha("modelo recusou o pedido (stop_reason=refusal)")
        return None
    texto, _ = _texto_e_citacoes(r.content)
    return texto or None


def gera_com_busca(prompt: str, dominios: list[str], sistema: str | None = None,
                   max_tokens: int = 6000,
                   max_buscas: int = MAX_BUSCAS_PADRAO) -> tuple[str | None, list[dict]]:
    """Texto do Claude escrito COM busca na web restrita a `dominios`, e as
    citacoes [{url, titulo}] das paginas que ele de fato usou.

    Devolve (None, []) nos mesmos casos de `gera`. Sem dominios, cai em
    `gera` (nao existe busca "aberta" aqui: fonte ou e' oficial ou nao entra).
    Resolve `pause_turn` reenviando a resposta, ate MAX_CONTINUACOES vezes."""
    dominios = [d for d in (dominios or []) if d]
    if not dominios:
        return gera(prompt, sistema=sistema, max_tokens=max_tokens), []
    cliente = _cliente()
    if cliente is None:
        return None, []

    ferramenta = {
        "type": FERRAMENTA_BUSCA, "name": "web_search",
        "max_uses": max_buscas,
        "allowed_domains": dominios,
        "allowed_callers": ["direct"],
        "user_location": {"type": "approximate", "country": "BR",
                          "timezone": "America/Sao_Paulo"},
    }
    mensagens = [{"role": "user", "content": prompt}]
    kwargs = {"model": MODELO_LLM, "max_tokens": max_tokens,
              "tools": [ferramenta], "messages": mensagens}
    if sistema:
        kwargs["system"] = sistema

    r = None
    for _ in range(MAX_CONTINUACOES + 1):
        r = _chama(cliente, **kwargs)
        if r is None:
            return None, []
        if getattr(r, "stop_reason", None) != "pause_turn":
            break
        # A API pausou o turno de busca: reenvia a resposta como veio, sem
        # mensagem extra, e ela retoma de onde parou.
        kwargs["messages"] = mensagens + [{"role": "assistant", "content": r.content}]

    if getattr(r, "stop_reason", None) == "refusal":
        _registra_falha("modelo recusou o pedido (stop_reason=refusal)")
        return None, []
    if getattr(r, "stop_reason", None) == "pause_turn":
        _registra_falha("busca na web nao terminou (pause_turn repetido)")
        return None, []

    texto, citacoes = _texto_e_citacoes(r.content)
    uso = getattr(getattr(r, "usage", None), "server_tool_use", None)
    buscas = getattr(uso, "web_search_requests", None)
    if buscas is not None:
        print(f"  [busca] {buscas} busca(s), {len(citacoes)} fonte(s) citada(s)")
    return (texto or None), citacoes
