"""Teste offline do gerador de cotacao. Nao acessa rede nem banco.

Usa uma serie simulada de 30 pregoes para conferir: portoes, numeros da tabela,
formato do texto e JSON-LD. Rode isso antes de qualquer coisa em producao.

    python testar_dolar.py
"""
from datetime import date, datetime, timedelta

from radar.config import carrega_sites
from radar.dolar_diario import portoes
from radar.gerador_dolar import monta

site = carrega_sites()["doll"]

# serie fake: 30 pregoes subindo de 5,10 para 5,42
serie = []
d = date(2026, 7, 14)
valor = 5.10
while len(serie) < 30:
    if d.weekday() < 5:
        serie.append({"data": d, "compra": round(valor - 0.0004, 4), "venda": round(valor, 4)})
        valor += 0.011
    d += timedelta(days=1)

hoje = dict(serie[-1], hora=datetime(2026, 8, 24, 13, 10))

liberado, motivo = portoes(hoje, serie)
print(f"portao: {'LIBERADO' if liberado else 'RASCUNHO'} — {motivo}\n")

artigo = monta(hoje, serie, site)
print(artigo["markdown"])
print("\n--- JSON-LD ---")
print(artigo["jsonld"])

# portao segurando dado maluco
ruim = dict(hoje, venda=hoje["venda"] * 1.2)
print("\nsalto de 20%:", portoes(ruim, serie))
try:
    portoes(dict(hoje, venda=99.0), serie)
except ValueError as e:
    print("faixa implausivel barrada:", e)
