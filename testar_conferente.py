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

print("conferente: ok")
