"""Fontes de sinal do motor Discover: o que esta' em alta, o que as pessoas
perguntam e o que os outros ja' publicaram sobre cada hub.

Cada coletor devolve uma lista de SINAL, sempre no mesmo formato:

    {"site", "hub", "fonte", "tipo", "texto", "url", "veiculo", "valor",
     "extra", "publicado_em" (ISO ou None), "dia", "hash_dedup"}

    fonte: google_news_rss | serp | trends | reddit | youtube | tiktok
    tipo : noticia | organico | paa | relacionada | trend_rising | trend_top | social
    valor: trends = alta em % (Breakout = 1000); social = upvotes/views

Regra do projeto, mantida: aqui entra TITULO, URL, data e snippet. Nunca o
texto integral de outro site.

Custo: SerpAPI e YouTube sao pagos/cotados. `coleta_sinais` consulta a tabela
`coletas` e so' chama a fonte quando o TTL dela venceu (TTL_HORAS). Fora do
periodo de producao do site (metas.producao_inicio/fim) as fontes pagas nao
sao chamadas — so' o RSS gratis, para o historico de topicos nao morrer.

Falhas nao derrubam a rodada: ficam registradas (mesmo padrao de llm.py) e
saem no resumo de `execucoes`.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone

import requests

from . import fontes
from .config import env
from .normaliza import hash_dedup, veiculo_de

URL_SERPAPI = "https://serpapi.com/search.json"
URL_REDDIT_TOKEN = "https://www.reddit.com/api/v1/access_token"
URL_REDDIT = "https://oauth.reddit.com"
URL_YOUTUBE = "https://www.googleapis.com/youtube/v3"
TIMEOUT_S = 30
CABECALHO = {"User-Agent": "RadarPautas/1.0 (+contato@exemplo.com.br)"}

# Quanto tempo uma coleta vale antes de a fonte ser consultada de novo.
TTL_HORAS = {"google_news_rss": 0.5, "serp": 24, "trends": 24,
             "reddit": 6, "youtube": 24, "tiktok": 24}
# Fontes que contam no teto diario da SerpAPI.
PAGAS = {"serp", "trends"}
TETO_SERPAPI_DIA_PADRAO = 250
BREAKOUT = 1000   # o Trends nao da' numero para "Breakout": alta acima de 5000%

# Falhas da rodada, uma impressao por mensagem distinta (padrao do llm.py).
_falhas: list[str] = []
_impressas: set[str] = set()


class ErroSinal(Exception):
    pass


def _registra_falha(mensagem: str) -> None:
    _falhas.append(mensagem)
    if mensagem not in _impressas:
        _impressas.add(mensagem)
        print(f"  [sinais] {mensagem}")


def falhas() -> list[str]:
    return list(_falhas)


def resumo_falhas() -> str:
    if not _falhas:
        return ""
    return f" | sinais: {len(_falhas)} falha(s): {_falhas[-1][:120]}"


def limpa_falhas() -> None:
    _falhas.clear()
    _impressas.clear()


def tem_serpapi() -> bool:
    return bool(env("SERPAPI_KEY"))


# -- formato ------------------------------------------------------------------

def _sinal(site: str, hub: str, fonte: str, tipo: str, texto: str, *,
           url: str | None = None, veiculo: str | None = None,
           valor: float | None = None, extra: dict | None = None,
           publicado_em: datetime | None = None,
           agora: datetime | None = None) -> dict:
    texto = " ".join((texto or "").split())
    agora = agora or datetime.now(timezone.utc)
    quando = publicado_em or agora
    return {
        "site": site, "hub": hub, "fonte": fonte, "tipo": tipo,
        "texto": texto[:300], "url": url, "veiculo": veiculo, "valor": valor,
        "extra": extra or None,
        "publicado_em": publicado_em.isoformat() if publicado_em else None,
        "dia": quando.date().isoformat(),
        # Manchete com data usa o mesmo hash da coleta antiga (titulo + dia);
        # pergunta e query nao tem data: hash so' do texto.
        "hash_dedup": hash_dedup(texto, publicado_em),
    }


def _manchete_limpa(titulo: str) -> tuple[str, str]:
    """O RSS do Google News cola ' - Veiculo' no fim do titulo. Devolve
    (manchete, veiculo)."""
    t = (titulo or "").strip()
    if " - " in t:
        manchete, veiculo = t.rsplit(" - ", 1)
        return manchete.strip(), veiculo.strip()
    return t, ""


# -- SerpAPI ------------------------------------------------------------------

def _serpapi(params: dict) -> dict:
    chave = env("SERPAPI_KEY")
    if not chave:
        raise ErroSinal("sem SERPAPI_KEY")
    try:
        r = requests.get(URL_SERPAPI, params={**params, "api_key": chave},
                         headers=CABECALHO, timeout=TIMEOUT_S)
    except requests.RequestException as erro:
        raise ErroSinal(f"SerpAPI sem conexao: {erro}") from erro
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if not r.ok:
        msg = (dados.get("error") if isinstance(dados, dict) else None) or r.text[:120]
        raise ErroSinal(f"SerpAPI HTTP {r.status_code} ({params.get('engine')}): {msg}")
    if isinstance(dados, dict) and dados.get("error"):
        raise ErroSinal(f"SerpAPI ({params.get('engine')}): {dados['error']}")
    return dados if isinstance(dados, dict) else {}


def coleta_serp(site: str, hub: str, consulta: str, geo: str = "BR",
                hl: str = "pt-BR", agora: datetime | None = None) -> list[dict]:
    """Engine `google`: os 10 organicos (titulo, link, snippet), as perguntas
    do People Also Ask e as buscas relacionadas. Uma chamada, tres tipos de
    sinal. Porta o `serpRelated` do conteudo.tihee."""
    dados = _serpapi({"engine": "google", "q": consulta, "num": 10,
                      "gl": geo.lower(), "hl": hl.lower(),
                      "google_domain": "google.com.br" if geo.upper() == "BR" else "google.com"})
    saida = []
    for r in (dados.get("organic_results") or [])[:10]:
        titulo, link = r.get("title"), r.get("link")
        if not titulo or not link:
            continue
        saida.append(_sinal(site, hub, "serp", "organico", titulo, url=link,
                            veiculo=veiculo_de(link),
                            extra={"snippet": (r.get("snippet") or "")[:300],
                                   "data": r.get("date"), "posicao": r.get("position"),
                                   "consulta": consulta}, agora=agora))
    for p in (dados.get("related_questions") or []):
        pergunta = p.get("question")
        if pergunta:
            saida.append(_sinal(site, hub, "serp", "paa", pergunta, url=p.get("link"),
                                extra={"snippet": (p.get("snippet") or "")[:300],
                                       "consulta": consulta}, agora=agora))
    for s in (dados.get("related_searches") or []):
        q = s.get("query")
        if q:
            saida.append(_sinal(site, hub, "serp", "relacionada", q,
                                extra={"consulta": consulta}, agora=agora))
    return saida


def _valor_trend(item: dict) -> float:
    """`value` vem como "Breakout", "+1,250%" ou 87; `extracted_value` e' o
    numero quando existe."""
    v = item.get("extracted_value")
    if isinstance(v, (int, float)):
        return float(v)
    bruto = str(item.get("value") or "").strip()
    if bruto.lower() == "breakout":
        return float(BREAKOUT)
    digitos = "".join(c for c in bruto if c.isdigit())
    return float(digitos) if digitos else 0.0


def coleta_trends(site: str, hub: str, termo: str, geo: str = "BR",
                  hl: str = "pt-BR", agora: datetime | None = None) -> list[dict]:
    """Engine `google_trends`, RELATED_QUERIES: o que esta' subindo (rising)
    e o que e' mais buscado (top) em torno do termo. Porta o `serpTrends`."""
    dados = _serpapi({"engine": "google_trends", "q": termo,
                      "data_type": "RELATED_QUERIES", "geo": geo.upper(),
                      "hl": hl.lower()})
    bloco = dados.get("related_queries") or {}
    saida = []
    for item in (bloco.get("rising") or []):
        q = item.get("query")
        if q:
            saida.append(_sinal(site, hub, "trends", "trend_rising", q,
                                url=item.get("link"), valor=_valor_trend(item),
                                extra={"termo": termo, "valor_bruto": item.get("value")},
                                agora=agora))
    for item in (bloco.get("top") or []):
        q = item.get("query")
        if q:
            saida.append(_sinal(site, hub, "trends", "trend_top", q,
                                url=item.get("link"), valor=_valor_trend(item),
                                extra={"termo": termo}, agora=agora))
    return saida


