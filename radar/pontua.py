"""Pontuacao de pautas — o criterio e' do editor, a decisao e' do robo.

Orientado a Google News/Discover: originalidade (dado proprio) > chegar cedo
(frescor) > angulo. Os pesos vem da coluna criterios da tabela metas (editada
na aba Radar do conteudo.tihee); sem ela, valem os padroes abaixo. A selecao
escolhe NO MAXIMO uma pauta por fato (item_id): publicar variacoes do mesmo
fato em serie e' o conteudo em escala que o Google derruba.
"""
from __future__ import annotations

from datetime import datetime, timezone

PADRAO = {
    # dado proprio e' a maior alavanca: News/Discover premiam informacao
    # original e punem reescrita em escala
    "dado_proprio": 35,
    # piso de qualidade: abaixo disso a vaga fica aberta em vez de aprovar resto
    "minimo": 30,
    # base por angulo: quem usa a base propria na frente; servico captura
    # busca; contexto e' o que o News agrupa; consequencia por ultimo
    "angulos": {"contagem": 30, "agregado": 25, "comparacao": 25,
                "servico": 20, "contexto": 15, "consequencia": 8},
    # frescor do FATO: valor de noticia morre em horas
    "frescor": {"ate6h": 30, "ate24h": 20, "ate48h": 10},
    # fato com ate N horas e' "quente": sai o quanto antes. Acima disso e'
    # "fixa": o valor vem do dado, entao distribui ao longo do dia.
    "quente_ate_horas": 24,
    # janela editorial (horas cheias, fuso de Sao Paulo) das pautas fixas
    "janela": {"inicio": 8, "fim": 20},
    # teto de satelites por hub por dia — o MESMO teto que o publicador
    # aplica. A selecao precisa conhece-lo: em 31/08 ela encheu a meta com
    # 6 pautas de cotacao sendo que so 2 podiam sair, e o dia fechou 6/8.
    "satelites_por_hub": 2,
}


def criterios_com_padrao(criterios: dict | None) -> dict:
    """Mescla os criterios salvos com os padroes (salvo incompleto nao quebra)."""
    c = {k: PADRAO[k] for k in ("dado_proprio", "minimo", "quente_ate_horas",
                                "satelites_por_hub")}
    c["angulos"] = dict(PADRAO["angulos"])
    c["frescor"] = dict(PADRAO["frescor"])
    c["janela"] = dict(PADRAO["janela"])
    if criterios:
        for chave in ("dado_proprio", "minimo", "quente_ate_horas",
                      "satelites_por_hub"):
            if isinstance(criterios.get(chave), (int, float)):
                c[chave] = criterios[chave]
        c["angulos"].update(criterios.get("angulos") or {})
        c["frescor"].update(criterios.get("frescor") or {})
        c["janela"].update(criterios.get("janela") or {})
    return c


def horas_do_fato(pauta: dict, agora: datetime) -> float:
    referencia = (pauta.get("itens") or {}).get("publicado_em") or pauta["criado_em"]
    quando = datetime.fromisoformat(str(referencia).replace("Z", "+00:00"))
    return (agora - quando).total_seconds() / 3600


def eh_quente(pauta: dict, criterios: dict, agora: datetime) -> bool:
    """Quente = o valor esta na hora: sai o quanto antes. O resto e' fixa."""
    return horas_do_fato(pauta, agora) <= criterios["quente_ate_horas"]


def proximo_horario_fixa(agora: datetime, ultimo: datetime | None,
                         criterios: dict, meta: int, fuso) -> datetime:
    """Proximo slot da pista fixa: espacado pela meta dentro da janela
    editorial; nunca no passado; passou do fim da janela, cola no fim."""
    j = criterios["janela"]
    hoje = agora.astimezone(fuso)
    inicio = hoje.replace(hour=int(j["inicio"]), minute=0, second=0, microsecond=0)
    fim = hoje.replace(hour=int(j["fim"]), minute=0, second=0, microsecond=0)
    espaco = (fim - inicio) / max(meta, 1)
    candidato = max(agora, inicio)
    if ultimo is not None:
        candidato = max(candidato, ultimo + espaco)
    return min(candidato, fim)


def pontua(pauta: dict, criterios: dict, agora: datetime) -> tuple[int, str]:
    """Devolve (pontos, motivo legivel para aparecer na aba)."""
    pontos = criterios["angulos"].get(pauta["angulo"], 10)
    motivos = [f"ângulo {pauta['angulo']}"]

    if pauta.get("dado_proprio"):
        pontos += criterios["dado_proprio"]
        motivos.append("dado próprio")

    horas = horas_do_fato(pauta, agora)
    if horas <= 6:
        pontos += criterios["frescor"]["ate6h"]
        motivos.append("muito fresca (≤6h)")
    elif horas <= 24:
        pontos += criterios["frescor"]["ate24h"]
        motivos.append("fresca (≤24h)")
    elif horas <= 48:
        pontos += criterios["frescor"]["ate48h"]
        motivos.append("de ontem (≤48h)")

    return int(pontos), " · ".join(motivos)


def seleciona(pautas: list[dict], vagas: int, criterios: dict | None = None,
              agora: datetime | None = None,
              fatos_usados: set | None = None,
              hubs_usados: dict | None = None) -> list[dict]:
    """As melhores pautas dentro das vagas: uma por fato, acima do piso, e
    no maximo satelites_por_hub por hub NO DIA (contando o que ja foi
    selecionado antes — hubs_usados). Sem este ultimo filtro a meta encaixa
    pautas que o publicador vai barrar, e a vaga morre sem virar post.
    fatos_usados = item_ids ja selecionados hoje (outra rodada ou pos-veto):
    o mesmo fato nunca entra duas vezes no dia, nem por outro angulo."""
    agora = agora or datetime.now(timezone.utc)
    c = criterios_com_padrao(criterios)

    pontuadas = []
    for p in pautas:
        pontos, motivo = pontua(p, c, agora)
        pontuadas.append({**p, "pontuacao": pontos, "motivo_selecao": motivo})
    pontuadas.sort(key=lambda p: p["pontuacao"], reverse=True)

    escolhidas: list[dict] = []
    fatos: set = set(fatos_usados or set())
    por_hub: dict = dict(hubs_usados or {})
    teto_hub = int(c.get("satelites_por_hub") or 0)
    for p in pontuadas:
        if len(escolhidas) >= vagas:
            break
        if p["pontuacao"] < c["minimo"]:
            break  # lista ordenada: dali para baixo ninguem passa do piso
        fato = p.get("item_id") or -p["id"]
        if fato in fatos:
            continue
        hub = p.get("hub") or "_"
        if teto_hub and por_hub.get(hub, 0) >= teto_hub:
            continue  # o hub ja tem o dia cheio: a vaga fica para outro hub
        fatos.add(fato)
        por_hub[hub] = por_hub.get(hub, 0) + 1
        escolhidas.append(p)
    return escolhidas
