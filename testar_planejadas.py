"""Teste offline das pautas planejadas (7d): o plano vira ideia marcada e os
fatos do planejador chegam a' pesquisa sem busca nenhuma.

    python testar_planejadas.py
"""
from datetime import datetime, timezone

from radar.pautas_planejadas import MIN_FATOS, monta_linhas
from radar.pesquisa import pesquisa

SITE = {"dominio": "exemplo.com.br", "hubs": [{"id": "dinheiro", "titulo": "Dinheiro"}]}
FATO = {"afirmacao": "A primeira parcela do 13o deve ser paga ate 30 de novembro",
        "valor": "30 de novembro", "fonte_url": "https://www.gov.br/x", "fonte_nome": "Gov.br"}
fatos = [dict(FATO, afirmacao=f"{FATO['afirmacao']} ({i})") for i in range(MIN_FATOS)]
plano = [
    {"hub": "dinheiro", "titulo": "13o salario: datas e calculo", "motivo": "prazo no fim do mes",
     "perguntas": ["Quando cai?"], "fatos": fatos + [{"afirmacao": "sem fonte"},
                                                      {"afirmacao": "url ruim", "fonte_url": "gov.br"}]},
    {"hub": "dinheiro", "titulo": "13o salario: datas e calculo", "fatos": fatos},   # repetida
    {"hub": "nao-existe", "titulo": "Hub errado", "fatos": fatos},
    {"hub": "dinheiro", "titulo": "Poucos fatos", "fatos": fatos[:MIN_FATOS - 1]},
    {"hub": "dinheiro", "fatos": fatos},                                              # sem titulo
    {"hub": "dinheiro", "titulo": "Segunda pauta", "fatos": fatos},
]
agora = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
linhas, recusas = monta_linhas(plano, "exemplo", SITE, agora)
assert [l["titulo"] for l in linhas] == ["13o salario: datas e calculo", "Segunda pauta"]
assert len(recusas) == 4, recusas
l = linhas[0]
assert l["status"] == "marcada" and l["origem"] == "planejada" and l["chave"].startswith("manual:")
assert len(l["detalhes"]["fatos"]) == MIN_FATOS            # sem fonte / url ruim ficaram de fora
assert linhas[0]["marcada_em"] < linhas[1]["marcada_em"]   # a ordem do plano e' a da fila

# Os fatos do planejador viram evidencias sem hub com fontes e sem modelo.
ev = pesquisa({"titulo": l["titulo"], "detalhes": l["detalhes"]}, {}, "exemplo", SITE,
              SITE["hubs"][0], None)
assert len(ev["fatos"]) == MIN_FATOS and ev["buscas"] == 0
assert ev["fatos"][0]["fonte_url"] == "https://www.gov.br/x"
assert ev["fontes_primarias"][0]["url"] == "https://www.gov.br/x"
assert ev["perguntas"] == ["Quando cai?"]
# Ideia do motor, sem fatos planejados: nada muda.
assert pesquisa({"titulo": "x", "detalhes": {}}, {}, "exemplo", SITE, SITE["hubs"][0], None)["fatos"] == []
print("ok: pautas planejadas — carga, recusas e fatos na pesquisa")
