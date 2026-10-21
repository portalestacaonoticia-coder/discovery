"""Ponte unica com a OpenAI (gpt-5.6-luna). Melhoria, nunca dependencia: sem
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

Modo local (16/10/2026): com LLM_LOCAL_URL no ambiente, o TEXTO sai do
modelo que roda nos Macs (exo, API compativel com a OpenAI em
/v1/chat/completions) e nao da' OpenAI — custo zero por chamada. A busca
vira codigo: SearXNG + leitura das paginas (radar/busca_local.py). So' a
imagem (gera_imagem) continua na OpenAI, e so' se houver OPENAI_API_KEY.

Duas portas:
  gera()           texto puro, sem ferramenta.
  gera_com_busca() texto + CITACOES, com a busca na web da propria API
                   restrita a uma lista de dominios (as fontes oficiais do
                   hub). E' o que da' ao guia prazo, lei e valor de verdade,
                   e ao bloco "Fontes" URLs que o modelo realmente leu —
                   nunca referencia inventada.
"""
from __future__ import annotations

import json
import re

import requests

from .config import env

# Modelo unico de geracao de artigos. Trocar aqui muda todas as esteiras.
MODELO_LLM = "gpt-5.6-luna"
# Classificacao de pauta: tarefa curta, JSON de 300 tokens por noticia nova.
# Mesmo modelo por padrao; se o volume pesar no custo, troque so' este.
MODELO_CLASSIFICA = MODELO_LLM

URL_API = "https://api.openai.com/v1/responses"
URL_IMAGENS = "https://api.openai.com/v1/images/generations"
TIMEOUT_S = 180
# Imagem destacada gerada por IA (radar/discover.py). 1536x1024 e' o maior
# formato paisagem da API e passa com folga no minimo do Discover (1200px).
MODELO_IMAGEM = "gpt-image-1"
TAMANHO_IMAGEM = "1536x1024"

# Busca na web da API (cobrada por chamada de busca + tokens das paginas
# lidas). A API nao tem teto de buscas por pedido: o limite vai no prompt
# (gerador_artigo.py cita MAX_BUSCAS_PADRAO) e o total feito sai no log.
MAX_BUSCAS_PADRAO = 3
# `filters.allowed_domains` aceita no maximo 20 dominios por pedido.
MAX_DOMINIOS = 20

# Modo local. O exo nao cobra por chamada; o preco e' o TEMPO (14,7 tok/s
# no Qwen3.8-27B em dois Macs, 16/10/2026), por isso o prazo e' longo.
MODELO_LOCAL_PADRAO = "mlx-community/Qwen3.8-27B-8bit"
TIMEOUT_LOCAL_S = 1200
# O Qwen pensa antes de responder, e o pensamento conta no max_tokens. Sem
# folga, a classificacao (300 tokens) seria cortada no meio do raciocinio.
FOLGA_RACIOCINIO = 4000

# Falhas da rodada, na ordem. Cada mensagem distinta e' impressa UMA vez
# (um 429 em 80 itens nao vira 80 linhas de log) mas contada todas.
_falhas: list[str] = []
_impressas: set[str] = set()


def modo_local() -> bool:
    return bool(env("LLM_LOCAL_URL"))


def tem_chave() -> bool:
    """Ha' modelo de texto disponivel? (OpenAI com chave, ou o local.)"""
    return modo_local() or bool(env("OPENAI_API_KEY"))


def _registra_falha(mensagem: str) -> None:
    _falhas.append(mensagem)
    # O request-id muda a cada chamada; sem tira-lo da chave, o mesmo 429
    # sairia uma vez por pauta (foram 40 linhas iguais na rodada de 28/09).
    chave = mensagem.split(" (request ")[0]
    if chave not in _impressas:
        _impressas.add(chave)
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


def tira_raciocinio(texto: str) -> str:
    """Remove o pensamento do Qwen (<think>...</think>). O template do modelo
    as vezes abre o <think> no proprio prompt, e a resposta traz so' o fecho:
    nesse caso vale o que vem depois do ultimo </think>."""
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    if "</think>" in texto:
        texto = texto.rsplit("</think>", 1)[1]
    return texto.strip()


def _guarda_resposta(texto: str) -> str:
    """Salva a resposta que nao virou JSON em saida/llm-falhas/ para ver o
    porque (a falha e' intermitente: 2 de 8 guias em 20/10/2026, e a mesma
    chamada repetida saiu valida). Devolve o sufixo para o log."""
    try:
        from datetime import datetime
        from .config import RAIZ
        pasta = RAIZ / "saida" / "llm-falhas"
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / f"{datetime.now():%Y%m%d-%H%M%S-%f}.txt"
        arquivo.write_text(texto or "", encoding="utf-8")
        return f" (resposta em saida/llm-falhas/{arquivo.name})"
    except OSError:
        return ""


