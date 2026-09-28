"""Ponte unica com a OpenAI (gpt-6-luna). Melhoria, nunca dependencia: sem
chave, devolve None e quem chama cai no seu proprio fallback.

Toda chamada ao modelo passa por aqui — classificacao, satelites, guias,
reserva. Um lugar so' para trocar de modelo e para VER as falhas: o erro da
API nao e' engolido em silencio, ele vai para o log da rodada (stdout do
Actions) e para o resumo gravado em `execucoes`, via `resumo_falhas()`.
Antes de 26/09/2026 uma chave vencida ou um credito esgotado so' aparecia
como "post nao saiu", sem motivo.

Uma chave so', OPENAI_API_KEY. Fala com a API direto via requests (ja' e'
dependencia do projeto) — sem SDK extra para instalar. Usa a Responses API
(/v1/responses), que e' onde vive a busca na web da propria OpenAI.

Duas portas:
  gera()           texto puro, sem ferramenta.
  gera_com_busca() texto + CITACOES, com a busca na web da propria API
                   restrita a uma lista de dominios (as fontes oficiais do
                   hub). E' o que da' ao guia prazo, lei e valor de verdade,
                   e ao bloco "Fontes" URLs que o modelo realmente leu —
                   nunca referencia inventada.
"""
from __future__ import annotations

import requests

from .config import env

# Modelo unico de geracao de artigos. Trocar aqui muda todas as esteiras.
MODELO_LLM = "gpt-6-luna"
# Classificacao de pauta: tarefa curta, JSON de 300 tokens por noticia nova.
# Mesmo modelo por padrao; se o volume pesar no custo, troque so' este.
MODELO_CLASSIFICA = MODELO_LLM

URL_API = "https://api.openai.com/v1/responses"
TIMEOUT_S = 180

# Busca na web da API (cobrada por chamada de busca + tokens das paginas
# lidas). A API nao tem teto de buscas por pedido: o limite vai no prompt
# (gerador_artigo.py cita MAX_BUSCAS_PADRAO) e o total feito sai no log.
MAX_BUSCAS_PADRAO = 3
# `filters.allowed_domains` aceita no maximo 20 dominios por pedido.
MAX_DOMINIOS = 20

# Falhas da rodada, na ordem. Cada mensagem distinta e' impressa UMA vez
# (um 429 em 80 itens nao vira 80 linhas de log) mas contada todas.
_falhas: list[str] = []
_impressas: set[str] = set()


