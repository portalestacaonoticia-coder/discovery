"""Selecao automatica do dia: dentro da meta, aprova sozinho as melhores
pautas novas. Nada e' publicado aqui — aprovar so' marca a escolha do dia.
O veto na aba (descartar) abre vaga e o proximo ciclo repoe.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .banco import Banco
from .pontua import seleciona

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
                           fatos_usados=banco.fatos_selecionados_hoje(site, inicio_dia))
    quando = datetime.now(timezone.utc).isoformat()
    for p in escolhidas:
        banco.marca_selecionada(p["id"], p["pontuacao"], p["motivo_selecao"], quando)
        print(f"  selecionada [{p['pontuacao']} pts] {(p.get('titulo_sug') or '')[:80]}")
    return len(escolhidas)