def extrai_json(texto: str) -> str | None:
    """O objeto JSON de uma resposta que pode vir com texto em volta ou
    dentro de ```json```. Devolve o JSON como texto, ou None se nao houver
    um objeto valido."""
    inicio, fim = (texto or "").find("{"), (texto or "").rfind("}")
    if inicio < 0 or fim <= inicio:
        return None
    bruto = texto[inicio:fim + 1]
    try:
        # strict=False aceita quebra de linha crua dentro das strings (o Qwen
        # faz isso no corpo do guia); devolve re-serializado, entao quem
        # chama pode fazer json.loads normal.
        return json.dumps(json.loads(bruto, strict=False), ensure_ascii=False)
    except json.JSONDecodeError:
        return None


def _gera_local(prompt: str, sistema: str | None, max_tokens: int,
                json_obj: bool) -> str | None:
    """Chama o exo e, se a resposta vier VAZIA (sem erro, sem texto), tenta
    de novo uma vez. Em 20-21/10/2026 o exo devolveu conteudo vazio 4 vezes
    (duas rodadas pedindo texto ao mesmo tempo) e o satelite caia no template
    sem nenhuma falha registrada."""
    global _ultima_vazia
    for _ in range(2):
        _ultima_vazia = False
        texto = _gera_local_1x(prompt, sistema, max_tokens, json_obj)
        if texto or not _ultima_vazia:
            return texto
    _registra_falha("local: o exo devolveu resposta vazia (2x)")
    return None


_ultima_vazia = False


