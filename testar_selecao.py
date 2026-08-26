"""Teste offline da selecao automatica de pautas. Nao acessa rede nem banco.

    python testar_selecao.py
"""
from datetime import datetime, timedelta, timezone

from radar.pontua import criterios_com_padrao, pontua, seleciona

AGORA = datetime(2026, 8, 26, 15, 0, tzinfo=timezone.utc)


def pauta(id, item_id, angulo, dado=None, horas_atras=1):
    quando = (AGORA - timedelta(hours=horas_atras)).isoformat()
    return {"id": id, "item_id": item_id, "angulo": angulo, "titulo_sug": f"pauta {id}",
            "dado_proprio": dado, "criado_em": quando, "itens": {"publicado_em": quando}}


c = criterios_com_padrao(None)

# dado proprio vence qualquer diferenca de angulo
com_dado, _ = pontua(pauta(1, 10, "contexto", dado="+1,5%"), c, AGORA)
sem_dado, _ = pontua(pauta(2, 11, "contagem"), c, AGORA)
assert com_dado > sem_dado, f"dado proprio deveria vencer: {com_dado} x {sem_dado}"

# frescor decai
fresca, _ = pontua(pauta(3, 12, "contexto", horas_atras=2), c, AGORA)
velha, _ = pontua(pauta(4, 13, "contexto", horas_atras=100), c, AGORA)
assert fresca > velha

# uma pauta por fato: duas variacoes do fato 10, so a melhor entra
escolhidas = seleciona([
    pauta(1, 10, "contagem", dado="x"),
    pauta(2, 10, "servico"),
    pauta(3, 11, "contexto"),
], vagas=3, agora=AGORA)
assert [p["id"] for p in escolhidas] == [1, 3], [p["id"] for p in escolhidas]

# piso de qualidade: pauta velha de angulo fraco nao entra mesmo com vaga
so_fraca = seleciona([pauta(5, 14, "consequencia", horas_atras=100)], vagas=3, agora=AGORA)
assert so_fraca == [], so_fraca

# criterios do editor sobrescrevem o padrao
radical = criterios_com_padrao({"minimo": 0, "angulos": {"consequencia": 90}})
alta, _ = pontua(pauta(6, 15, "consequencia", horas_atras=100), radical, AGORA)
assert alta == 90, alta

# vagas limitam a selecao
tres = seleciona([pauta(i, 20 + i, "servico") for i in range(1, 6)], vagas=2, agora=AGORA)
assert len(tres) == 2

# fato ja escolhido hoje (mesmo que vetado) nao volta por outro angulo
repos = seleciona([pauta(7, 30, "contagem", dado="x"), pauta(8, 31, "servico")],
                  vagas=1, agora=AGORA, fatos_usados={30})
assert [p["id"] for p in repos] == [8], [p["id"] for p in repos]

print("selecao ok: pontuacao, dedup por fato, piso, criterios do editor e vagas")
