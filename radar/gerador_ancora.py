"""Textos ancora do doll: guias de servico evergreen, ancorados SO' no dado.

Diferente do gerador_dolar (que e' a noticia do dia, com data), estes sao
paginas permanentes — os destinos que os artigos-satelite do radar linkam.
Mesma regra dura: nada aqui e' interpretado ou apurado de terceiro; tudo sai
da base de cotacoes e do IOF do config. O que muda ao republicar sao os
numeros; a pagina e' a mesma (referencia fixa por guia).
"""
from __future__ import annotations

import json
from datetime import date, datetime

from .gerador_dolar import brl, pct

VALORES_TABELA = [100, 500, 1000, 5000, 10000]


def _resumo_da_serie(serie: list[dict]) -> dict:
    """Os numeros que todo guia usa, derivados da serie (ordem crescente)."""
    venda = serie[-1]["venda"]
    compra = serie[-1]["compra"]
    janela = [l["venda"] for l in serie]
    maior, menor = (max(janela), min(janela)) if janela else (venda, venda)
    var_janela = ((venda / janela[0] - 1) * 100) if len(janela) >= 2 else None
    return {"venda": venda, "compra": compra, "maior": maior, "menor": menor,
            "var_janela": var_janela, "n": len(janela),
            "data": serie[-1]["data"]}


def _jsonld(titulo: str, tipo_schema: str, site: dict) -> str:
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    return json.dumps({
        "@context": "https://schema.org",
        "@type": tipo_schema,
        "headline": titulo,
        "dateModified": agora,
        "inLanguage": site.get("idioma", "pt-BR"),
        "isAccessibleForFree": True,
        "publisher": {"@type": "NewsMediaOrganization", "name": site["entidade"]},
    }, ensure_ascii=False, indent=2)


def guia_comprar_dolar(serie: list[dict], site: dict) -> dict:
    """Hub 'cotacao': quanto custa comprar dolar hoje, com tabela e IOF."""
    r = _resumo_da_serie(serie)
    venda = r["venda"]
    iof = float(site.get("iof", {}).get("cartao_credito", 3.5))
    d: date = r["data"]

    titulo = "Quanto custa comprar dólar hoje: tabela de conversão e IOF"
    resumo = (f"Pela PTAX de venda de {brl(venda, 4)}, US$ 1.000 saem por "
              f"{brl(1000 * venda)} antes de taxas — e {brl(1000 * venda * (1 + iof / 100))} "
              f"na compra com cartão, já com o IOF de {pct(iof)}.")

    linhas = "\n".join(
        f"| US$ {v:,.0f}".replace(",", ".") +
        f" | {brl(v * venda)} | {brl(v * venda * (1 + iof / 100))} |"
        for v in VALORES_TABELA)

    markdown = f"""# {titulo}

{resumo}

## A conta, valor a valor

A tabela abaixo converte pela **PTAX de venda** do Banco Central e mostra
quanto o mesmo valor fica **no cartão de crédito**, onde incide {pct(iof)} de
IOF sobre o montante convertido.

| Valor em dólar | Pela PTAX | No cartão (IOF {pct(iof)}) |
|---|---|---|
{linhas}

*Cálculo próprio sobre a PTAX de venda de {brl(venda, 4)} ({d:%d/%m/%Y}). A PTAX
é a taxa de referência do Banco Central — casas de câmbio e bancos somam a ela um
spread próprio, que não entra nesta conta.*

## PTAX ou preço de balcão: qual é qual

A **PTAX** é a média das operações do mercado interbancário, calculada pelo
Banco Central e divulgada em torno das 13h10 de cada dia útil. É a referência
oficial — a base de contratos e conversões. O **preço de balcão**, o que você
paga na casa de câmbio, soma a essa referência o spread da instituição e os
tributos. Por isso o balcão fica sempre acima da PTAX.

## Perguntas frequentes

**Por que o valor no cartão é maior que a PTAX?**
Porque sobre a compra com cartão de crédito incide {pct(iof)} de IOF, além do
spread do banco. A tabela acima já mostra o efeito do IOF; o spread varia por
instituição.

**A PTAX muda durante o dia?**
A PTAX de fechamento sai uma vez por dia útil, em torno das 13h10. Ao longo do
dia o dólar de mercado oscila, mas a referência oficial é a PTAX divulgada.

**Onde vejo a cotação atualizada?**
Todo dia útil publicamos o fechamento da PTAX com a variação do dia.

---

**Fonte:** [Banco Central do Brasil — PTAX](https://www.bcb.gov.br/estabilidadefinanceira/historicocotacoes)
"""
    return {"titulo": titulo, "markdown": markdown, "resumo": resumo,
            "jsonld": _jsonld(titulo, "Article", site), "hub": "cotacao",
            "referencia": "guia-comprar-dolar"}