def coleta_noticias_serpapi(site: str, hub: str, consulta: str, geo: str = "BR",
                            hl: str = "pt-BR", agora: datetime | None = None) -> list[dict]:
    """Engine `google_news` da SerpAPI (opcional: sinais.noticias_via_serpapi).
    O RSS gratis cobre o mesmo; isto e' para quando o RSS falhar."""
    dados = _serpapi({"engine": "google_news", "q": consulta,
                      "gl": geo.lower(), "hl": hl.lower()})
    itens = list(dados.get("news_results") or [])
    for bloco in (dados.get("stories") or []):
        itens.extend(bloco.get("stories") or [])
    saida = []
    for n in itens[:20]:
        titulo, link = n.get("title"), n.get("link")
        if not titulo or not link:
            continue
        fonte = n.get("source") or {}
        saida.append(_sinal(site, hub, "serp", "noticia", titulo, url=link,
                            veiculo=(fonte.get("name") if isinstance(fonte, dict) else None)
                            or veiculo_de(link),
                            extra={"data": n.get("date"), "consulta": consulta},
                            agora=agora))
    return saida


# -- Google News (RSS gratis) -------------------------------------------------

def coleta_noticias_rss(site: str, hub: str, consulta: str,
                        agora: datetime | None = None) -> list[dict]:
    """O mesmo RSS que o radar antigo le, mas por HUB: manchete, veiculo e
    data. E' a base da velocidade de noticias (quantos veiculos em 24h)."""
    saida = []
    time.sleep(fontes.PAUSA)   # educacao com o servidor, como em fontes.coleta
    for cru in fontes.coleta_google_news(consulta)[:60]:
        manchete, veiculo = _manchete_limpa(cru["titulo"])
        if not manchete:
            continue
        saida.append(_sinal(site, hub, "google_news_rss", "noticia", manchete,
                            url=cru["url"], veiculo=veiculo or veiculo_de(cru["url"]),
                            extra={"resumo": (cru.get("resumo") or "")[:200],
                                   "consulta": consulta},
                            publicado_em=cru.get("publicado_em"), agora=agora))
    return saida


