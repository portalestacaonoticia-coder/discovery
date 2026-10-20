"""Teste offline das correcoes dos guias (ensaio local de 20/10/2026).
Sem rede nem banco.

    python testar_guias.py
"""
from datetime import datetime

from radar.brief import fatos_fixos
from radar.checagem import _norm_num, checa_estrutura, checa_iof
from radar.gerador_artigo import _le_json_artigo
from radar.pesquisa import _dentro, _fato_confiavel, _prefixos_do_hub, _recente

SITE = {"iof": {"cartao_credito": 3.5, "especie": 3.5}}

# IOF vem do sites.yaml: 6,38% (2020) e "conta global sem IOF" reprovam
assert checa_iof("O IOF de 6,38% incide no cartão.", SITE)
assert checa_iof("Conta global pode reduzir o IOF.", SITE)
assert checa_iof("O IOF é descontado do valor recebido.", SITE)
assert checa_iof("Há isenção de IOF em programas de fidelidade.", SITE)
assert checa_iof("O IOF de 3,5% no cartão soma ao spread de 4%.", SITE) == []
assert checa_iof("O IOF de 6,38%.", {}) == []          # site sem IOF configurado

# o fato fixo leva a aliquota certa ao brief, e a checagem aceita "3,5%"
fixos = fatos_fixos({"iof": SITE["iof"], "dominio": "x"})
assert "3,50%" in fixos[0]["fato"] and fixos[0]["fonte_url"].startswith("https://")
assert _norm_num("3,50%") == _norm_num("3,5%") and _norm_num("R$ 1.000") == "r$1000"

# texto de link interno nao conta como numero do guia
corpo = ("## A\n\n" + "palavra " * 650 + "\n\n## B\n\nx\n\n## C\n\n"
         "Veja [Dólar fecha em R$ 5,0564, queda de 0,52%](https://doll.com.br/a/).")
brief = {"key_facts": [], "internal_links": [{"url": "https://doll.com.br/a/"}]}
probs = checa_estrutura({"titulo": "Guia de palavra", "corpo_md": corpo}, brief, {}, {}, SITE)
assert not any("sem fato" in p for p in probs), probs
probs = checa_estrutura({"titulo": "Guia de palavra", "corpo_md": corpo + " Custa R$ 9,99."},
                        brief, {}, {}, SITE)
assert any("R$ 9,99" in p for p in probs), probs

# JSON do guia: quebra de linha crua dentro do corpo nao derruba
motivo = []
crua = '{"titulo": "T", "resumo": "r", "corpo_md": "' + "linha\n" * 300 + '"}'
assert _le_json_artigo(crua, motivo) and not motivo
assert _le_json_artigo("sem json", motivo) is None and motivo == ["resposta sem JSON"]

# fato so' de dentro do caminho da fonte oficial, e de pagina recente
hub = {"fontes": [{"nome": "Receita", "url": "https://www.gov.br/receitafederal"},
                  {"nome": "BC", "url": "https://www.bcb.gov.br"}]}
pf = _prefixos_do_hub(hub)
assert _dentro("https://www.gov.br/receitafederal/pt-br/iof", pf)
assert not _dentro("https://www.gov.br/procon-mt/iof", pf)
assert _dentro("https://www2.bcb.gov.br/x", pf)
procon = {"fonte_url": "https://www.gov.br/procon-mt/iof"}
assert not _fato_confiavel(procon, [{"url": procon["fonte_url"]}], ["gov.br"], pf)
hoje = datetime(2026, 10, 20)
assert not _recente({"data": "2020"}, [], hoje)
assert _recente({"data": "2025"}, [], hoje) and _recente({"data": ""}, [], hoje)
pagina = [{"url": "https://a/b", "texto": "Em 2020 o IOF era de 6,38%."}]
assert not _recente({"fonte_url": "https://a/b"}, pagina, hoje)

print("guias: ok")