def guia_viagem(serie: list[dict], site: dict) -> dict:
    """Hub 'viagem': cartao x especie x pre-pago, com IOF de cada um."""
    r = _resumo_da_serie(serie)
    venda = r["venda"]
    iof_cartao = float(site.get("iof", {}).get("cartao_credito", 3.5))
    iof_especie = float(site.get("iof", {}).get("especie", 3.5))
    d: date = r["data"]

    def com(iof):
        return brl(1000 * venda * (1 + iof / 100))

    titulo = "Dólar para viagem: cartão, espécie ou pré-pago — o que sai mais barato"
    resumo = (f"Com a PTAX de venda em {brl(venda, 4)}, US$ 1.000 na viagem "
              f"custam cerca de {com(iof_cartao)} no cartão de crédito e "
              f"{com(iof_especie)} em espécie, já com o IOF de cada um.")

    markdown = f"""# {titulo}

{resumo}

## O IOF de cada forma de levar dólar

O que separa as opções não é só a cotação — é o **IOF**, que muda conforme a
forma de pagamento. Sobre a PTAX de venda de hoje ({brl(venda, 4)}), US$ 1.000
ficam assim:

| Forma | IOF | Custo de US$ 1.000 |
|---|---|---|
| Cartão de crédito | {pct(iof_cartao)} | {com(iof_cartao)} |
| Espécie (papel-moeda) | {pct(iof_especie)} | {com(iof_especie)} |

*Cálculo próprio sobre a PTAX de venda de {brl(venda, 4)} ({d:%d/%m/%Y}). Os
valores usam a PTAX como referência; a casa de câmbio soma o próprio spread, que
varia e não entra nesta conta.*

## Como escolher

A conta acima mostra o **IOF**, que é fixo por decreto e igual para todos. A
diferença de verdade, na prática, está no **spread** que cada casa de câmbio,
banco ou cartão aplica sobre a PTAX — e esse você só descobre comparando na
hora. A dica derivável dos números: quanto menor o spread sobre a PTAX de
{brl(venda, 4)}, mais perto do valor da tabela você paga.

## Perguntas frequentes

**O IOF de viagem muda?**
Sim — é definido por decreto e pode ser alterado pelo governo. Os valores desta
página são atualizados quando a alíquota muda; confira sempre a data.

**Vale a pena levar em espécie?**
Depende do spread da casa de câmbio no dia. A tabela isola o efeito do IOF; o
que decide no fim é onde você compra.

---

**Fonte:** [Banco Central do Brasil — PTAX](https://www.bcb.gov.br/estabilidadefinanceira/historicocotacoes)
"""
    return {"titulo": titulo, "markdown": markdown, "resumo": resumo,
            "jsonld": _jsonld(titulo, "Article", site), "hub": "viagem",
            "referencia": "guia-viagem"}


# Os guias que o doll publica como paginas ancora. Adicionar um guia = uma
# funcao nova aqui; o fluxo em ancoras.py cuida do resto.
GUIAS = [guia_comprar_dolar, guia_viagem]


def monta_ancoras(serie: list[dict], site: dict) -> list[dict]:
    return [g(serie, site) for g in GUIAS]