# -- social -------------------------------------------------------------------

_token_reddit: dict = {}


def _reddit_token() -> str | None:
    cid, seg = env("REDDIT_CLIENT_ID"), env("REDDIT_CLIENT_SECRET")
    if not cid or not seg:
        return None
    if _token_reddit.get("ate", 0) > time.time() + 60:
        return _token_reddit["token"]
    r = requests.post(URL_REDDIT_TOKEN, auth=(cid, seg),
                      data={"grant_type": "client_credentials"},
                      headers=CABECALHO, timeout=TIMEOUT_S)
    if not r.ok:
        raise ErroSinal(f"Reddit token HTTP {r.status_code}")
    dados = r.json()
    _token_reddit.update({"token": dados.get("access_token"),
                          "ate": time.time() + int(dados.get("expires_in") or 3600)})
    return _token_reddit["token"]


def _reddit(site: str, hub: str, subreddit: str, consulta: str,
            agora: datetime | None = None) -> list[dict]:
    token = _reddit_token()
    if not token:
        raise ErroSinal("sem REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET")
    r = requests.get(f"{URL_REDDIT}/r/{subreddit}/search",
                     params={"q": consulta, "restrict_sr": 1, "sort": "new",
                             "t": "week", "limit": 25},
                     headers={**CABECALHO, "Authorization": f"Bearer {token}"},
                     timeout=TIMEOUT_S)
    if not r.ok:
        raise ErroSinal(f"Reddit r/{subreddit} HTTP {r.status_code}")
    saida = []
    for filho in (r.json().get("data") or {}).get("children") or []:
        d = filho.get("data") or {}
        titulo = d.get("title")
        if not titulo:
            continue
        quando = None
        if d.get("created_utc"):
            quando = datetime.fromtimestamp(float(d["created_utc"]), tz=timezone.utc)
        saida.append(_sinal(site, hub, "reddit", "social", titulo,
                            url=f"https://www.reddit.com{d.get('permalink') or ''}",
                            veiculo=f"r/{subreddit}", valor=float(d.get("ups") or 0),
                            extra={"comentarios": d.get("num_comments"),
                                   "consulta": consulta},
                            publicado_em=quando, agora=agora))
    return saida


