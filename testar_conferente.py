"""Teste offline do conferente do satelite (radar/confere_satelite.py).
Os casos sao os erros reais do ensaio local de 19/10/2026. Sem rede nem banco.

    python testar_conferente.py
"""
from datetime import date

from radar.confere_satelite import confere

N = {"venda": 5.0826, "var_dia": 0.60, "var_semana": 1.41, "var_mes": -1.68,
     "var_janela": -0.5, "maior": 5.2238, "menor": 4.9698, "n": 22,
     "seq": 4, "direcao": 1, "max_ano": 5.5739, "min_ano": 4.8973,
     "max_quando": date(2025, 12, 29), "min_quando": date(2026, 5, 11),
     "pregoes_serie": 285, "data": date(2026, 10, 16)}
HOJE = date(2026, 10, 19)                      # segunda; pregao foi sexta (16)
MANCHETE = "Dólar sobe a R$ 5,22 com aversão a risco global"
DATA_MANCHETE = date(2026, 10, 1)


def c(titulo, corpo, manchete=MANCHETE, data_manchete=DATA_MANCHETE):
    return confere(titulo, corpo, N, manchete, HOJE, data_manchete)


# texto certo passa (valores arredondados e distancia calculada inclusive)
bom = ("Segundo a imprensa, o dólar subiu. Na PTAX de sexta-feira, 16 de outubro, "
       "a moeda fechou a R$ 5,0826, alta de 0,60%, o quarto pregão seguido de alta. "
       "Na semana subiu 1,41%; no mês caiu 1,68%. Está R$ 0,4913 abaixo da máxima "
       "de R$ 5,5739, de 29/12/2025, e acima da mínima de R$ 4,8973 (11/05/2026). "
       "O dólar a R$ 5,08 segue abaixo dos R$ 5,22 da manchete.")
assert c("Dólar fecha a R$ 5,08", bom) == [], c("Dólar fecha a R$ 5,08", bom)

# direcao invertida no dia e no mes
assert any("direcao invertida" in p for p in c("t", "O dólar fechou em queda de 0,60%."))
assert any("CAIU 1,68%" in p for p in c("t", "No mês, o avanço foi de 1,68%."))
assert c("t", "No mês, o dólar acumulou queda de 1,68%.") == []

# sequencia com a direcao errada
assert any("sequencia" in p for p in c("t", "É o quarto pregão seguido de queda."))

# cotacao inventada (nem base, nem manchete)
assert any("R$ 5,30" in p for p in c("Dólar fecha acima de R$ 5,30", "x"))

# percentual inventado
assert any("3,2%" in p for p in c("t", "O dólar subiu 3,2% no ano."))

# manchete antiga atribuida a hoje
probs = c("t", "O dólar fechou nesta segunda-feira (19), 19 de outubro, em alta.")
assert any("segunda-feira" in p for p in probs), probs
assert any("(19)" in p for p in probs), probs
assert any("19 de outubro" in p for p in probs), probs

# hoje vale quando a manchete e' de hoje
assert c("t", "Nesta segunda-feira, 19 de outubro, a imprensa noticiou a alta.",
         data_manchete=HOJE) == []

# estilo: termos que o portal nao assina
assert any("dolar comercial" in p for p in c("t", "O dólar comercial fechou em alta."))
assert any("historicos" in p for p in c("t", "A máxima histórica foi de R$ 5,5739."))
assert any("veiculo" in p for p in c("t", "A cotação subiu, segundo o veiculo."))
assert any("analise tecnica" in p for p in c("t", "Sem rompimento das barreiras técnicas."))
assert any("analise tecnica" in p for p in c("t", "Indica rotação de posições em derivativos."))

# distancia em % ate os extremos do ano e' analise permitida
assert c("t", "A PTAX está 8,81% abaixo da máxima do ano e 3,78% acima da mínima.") == []

# dado nosso na boca da imprensa (26641 do ensaio)
assert any("Banco Central" in p for p in c(
    "t", "Segundo a imprensa, a PTAX fechou a sexta-feira a R$ 5,0826, alta de 0,60%."))
# ... mas o numero da propria manchete pode, e "segundo a PTAX" tambem
assert c("t", "Segundo a imprensa, o dólar subiu a R$ 5,22.") == []
assert c("t", "Segundo a PTAX do Banco Central, o dólar fechou a R$ 5,0826.") == []

# posicao na faixa: a PTAX (R$ 5,0826 entre 4,9698 e 5,2238) esta' mais perto do piso
assert any("piso da faixa" in p for p in c("t", "O fechamento ficou na metade superior do intervalo recente."))
assert any("piso da faixa" in p for p in c("t", "A cotação está mais próxima do topo da faixa."))
assert c("t", "O fechamento ficou mais perto da parte baixa da faixa recente.") == []
# no ano tambem mais perto da minima; "distante do pico" nao e' afirmar proximidade
assert any("do ano" in p for p in c("t", "No ano, a cotação está perto da máxima."))
assert c("t", "No ano, o dólar segue distante do pico de dezembro.") == []

