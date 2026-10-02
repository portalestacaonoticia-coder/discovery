"""DiscoverScore: a nota de oportunidade editorial de um topico, e o plano
de producao do site (quantas pautas por dia, por quanto tempo).

Mesmo contrato do pontua.py do radar antigo: o criterio e' do editor
(metas.criterios["discover"], editado na tela Radar), a decisao e' do robo,
e toda nota vem com um motivo legivel.

    DiscoverScore = 20% velocidade de tendencia (Trends)
                  + 15% frescor (o Discover vive ~72h)
                  + 15% afinidade com o publico do hub
                  + 15% lacuna de informacao (perguntas sem resposta no site)
                  + 10% velocidade de noticias (veiculos em 24h)
                  + 10% potencial visual
                  + 10% autoridade topica do site (o que ele ja' publicou)
                  +  5% conversa social

Cada componente vale 0..1; a nota final vai de 0 a 100.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from . import tendencias
from .normaliza import sem_acento
from .sinais import log_valor

PADRAO_DISCOVER = {
    "pesos": {"velocidade_tendencia": 20, "frescor": 15, "afinidade_publico": 15,
              "lacuna_informacao": 15, "velocidade_noticias": 10, "potencial_visual": 10,
              "autoridade_topica": 10, "conversa_social": 5},
    # piso: abaixo disso o topico nao vira pauta; vaga vazia e' melhor
    "minimo": 45,
    # quantos topicos por site passam para angulo/pesquisa/brief por rodada
    "topicos_por_ciclo": 3,
    # o mesmo teto por hub/dia que o publicador aplica
    "satelites_por_hub": 2,
}

COMPONENTES = tuple(PADRAO_DISCOVER["pesos"].keys())


def criterios_discover(criterios: dict | None) -> dict:
    """Mescla metas.criterios["discover"] sobre o padrao (salvo incompleto
    nao quebra; peso desconhecido e' ignorado)."""
    c = {"pesos": dict(PADRAO_DISCOVER["pesos"]),
         "minimo": PADRAO_DISCOVER["minimo"],
         "topicos_por_ciclo": PADRAO_DISCOVER["topicos_por_ciclo"],
         "satelites_por_hub": PADRAO_DISCOVER["satelites_por_hub"]}
    # Pesquisa de pautas da tela Radar: categorias ativas e temas macro por
    # hub. Hub fora de hubs_ativos nao coleta sinal nem recebe sugestao;
    # temas viram as consultas de sinal do hub.
    c["pesquisa"] = {"hubs_ativos": [], "temas": {}, "linha_editorial": "", "formato": "livre"}
    d = (criterios or {}).get("discover") if isinstance(criterios, dict) else None
    if isinstance(d, dict):
        for chave in ("minimo", "topicos_por_ciclo", "satelites_por_hub"):
            if isinstance(d.get(chave), (int, float)):
                c[chave] = d[chave]
        for nome, peso in (d.get("pesos") or {}).items():
            if nome in c["pesos"] and isinstance(peso, (int, float)):
                c["pesos"][nome] = peso
        p = d.get("pesquisa")
        if isinstance(p, dict):
            c["pesquisa"]["hubs_ativos"] = [str(h) for h in (p.get("hubs_ativos") or []) if h]
            c["pesquisa"]["temas"] = {str(h): str(t) for h, t in (p.get("temas") or {}).items()
                                      if isinstance(t, str) and t.strip()}
            # Linha editorial da tela: regras livres + formato ("individual" =
            # um assunto por pauta, sem listas). O motor as passa ao angulo,
            # ao brief e ao redator.
            c["pesquisa"]["linha_editorial"] = str(p.get("linha_editorial") or "").strip()[:1000]
            c["pesquisa"]["formato"] = "individual" if p.get("formato") == "individual" else "livre"
    # o teto por hub tambem pode vir do criterio antigo (mesma tela)
    if isinstance(criterios, dict) and isinstance(criterios.get("satelites_por_hub"), (int, float)) \
            and not (isinstance(d, dict) and "satelites_por_hub" in d):
        c["satelites_por_hub"] = criterios["satelites_por_hub"]
    return c


# -- plano de producao --------------------------------------------------------

def _data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def em_producao(meta: dict | None, hoje: date) -> tuple[bool, str]:
    """O site esta' dentro do periodo de producao? Sem as duas datas, NAO:
    producao no motor discover e' sempre uma decisao explicita com prazo.
    Devolve (bool, motivo legivel)."""
    meta = meta or {}
    inicio, fim = _data(meta.get("producao_inicio")), _data(meta.get("producao_fim"))
    if not inicio or not fim:
        return False, "sem periodo de producao configurado (metas.producao_inicio/fim)"
    if hoje < inicio:
        return False, f"producao comeca em {inicio:%d/%m}"
    if hoje > fim:
        return False, f"fora do periodo (terminou em {fim:%d/%m})"
    dias = (fim - hoje).days
    return True, f"em producao ate {fim:%d/%m}" + (f" ({dias} dia(s) restantes)" if dias <= 3 else "")


def avisos_de_producao(meta: dict | None, hoje: date) -> list[str]:
    """Mensagens para o dia em que o site entra, o dia em que sai e 3 dias
    antes de acabar. Quem chama garante uma vez por dia."""
    meta = meta or {}
    inicio, fim = _data(meta.get("producao_inicio")), _data(meta.get("producao_fim"))
    if not inicio or not fim:
        return []
    por_dia = meta.get("pautas_por_dia") or "?"
    avisos = []
    if hoje == inicio:
        avisos.append(f"producao COMECOU hoje: {por_dia} pautas/dia ate {fim:%d/%m}")
    if (fim - hoje).days == 3:
        avisos.append(f"producao termina em 3 dias ({fim:%d/%m}), {por_dia} pautas/dia")
    if hoje == fim + timedelta(days=1):
        avisos.append(f"producao TERMINOU ontem ({fim:%d/%m}); o site parou de produzir")
    return avisos


# -- componentes --------------------------------------------------------------

def _palavras(texto: str) -> set[str]:
    limpo = re.sub(r"[^a-z0-9\s]", " ", sem_acento((texto or "").lower()))
    return {p for p in limpo.split() if len(p) >= 4}


def _cobre(pergunta: str, titulos_publicados: list[str]) -> bool:
    """A pergunta ja' tem resposta no site? Aproximacao: 2+ palavras da
    pergunta num titulo publicado."""
    p = _palavras(pergunta)
    return any(len(p & _palavras(t)) >= 2 for t in titulos_publicados)


def componentes(topico: dict, hub: dict, site: dict, historico_site: list[dict],
                agora: datetime) -> dict[str, float]:
    """Os oito componentes, cada um em 0..1. `historico_site` sao os artigos
    publicados do hub: [{titulo, url_publicada}]."""
    titulos = [a.get("titulo") or "" for a in (historico_site or [])]
    termos_topico = set(topico.get("termos") or [])
    for m in topico.get("manchetes") or []:
        termos_topico |= tendencias.tokens(m.get("titulo") or "")

    # afinidade: quanto do vocabulario do hub (termos + perfil do leitor)
    # aparece no topico
    vocabulario = set()
    for t in hub.get("termos") or []:
        vocabulario |= _palavras(str(t))
    vocabulario |= _palavras(str(hub.get("perfil_leitor") or ""))
    acertos = len(vocabulario & termos_topico)
    afinidade = min(1.0, acertos / 3) if vocabulario else 0.0

    # lacuna: perguntas que o site ainda nao respondeu + ninguem cobriu
    # recentemente nos organicos
    perguntas = topico.get("perguntas") or []
    sem_cobertura = sum(1 for p in perguntas if not _cobre(p, titulos))
    lacuna = 0.6 * min(1.0, sem_cobertura / 4)
    organicos = topico.get("organicos") or []
    recentes = [o for o in organicos if _organico_recente(o.get("data"))]
    if organicos and not recentes:
        lacuna += 0.4
    elif not organicos:
        lacuna += 0.2   # sem SERP nao da' para saber; meio-termo

    # visual
    imagem = hub.get("imagem")
    visual = 0.0 if imagem is False else 0.6
    if hub.get("estilo_visual") or site.get("estilo_visual"):
        visual += 0.2
    if topico.get("tem_miniatura"):
        visual += 0.2

    # autoridade topica: so' com o que o site ja' publicou (GSC fora da v1)
    autoridade = 0.6 * min(1.0, len(titulos) / 10)
    if titulos and termos_topico:
        melhor = max(len(termos_topico & _palavras(t)) / max(1, len(termos_topico)) for t in titulos)
        autoridade += 0.4 * min(1.0, melhor * 3)

    # social
    posts = topico.get("social") or []
    social = 0.0
    if posts:
        maior = max(float(p.get("valor") or 0) for p in posts)
        social = min(1.0, len(posts) / 5) * (0.5 + 0.5 * log_valor(maior))

    return {
        "velocidade_tendencia": round(tendencias.velocidade_tendencia(topico), 3),
        "frescor": round(tendencias.frescor(topico, agora), 3),
        "afinidade_publico": round(afinidade, 3),
        "lacuna_informacao": round(min(1.0, lacuna), 3),
        "velocidade_noticias": round(tendencias.velocidade_noticias(topico), 3),
        "potencial_visual": round(min(1.0, visual), 3),
        "autoridade_topica": round(min(1.0, autoridade), 3),
        "conversa_social": round(min(1.0, social), 3),
    }


def _organico_recente(data: str | None) -> bool:
    """A SerpAPI devolve a data do organico como texto ("3 days ago",
    "Sep 12, 2026"). Recente = fala em horas/dias/semanas ou traz o ano atual."""
    if not data:
        return False
    d = data.lower()
    if any(p in d for p in ("hour", "hora", "day", "dia", "week", "semana", "min")):
        return True
    return str(datetime.now().year) in d


ROTULO = {"velocidade_tendencia": "tendencia", "frescor": "fresca",
          "afinidade_publico": "afinidade", "lacuna_informacao": "lacuna",
          "velocidade_noticias": "noticias", "potencial_visual": "visual",
          "autoridade_topica": "autoridade", "conversa_social": "social"}


def pontua_topico(topico: dict, comp: dict[str, float], criterios: dict) -> tuple[int, str]:
    """Soma ponderada dos componentes (pesos somam 100 no padrao; se o editor
    mudar a soma, normaliza). Motivo = os tres componentes que mais pesaram."""
    pesos = criterios["pesos"]
    total_pesos = sum(pesos.values()) or 1
    contribuicoes = {n: pesos.get(n, 0) * comp.get(n, 0.0) for n in COMPONENTES}
    nota = int(round(sum(contribuicoes.values()) * 100 / total_pesos))
    principais = sorted(contribuicoes.items(), key=lambda kv: kv[1], reverse=True)[:3]
    motivo = " · ".join(f"{ROTULO[n]} {comp.get(n, 0.0):.1f}" for n, v in principais if v > 0)
    return nota, motivo or "sem sinal forte"


def seleciona_topicos(topicos: list[dict], criterios: dict,
                      hubs_usados: dict | None = None) -> list[dict]:
    """Os melhores topicos do site para virar pauta nesta rodada: acima do
    piso, um por chave, teto por hub, no maximo `topicos_por_ciclo`, e nunca
    um que ja' virou pauta."""
    hubs_usados = dict(hubs_usados or {})
    escolhidos, chaves = [], set()
    for t in sorted(topicos, key=lambda t: t.get("pontuacao", 0), reverse=True):
        if t.get("pontuacao", 0) < criterios["minimo"]:
            break
        if t.get("ja_pautado") or t["chave"] in chaves:
            continue
        hub = t.get("hub") or "_"
        if hubs_usados.get(hub, 0) >= criterios["satelites_por_hub"]:
            continue
        escolhidos.append(t)
        chaves.add(t["chave"])
        hubs_usados[hub] = hubs_usados.get(hub, 0) + 1
        if len(escolhidos) >= criterios["topicos_por_ciclo"]:
            break
    return escolhidos