def _youtube(site: str, hub: str, consulta: str,
             agora: datetime | None = None) -> list[dict]:
    chave = env("YOUTUBE_API_KEY")
    if not chave:
        raise ErroSinal("sem YOUTUBE_API_KEY")
    agora = agora or datetime.now(timezone.utc)
    desde = (agora - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(f"{URL_YOUTUBE}/search",
                     params={"part": "snippet", "type": "video", "order": "date",
                             "publishedAfter": desde, "regionCode": "BR",
                             "relevanceLanguage": "pt", "maxResults": 10,
                             "q": consulta, "key": chave},
                     headers=CABECALHO, timeout=TIMEOUT_S)
    if not r.ok:
        raise ErroSinal(f"YouTube search HTTP {r.status_code}")
    videos = {}
    for item in r.json().get("items") or []:
        vid = (item.get("id") or {}).get("videoId")
        sn = item.get("snippet") or {}
        if vid and sn.get("title"):
            videos[vid] = sn
    if not videos:
        return []
    views: dict[str, float] = {}
    r2 = requests.get(f"{URL_YOUTUBE}/videos",
                      params={"part": "statistics", "id": ",".join(videos), "key": chave},
                      headers=CABECALHO, timeout=TIMEOUT_S)
    if r2.ok:
        for item in r2.json().get("items") or []:
            views[item.get("id")] = float((item.get("statistics") or {}).get("viewCount") or 0)
    saida = []
    for vid, sn in videos.items():
        quando = None
        if sn.get("publishedAt"):
            try:
                quando = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            except ValueError:
                quando = None
        saida.append(_sinal(site, hub, "youtube", "social", sn["title"],
                            url=f"https://www.youtube.com/watch?v={vid}",
                            veiculo=sn.get("channelTitle"), valor=views.get(vid, 0.0),
                            extra={"tem_miniatura": True, "consulta": consulta},
                            publicado_em=quando, agora=agora))
    return saida


_aviso_tiktok = False


def _tiktok(site: str, hub: str, consulta: str, agora=None) -> list[dict]:
    """Sem API publica de busca. Fica o gancho para a Research API (exige
    aprovacao) ou um provedor terceiro."""
    global _aviso_tiktok
    if not _aviso_tiktok:
        _aviso_tiktok = True
        print("  [sinais] TikTok sem API publica — fonte desligada")
    return []


# -- configuracao do hub ------------------------------------------------------

def consultas_do_hub(hub: dict) -> dict[str, list[str]]:
    """O que consultar em cada fonte para este hub. `hubs[].sinais` no
    sites.yaml sobrescreve; sem ele, valem os padroes: noticias e SERP a
    partir do titulo/termos do hub, Trends com os dois primeiros termos,
    social vazio (exige app configurado)."""
    cfg = hub.get("sinais") or {}
    termos = [str(t) for t in (hub.get("termos") or [])]
    titulo = hub.get("titulo") or hub.get("id") or ""

    def lista(chave, padrao):
        v = cfg.get(chave)
        if v is None:
            return list(padrao)
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v if x]

    return {
        "noticias": lista("noticias", [" OR ".join(termos[:4]) if termos else titulo]),
        "serp": lista("serp", [titulo] if titulo else []),
        "trends": lista("trends", termos[:2]),
        "reddit": lista("reddit", []),
        "youtube": lista("youtube", []),
        "tiktok": lista("tiktok", []),
    }