# data da manchete grudada em dado nosso (26641 da v3)
assert any("pregao de sexta-feira" in p for p in c(
    "t", "A taxa de 1º de outubro está 8,81% abaixo da máxima do ano."))
assert c("t", "A imprensa noticiou em 1º de outubro que o dólar subiu a R$ 5,22.") == []

# direcao sem percentual (N: dia +0,60%) — titulo e frase da PTAX
assert any("SUBIU" in p for p in c("Dólar fecha em queda na PTAX a R$ 5,0826", "x"))
assert any("SUBIU" in p for p in c("t", "O dólar recuou e fechou a R$ 5,0826 na PTAX."))
assert c("Dólar fecha em alta na sexta; PTAX a R$ 5,0826", "x") == []
assert c("Dólar a R$ 5,0826, mas mês tem queda de 1,68%", "x") == []   # outro periodo
assert c("Segundo a imprensa, dólar caiu a R$ 5,22", "x") == []        # da manchete

# efeito no real: dolar subiu na semana (+1,41%) => real perdeu
assert any("efeito no real" in p for p in c(
    "t", "O saldo da semana é positivo para o real: o dólar subiu 1,41%."))
assert any("efeito no real" in p for p in c(
    "t", "No mês, o dólar caiu 1,68%, com desvalorização do real."))
assert c("t", "No mês, o dólar caiu 1,68%, com valorização do real.") == []
assert any("efeito no real" in p for p in c(
    "t", "A PTAX a R$ 5,0826 mostra o real se valorizando no dia."))

# titulo unico
recentes = ["Dólar cai 0,52% e PTAX fecha a R$ 5,0564, perto do piso da faixa"]
assert any("titulo" in p for p in confere(
    "Dólar cai 0,52% e PTAX fecha a R$ 5,0564, perto do piso da faixa!", "x",
    {**N, "venda": 5.0564, "var_dia": -0.52}, "", HOJE, None, recentes))
assert not any("titulo" in p for p in confere(
    "Real ganha fôlego: PTAX recua a R$ 5,0564", "x",
    {**N, "venda": 5.0564, "var_dia": -0.52}, "", HOJE, None, recentes))

# "patamar historico" (26635 da v5) tambem e' proibido
assert any("historicos" in p for p in c("t", "Está no patamar histórico mais baixo do período."))

# ordinal do dia 1 corrigido por codigo, sem tocar no resto
from radar.gerador_satelite import _primeiro_do_mes
assert _primeiro_do_mes("Na quinta-feira, 1 de outubro, e em 11 de maio") == \
    "Na quinta-feira, 1º de outubro, e em 11 de maio"
assert _primeiro_do_mes("1º de outubro") == "1º de outubro"

# real nos extremos do ano (1o satelite do Mac): na minima do dolar o real
# esteve no ponto mais forte; o comparativo "mais forte do que no pico" passa
assert any("mais FORTE" in p for p in c("t", "O real está mais forte do que no pico de dezembro, mas distante do nível mais fraco registrado em maio."))
assert c("t", "O real está mais forte do que no pico de dezembro.") == []

# data relativa errada para manchete antiga
assert any("passada" in p for p in confere("t", "A publicação é de quarta-feira passada.", N, "", HOJE, date(2026, 8, 26)))
assert confere("t", "A publicação é de quarta-feira passada.", N, "", HOJE, date(2026, 10, 14)) == []

# os exemplos-modelo nao podem ser aceitos com os dados de outro dia
from radar.gerador_satelite import _exemplos
for exemplo in _exemplos().split("====="):
    corpo = exemplo.split("TITULO:", 1)[1]
    assert c("t", corpo), "exemplo copiado passaria no conferente"

print("conferente: ok")

# --- dado proprio por categoria (21/10/2026) ---------------------------------
# cada exemplo-modelo passa no conferente com os PROPRIOS dados (extras), e
# copiar o exemplo com os dados de outro dia e' reprovado
from radar.gerador_satelite import _exemplos as _ex_hub


def _n_ptax(venda, var_dia, data):
    return {**N, "venda": venda, "var_dia": var_dia, "var_semana": None,
            "var_mes": None, "var_janela": None, "maior": venda * 1.02,
            "menor": venda * 0.98, "data": data}


