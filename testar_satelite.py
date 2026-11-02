"""Teste offline do gerador de satelites: o que acontece quando o modelo ou o
dado da categoria falham (25/10/2026). Sem rede, sem banco, sem modelo.

    python testar_satelite.py
"""
from datetime import date, timedelta

import radar.gerador_satelite as g

SITE = {"entidade": "Doll", "idioma": "pt-BR", "iof": {"cartao_credito": 3.5}}
SERIE = [{"data": date(2026, 9, 1) + timedelta(days=i), "venda": 5.0 + i * 0.001}
         for i in range(60)]
PAUTA = {"id": 1, "hub": "cotacao", "itens": {"titulo": "Dólar cai - Jornal",
                                               "url": "https://exemplo.com/a"}}

# 1. modelo configurado e falha: NADA de template, a pauta espera
g.llm.tem_chave = lambda: True
g._monta_llm = lambda *a, **k: (None, "o modelo nao respondeu")
art = g.monta(PAUTA, SERIE, "https://doll.com.br/guia/", SITE)
assert art == {"por": "falhou", "motivo": "o modelo nao respondeu"}, art

# 2. sem modelo nenhum (nuvem sem chave): o template continua
g.llm.tem_chave = lambda: False
art = g.monta(PAUTA, SERIE, "https://doll.com.br/guia/", SITE)
assert art["por"] == "template" and art["titulo"] and "markdown" in art, art

# 3. dado da categoria indisponivel: nao recai na PTAX (nem chama o modelo)
import importlib
importlib.reload(g)
chamou = []
g.llm.tem_chave = lambda: True
g.llm.gera = lambda *a, **k: chamou.append(1) or None
g.dado_da_categoria = lambda *a, **k: None
art, motivo = g._monta_llm({**PAUTA, "hub": "viagem"}, SERIE, "https://doll.com.br/g/", SITE)
assert art is None and "indisponivel" in motivo and not chamou, (art, motivo, chamou)

print("satelite (falha sem template, sem recair na PTAX): ok")

# 4. pauta reprovada nao segura a fila (02/11/2026, pauta 32860)
import tempfile
from pathlib import Path
import radar.satelites as s

s.ARQ_REPROVADAS = Path(tempfile.mkdtemp()) / "x" / "reprovadas.json"
assert s.le_reprovadas() == {}
fila = [{"id": 1}, {"id": 2}]
s.grava_reprovadas({"1": 3, "2": 1, "99": 3}, fila)
reprovadas = s.le_reprovadas()
assert reprovadas == {"1": 3, "2": 1}, reprovadas   # a 99 ja' saiu da fila
assert s.desistiu({"id": 1}, reprovadas) and not s.desistiu({"id": 2}, reprovadas)
assert s.falha_da_pauta("reprovado 2x: titulo quase igual")
assert s.falha_da_pauta("dado da categoria viagem indisponivel")
assert not s.falha_da_pauta("o exo devolveu resposta vazia (2x)")
print("satelite (reprovada nao segura a fila): ok")
