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

# os exemplos-modelo nao podem ser aceitos com os dados de outro dia
from radar.gerador_satelite import _exemplos
for exemplo in _exemplos().split("====="):
    corpo = exemplo.split("TITULO:", 1)[1]
    assert c("t", corpo), "exemplo copiado passaria no conferente"

print("conferente: ok")