CASOS = {
    "indicadores": (_n_ptax(5.3920, -0.2, date(2026, 3, 9)),
                    {"brl": [5.48, 5.55, 5.60], "pct": [1.61, 4.10, 4.25, 4.62],
                     "variacoes_moeda": {"revisao": -1.26}, "variacoes_outras": {},
                     "datas": [date(2026, 3, 6), date(2026, 2, 6)]},
                    "Focus eleva projeção do PIB e mantém câmbio",
                    date(2026, 3, 9), date(2026, 3, 9)),
    "politica-monetaria": (_n_ptax(5.2810, -0.31, date(2026, 2, 13)),
                           {"brl": [], "pct": [11.25, 11.75, 0.50, 4.90, 6.35, 10.50, 10.75],
                            "variacoes_moeda": {}, "variacoes_outras": {},
                            "datas": [date(2026, 1, 30), date(2026, 2, 13)]},
                           "Copom sinaliza novos cortes de juros",
                           date(2026, 2, 13), date(2026, 2, 12)),
    "viagem": (_n_ptax(5.3920, 0.35, date(2026, 3, 13)),
               {"brl": [7.1240, 7.2583, 7.0815, 7.2990, 7124.0, 7373.34, 249.34],
                "pct": [3.5], "variacoes_moeda": {"dia": 0.42, "mes": -1.85},
                "variacoes_outras": {}, "datas": [date(2026, 3, 13)]},
               "Dólar sobe com cautela no exterior",
               date(2026, 3, 13), date(2026, 3, 13)),
}
CASOS["indicadores-inflacao"] = (
    _n_ptax(5.3120, 0.1, date(2026, 4, 10)),
    {"brl": [], "pct": [0.45, 0.62, 4.21, 3.0, 1.5, 4.5, 4.05, 4.20, 3.80],
     "variacoes_moeda": {}, "variacoes_outras": {"ipca de marco": 0.45},
     "datas": [date(2026, 4, 10)]},
    "IPCA de março desacelera e fica em 0,45%", date(2026, 4, 13), date(2026, 4, 10))
for hub, (n_hub, extras, manchete, hoje_hub, data_m) in CASOS.items():
    exemplo = _ex_hub(hub)
    assert "DADOS DESTE EXEMPLO" in exemplo and hub not in ("cotacao",), hub
    tit, corpo = exemplo.split("TITULO:", 1)[1].split("\n", 1)
    probs = confere(tit.strip(), corpo, n_hub, manchete, hoje_hub, data_m, extras=extras)
    assert probs == [], (hub, probs)
    # copiado com os dados de hoje (N, sem extras da categoria): reprovado
    assert confere(tit.strip(), corpo, N, "", HOJE, None, extras={"datas": []}), hub

# direcao de moeda estrangeira e efeito no real com extras
ex_euro = {"brl": [5.6317], "pct": [], "variacoes_moeda": {"euro no dia": -0.64},
           "variacoes_outras": {}, "datas": []}
assert any("direcao" in p for p in confere("t", "O euro subiu 0,64% no dia.", N, "", HOJE, None, extras=ex_euro))
assert confere("t", "O euro caiu 0,64% no dia, a R$ 5,6317.", N, "", HOJE, None, extras=ex_euro) == []
assert any("efeito no real" in p for p in confere(
    "t", "O euro caiu 0,64%, com desvalorização do real.", N, "", HOJE, None, extras=ex_euro))
print("conferente por categoria: ok")

# "nesta <dia>" e atribuicao dobrada (ensaio por categoria 2)
assert any("nesta" in p for p in confere("t", "A imprensa noticiou nesta terça-feira, 9 de junho, uma análise.",
                                         N, "", HOJE, date(2026, 6, 9)))
assert confere("t", "A imprensa noticiou nesta segunda-feira, 19 de outubro, uma análise.",
               N, "", HOJE, date(2026, 10, 19)) == []
assert any("repetida" in p for p in c("t", "Segundo a imprensa, a imprensa noticiou o Pix."))
print("conferente (nesta / atribuicao): ok")

# 2o recorte: teto por categoria e 2a moeda do dia (sempre diferente da 1a)
from radar.pontua import criterios_com_padrao as _crit, teto_do_hub
_c = _crit({"satelites_por_hub": 1, "satelites_por_hub_detalhe": {"viagem": 2, "indicadores": 2}})
assert (teto_do_hub(_c, "viagem"), teto_do_hub(_c, "indicadores"), teto_do_hub(_c, "cotacao")) == (2, 2, 1)
from radar.indicadores_bcb import moeda_do_dia
for d in range(1, 31):
    assert moeda_do_dia(date(2026, 11, d), 0) != moeda_do_dia(date(2026, 11, d), 1)
print("segundo recorte: ok")

# ensaio dos recortes: "ultima quinta-feira" antiga, conselho de compra, sinal dobrado
assert any("27/08" in p for p in confere("t", "Noticiado na última quinta-feira, 27 de agosto.",
                                         N, "", HOJE, date(2026, 8, 27)))
assert any("recomende" in p for p in c("t", "Isso pode incentivar a antecipação de compras de moeda."))
assert any("sinal" in p for p in c("t", "Revertendo a deflação de -0,32% de agosto."))
print("conferente (recortes): ok")