def tem_chave() -> bool:
    return bool(env("OPENAI_API_KEY"))


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
    Ex.: ' | LLM: 3 falha(s): HTTP 429 rate_limit_exceeded ...'"""
    if not _falhas:
        return ""
    return f" | LLM: {len(_falhas)} falha(s): {_falhas[-1][:160]}"


def limpa_falhas() -> None:
    _falhas.clear()
    _impressas.clear()


def _corpo(prompt: str, sistema: str | None, max_tokens: int,
           modelo: str | None, json_obj: bool) -> dict:
    corpo = {
        "model": modelo or MODELO_LLM,
        "input": prompt,
        "max_output_tokens": max_tokens,
    }
    if sistema:
        corpo["instructions"] = sistema
    if json_obj:
        # Modo JSON: a API garante um objeto valido. O prompt precisa conter
        # a palavra "JSON", exigencia da propria API.
        corpo["text"] = {"format": {"type": "json_object"}}
    return corpo


def _chama(corpo: dict) -> dict | None:
    """POST /v1/responses com a falha registrada. Devolve a resposta (dict)
    ou None. Sem chave NAO e' falha — e' o modo sem LLM, por desenho."""
    chave = env("OPENAI_API_KEY")
    if not chave:
        return None
    cabecalhos = {"Authorization": f"Bearer {chave}",
                  "Content-Type": "application/json"}
    org = env("OPENAI_ORG_ID")
    if org:
        cabecalhos["OpenAI-Organization"] = org
    try:
        r = requests.post(URL_API, json=corpo, headers=cabecalhos,
                          timeout=TIMEOUT_S)
    except requests.RequestException as erro:
        _registra_falha(f"sem conexao com a API: {erro}")
        return None
    except Exception as erro:  # noqa: BLE001 — melhoria, nunca dependencia
        _registra_falha(f"{type(erro).__name__}: {erro}")
        return None

    req = r.headers.get("x-request-id") or ""
    try:
        dados = r.json()
    except ValueError:
        dados = None
    if not r.ok:
        # 401 chave, 403 permissao, 429 limite/credito, 400 pedido, 5xx
        # servidor: o codigo + tipo dizem o que fazer; o request-id serve
        # para o suporte.
        detalhe = dados.get("error") if isinstance(dados, dict) else None
        if isinstance(detalhe, dict):
            rotulo = detalhe.get("code") or detalhe.get("type") or ""
            texto = f"{rotulo}: {detalhe.get('message') or ''}".strip(": ")
        else:
            texto = (r.text or "").strip()[:200]
        _registra_falha(f"HTTP {r.status_code} {texto}"
                        + (f" (request {req})" if req else ""))
        return None
    if not isinstance(dados, dict):
        _registra_falha("resposta da API sem JSON")
        return None
    erro = dados.get("error")
    if erro:
        # status=failed vem com HTTP 200 e o erro dentro do corpo.
        msg = erro.get("message") if isinstance(erro, dict) else str(erro)
        _registra_falha(f"pedido falhou: {msg}")
        return None
    if dados.get("status") == "incomplete":
        # Cortado no max_output_tokens (ou filtro de conteudo): o JSON do
        # artigo vem pela metade e nao serve. Melhor registrar e nao usar.
        motivo = (dados.get("incomplete_details") or {}).get("reason") or "?"
        _registra_falha(f"resposta incompleta ({motivo})")
        return None
    return dados


def _texto_e_citacoes(saida) -> tuple[str, list[dict], int]:
    """Junta o texto das mensagens (ignora raciocinio e chamadas de busca),
    recolhe as citacoes [{url, titulo}] sem repetir URL, na ordem em que
    apareceram, e conta as buscas feitas. Recusa do modelo e busca que falhou
    (vem com HTTP 200, dentro da saida) sao registradas como falha."""
    partes: list[str] = []
    citacoes: list[dict] = []
    vistas: set[str] = set()
    buscas = 0
    for item in saida or []:
        if not isinstance(item, dict):
            continue
        tipo = item.get("type")
        if tipo == "message":
            for c in item.get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "output_text":
                    partes.append(c.get("text") or "")
                    for a in c.get("annotations") or []:
                        if not isinstance(a, dict) or a.get("type") != "url_citation":
                            continue
                        url = (a.get("url") or "").strip()
                        if not url:
                            continue
                        chave = url.rstrip("/")
                        if chave in vistas:
                            continue
                        vistas.add(chave)
                        citacoes.append({"url": url,
                                         "titulo": (a.get("title") or url).strip()})
                elif c.get("type") == "refusal":
                    _registra_falha("modelo recusou o pedido: "
                                    f"{(c.get('refusal') or '')[:120]}")
        elif tipo == "web_search_call":
            buscas += 1
            if item.get("status") == "failed":
                _registra_falha("busca na web falhou")
    return "".join(partes).strip(), citacoes, buscas


def gera(prompt: str, sistema: str | None = None, max_tokens: int = 1000,
         modelo: str | None = None, json_obj: bool = False) -> str | None:
    """Texto do modelo, ou None se nao der (sem chave, erro de API, vazio).

    json_obj=True pede a resposta em modo JSON (a API garante um objeto
    valido). Sem chave NAO e' falha — e' o modo sem LLM, por desenho. Erro da
    API e' falha: fica registrado (ver `resumo_falhas`)."""
    if not tem_chave():
        return None
    dados = _chama(_corpo(prompt, sistema, max_tokens, modelo, json_obj))
    if dados is None:
        return None
    texto, _, _ = _texto_e_citacoes(dados.get("output"))
    return texto or None


def gera_com_busca(prompt: str, dominios: list[str], sistema: str | None = None,
                   max_tokens: int = 6000,
                   max_buscas: int = MAX_BUSCAS_PADRAO) -> tuple[str | None, list[dict]]:
    """Texto do modelo escrito COM busca na web restrita a `dominios`, e as
    citacoes [{url, titulo}] das paginas que ele de fato usou.

    Devolve (None, []) nos mesmos casos de `gera`. Sem dominios, cai em
    `gera` (nao existe busca "aberta" aqui: fonte ou e' oficial ou nao entra).
    `max_buscas` e' orientacao ao modelo (vai no prompt de quem chama); a API
    nao impoe teto, entao o numero real de buscas sai no log."""
    dominios = [d for d in (dominios or []) if d][:MAX_DOMINIOS]
    if not dominios:
        return gera(prompt, sistema=sistema, max_tokens=max_tokens), []
    if not tem_chave():
        return None, []

    corpo = _corpo(prompt, sistema, max_tokens, None, False)
    corpo["tools"] = [{
        "type": "web_search",
        "filters": {"allowed_domains": dominios},
        "user_location": {"type": "approximate", "country": "BR",
                          "timezone": "America/Sao_Paulo"},
    }]
    corpo["tool_choice"] = "auto"
    dados = _chama(corpo)
    if dados is None:
        return None, []

    texto, citacoes, buscas = _texto_e_citacoes(dados.get("output"))
    if buscas:
        print(f"  [busca] {buscas} busca(s), {len(citacoes)} fonte(s) citada(s)")
        if buscas > max_buscas:
            print(f"  [busca] passou do teto sugerido de {max_buscas}")
    return (texto or None), citacoes
