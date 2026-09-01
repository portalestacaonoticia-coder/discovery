"""Selecao automatica do dia: dentro da meta, aprova sozinho as melhores
pautas novas. Nada e' publicado aqui — aprovar so' marca a escolha do dia.
O veto na aba (descartar) abre vaga e o proximo ciclo repoe.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .banco import Banco
from .pontua import criterios_com_padrao, eh_quente, proximo_horario_fixa, seleciona

# Sao Paulo e' UTC-3 fixo desde 2019; dispensa tzdata no Windows.
FUSO_SP = timezone(timedelta(hours=-3))


def inicio_do_dia_sp() -> str:
    agora = datetime.now(FUSO_SP)
    return agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def roda_selecao(banco: Banco, site: str) -> int:
    """Preenche as vagas do dia; devolve quantas pautas selecionou."""
    meta = banco.meta_do_site(site)
    if not meta:
        return 0
    inicio_dia = inicio_do_dia_sp()
    vagas = int(meta.get("pautas_por_dia") or 0) - banco.selecionadas_hoje(site, inicio_dia)
    if vagas <= 0:
        return 0

    escolhidas = seleciona(banco.pautas_novas(site), vagas, meta.get("criterios"),
                           fatos_usados=banco.fatos_selecionados_hoje(site, inicio_dia),
                           hubs_usados=banco.hubs_selecionados_hoje(site, inicio_dia))
    quando = datetime.now(timezone.utc)
    criterios = criterios_com_padrao(meta.get("criterios"))
    ultimo_txt = banco.ultimo_horario_sugerido(site, inicio_dia)
    ultimo = datetime.fromisoformat(ultimo_txt.replace("Z", "+00:00")) if ultimo_txt else None

    for p in escolhidas:
        # Duas pistas: quente sai o quanto antes; fixa distribui pela janela.
        if eh_quente(p, criterios, quando):
            horario = quando
        else:
            horario = proximo_horario_fixa(quando, ultimo, criterios,
                                           int(meta.get("pautas_por_dia") or 1), FUSO_SP)
            ultimo = horario
        banco.marca_selecionada(p["id"], p["pontuacao"], p["motivo_selecao"],
                                quando.isoformat(), horario.isoformat())
        rotulo = "para já" if horario <= quando else f"para {horario.astimezone(FUSO_SP):%H:%M}"
        print(f"  selecionada [{p['pontuacao']} pts, {rotulo}] {(p.get('titulo_sug') or '')[:70]}")
    return len(escolhidas)