def _gera_local_1x(prompt: str, sistema: str | None, max_tokens: int,
                   json_obj: bool) -> str | None:
    """Uma chamada ao exo (/v1/chat/completions). Mesmo contrato de `gera`:
    texto ou None, com a falha registrada."""
    base = (env("LLM_LOCAL_URL") or "").rstrip("/")
    instrucoes = (sistema or "").strip()
    if json_obj:
        # O exo nao garante JSON como a OpenAI; quem garante e' extrai_json.
        instrucoes = (instrucoes + "\n\nResponda SOMENTE com um objeto JSON "
                      "valido, sem nenhum texto antes ou depois.").strip()
    mensagens = [{"role": "system", "content": instrucoes}] if instrucoes else []
    mensagens.append({"role": "user", "content": prompt})
    folga = int(env("LLM_LOCAL_FOLGA") or FOLGA_RACIOCINIO)
    corpo = {"model": env("LLM_LOCAL_MODELO") or MODELO_LOCAL_PADRAO,
             "messages": mensagens, "max_tokens": max_tokens + folga,
             "temperature": 0.6, "stream": False}
    # Ensaio de 19/10/2026: com o pensamento ligado o Qwen as vezes nao para
    # de raciocinar e estoura o max_tokens (14 min e TEMPLATE). Desligado por
    # padrao; LLM_LOCAL_RACIOCINIO=1 religa.
    if (env("LLM_LOCAL_RACIOCINIO") or "") != "1":
        corpo["enable_thinking"] = False
    try:
        r = requests.post(f"{base}/chat/completions", json=corpo,
                          timeout=int(env("LLM_LOCAL_TIMEOUT") or TIMEOUT_LOCAL_S))
    except requests.RequestException as erro:
        _registra_falha(f"local: sem conexao com o exo em {base}: {erro}")
        return None
    if not r.ok:
        _registra_falha(f"local: HTTP {r.status_code} {(r.text or '').strip()[:200]}")
        return None
    try:
        escolha = r.json()["choices"][0]
        texto = escolha["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        _registra_falha("local: resposta do exo sem 'choices'")
        return None
    if escolha.get("finish_reason") == "length":
        # Cortado no teto: JSON pela metade nao serve (mesma regra do
        # status=incomplete da OpenAI).
        _registra_falha("local: resposta incompleta (max_tokens)")
        return None
    texto = tira_raciocinio(texto)
    if not texto.strip():
        global _ultima_vazia
        _ultima_vazia = True
        return None
    if json_obj:
        bruto = extrai_json(texto)
        if bruto is None:
            _registra_falha("local: modelo nao devolveu JSON valido"
                            + _guarda_resposta(texto))
            return None
        texto = bruto
    return texto or None


def gera(prompt: str, sistema: str | None = None, max_tokens: int = 1000,
         modelo: str | None = None, json_obj: bool = False) -> str | None:
    """Texto do modelo, ou None se nao der (sem chave, erro de API, vazio).

    json_obj=True pede a resposta em modo JSON (a API garante um objeto
    valido). Sem chave NAO e' falha — e' o modo sem LLM, por desenho. Erro da
    API e' falha: fica registrado (ver `resumo_falhas`)."""
    if modo_local():
        # `modelo` e' nome de modelo da OpenAI: no local vale LLM_LOCAL_MODELO.
        return _gera_local(prompt, sistema, max_tokens, json_obj)
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
    if modo_local():
        return _gera_com_busca_local(prompt, dominios, sistema, max_tokens, max_buscas)
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


def _consultas_locais(prompt: str, max_buscas: int) -> list[str]:
    """O modelo local escreve as consultas; se falhar, a primeira linha do
    pedido (sem o rotulo "Ideia:") vira a consulta."""
    pedido = ("Voce vai pesquisar na web para atender o pedido abaixo. Escreva "
              f"ate' {max_buscas} consultas de busca curtas (3 a 8 palavras), "
              "objetivas, no idioma das fontes. Responda SO um JSON: "
              '{"consultas": ["..."]}\n\nPEDIDO:\n' + prompt[:4000])
    consultas: list[str] = []
    saida = _gera_local(pedido, None, 300, True)
    if saida:
        lido = json.loads(saida)
        bruto = lido.get("consultas") if isinstance(lido, dict) else None
        consultas = [str(c).strip() for c in (bruto or []) if str(c).strip()]
    if not consultas:
        linha = next((l for l in prompt.splitlines() if l.strip()), "")
        consultas = [re.sub(r"^\s*[\w ]{1,20}:\s*", "", linha).strip()[:120]]
    return [c for c in consultas if c][:max_buscas]


def _gera_com_busca_local(prompt: str, dominios: list[str], sistema: str | None,
                          max_tokens: int, max_buscas: int) -> tuple[str | None, list[dict]]:
    """gera_com_busca no Mac: o codigo busca e le, o modelo so' escreve.

    Sem pagina lida, NAO escreve: de memoria o modelo local inventa numero.
    As citacoes levam o `texto` lido, para a pesquisa conferir o valor."""
    from . import busca_local
    if not busca_local.ligada():
        _registra_falha("local: sem SEARXNG_URL, nao ha' como ler as fontes")
        return None, []
    consultas = _consultas_locais(prompt, max_buscas)
    paginas = busca_local.busca_e_le(consultas, dominios)
    print(f"  [busca local] {len(consultas)} busca(s), {len(paginas)} pagina(s) lida(s)")
    if not paginas:
        return None, []
    material = "\n\n".join(f"[{i}] {p['titulo']}\nURL: {p['url']}\n{p['texto']}"
                            for i, p in enumerate(paginas, 1))
    instrucoes = ((sistema or "").strip() + "\n\nNesta execucao a busca JA' FOI FEITA: "
                  "as paginas lidas estao no pedido. Use so' o que esta' nelas, e "
                  "toda URL citada tem de ser uma delas, copiada exatamente.").strip()
    texto = _gera_local(f"{prompt}\n\n=== PAGINAS LIDAS ===\n{material}\n=== FIM ===",
                        instrucoes, max_tokens, False)
    if not texto:
        return None, []
    citadas = [p for p in paginas if p["url"].rstrip("/") in texto]
    # Nenhuma URL no texto: as paginas lidas sao, ainda assim, onde conferir.
    return texto, (citadas or paginas)


def gera_imagem(prompt: str, tamanho: str = TAMANHO_IMAGEM,
                qualidade: str = "medium") -> bytes | None:
    """Bytes JPEG de uma imagem gerada (Images API), ou None. Mesmo registro
    de falhas das chamadas de texto. Sem chave NAO e' falha."""
    import base64
    chave = env("OPENAI_API_KEY")
    if not chave:
        return None
    cabecalhos = {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
    org = env("OPENAI_ORG_ID")
    if org:
        cabecalhos["OpenAI-Organization"] = org
    corpo = {"model": MODELO_IMAGEM, "prompt": prompt[:4000], "n": 1,
             "size": tamanho, "quality": qualidade, "output_format": "jpeg"}
    try:
        r = requests.post(URL_IMAGENS, json=corpo, headers=cabecalhos, timeout=TIMEOUT_S)
    except requests.RequestException as erro:
        _registra_falha(f"imagem: sem conexao com a API: {erro}")
        return None
    try:
        dados = r.json()
    except ValueError:
        dados = None
    if not r.ok:
        detalhe = dados.get("error") if isinstance(dados, dict) else None
        msg = (detalhe.get("message") if isinstance(detalhe, dict) else None) or (r.text or "")[:160]
        _registra_falha(f"imagem: HTTP {r.status_code} {msg}")
        return None
    try:
        b64 = (dados.get("data") or [{}])[0].get("b64_json")
        return base64.b64decode(b64) if b64 else None
    except Exception as erro:  # noqa: BLE001
        _registra_falha(f"imagem: resposta inesperada: {erro}")
        return None