def _venceu(ultima_iso: str | None, fonte: str, agora: datetime) -> bool:
    if not ultima_iso:
        return True
    ultima = datetime.fromisoformat(str(ultima_iso).replace("Z", "+00:00"))
    return (agora - ultima) >= timedelta(hours=TTL_HORAS.get(fonte, 24))


def coleta_sinais(nome: str, site: dict, hub: dict, banco, agora: datetime,
                  pagas: bool = True, leitor=None) -> list[dict]:
    """Coleta as fontes do hub cujo TTL venceu, grava e devolve os sinais
    novos. `pagas=False` (site fora do periodo de producao) pula SerpAPI,
    Trends, Reddit e YouTube — so' o RSS gratis roda.

    `leitor` e' quem responde o TTL e o teto (no ensaio --seco e' um cliente
    real so' de leitura; as gravacoes vao para `banco`, que nao grava)."""
    leitor = leitor or banco
    cfg_site = site.get("sinais") or {}
    geo = str(cfg_site.get("geo") or "BR")
    hl = str(cfg_site.get("hl") or "pt-BR")
    hub_id = hub["id"]
    consultas = consultas_do_hub(hub)
    teto = int(env("SERPAPI_TETO_DIA") or TETO_SERPAPI_DIA_PADRAO)
    inicio_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    planos: list[tuple[str, str, callable]] = []
    for c in consultas["noticias"]:
        if cfg_site.get("noticias_via_serpapi"):
            planos.append(("serp", c, lambda c=c: coleta_noticias_serpapi(nome, hub_id, c, geo, hl, agora)))
        else:
            planos.append(("google_news_rss", c, lambda c=c: coleta_noticias_rss(nome, hub_id, c, agora)))
    for c in consultas["serp"]:
        planos.append(("serp", c, lambda c=c: coleta_serp(nome, hub_id, c, geo, hl, agora)))
    for c in consultas["trends"]:
        planos.append(("trends", c, lambda c=c: coleta_trends(nome, hub_id, c, geo, hl, agora)))
    for sub in consultas["reddit"]:
        consulta = " OR ".join(str(t) for t in (hub.get("termos") or [])[:3]) or hub.get("titulo", "")
        planos.append(("reddit", f"r/{sub}: {consulta}", lambda s=sub, q=consulta: _reddit(nome, hub_id, s, q, agora)))
    for c in consultas["youtube"]:
        planos.append(("youtube", c, lambda c=c: _youtube(nome, hub_id, c, agora)))
    for c in consultas["tiktok"]:
        planos.append(("tiktok", c, lambda c=c: _tiktok(nome, hub_id, c, agora)))

    novos: list[dict] = []
    for fonte, consulta, coletor in planos:
        if fonte != "google_news_rss" and not pagas:
            continue
        if not _venceu(leitor.ultima_coleta(nome, hub_id, fonte, consulta), fonte, agora):
            continue
        if fonte in PAGAS:
            if not tem_serpapi():
                _registra_falha("sem SERPAPI_KEY: SERP e Trends desligados")
                continue
            if leitor.coletas_hoje(fonte, inicio_dia) >= teto:
                _registra_falha(f"teto diario da SerpAPI ({teto}) atingido")
                continue
        try:
            sinais = coletor()
        except ErroSinal as erro:
            _registra_falha(str(erro))
            continue
        except Exception as erro:  # noqa: BLE001 — fonte quebrada nao derruba o hub
            _registra_falha(f"{fonte} ({consulta[:40]}): {type(erro).__name__}: {erro}")
            continue
        banco.grava_sinais(sinais)
        banco.registra_coleta({"site": nome, "hub": hub_id, "fonte": fonte,
                               "consulta": consulta, "itens": len(sinais),
                               "coletado_em": agora.isoformat()})
        novos.extend(sinais)
        print(f"    {fonte:16} {consulta[:45]:45} {len(sinais):3} sinais")
    return novos


def log_valor(v: float | None) -> float:
    """log10 saturado em 0..1 para valores sociais (10 = 0.25, 10k = 1)."""
    if not v or v <= 1:
        return 0.0
    return min(1.0, math.log10(v) / 4)
