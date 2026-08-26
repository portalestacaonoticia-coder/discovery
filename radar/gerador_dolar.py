"""Monta o artigo diario de cotacao a partir do dado — e SO' do dado.

Regra dura deste gerador: ele nao explica causa. "O dolar subiu porque o Fed
sinalizou..." e' interpretacao, e interpretacao inventada por robo vira erro
factual assinado por voce. Tudo que sai daqui e' derivavel da serie: valor,
variacao, extremos, conversao, IOF. A leitura do 'porque' fica para o rascunho
humano ou para a materia de consequencia do dia seguinte.
"""
from __future__ import annotations

import json
from datetime import date, datetime

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

VALORES_TABELA = [100, 500, 1000, 5000]


def pct(valor: float, casas: int = 2) -> str:
    """Percentual no padrao brasileiro: virgula decimal."""
    return f"{valor:.{casas}f}".replace(".", ",") + "%"


def brl(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _rumo(pct: float) -> str:
    if pct > 0.005:
        return "alta"
    if pct < -0.005:
        return "queda"
    return "estabilidade"


def monta(hoje: dict, serie: list[dict], site: dict) -> dict:
    """hoje = {data, hora, compra, venda}; serie = ultimos N dias (ordem crescente).
    Devolve {titulo, markdown, jsonld, resumo}."""
    venda = hoje["venda"]
    d: date = hoje["data"]
    iof = float(site.get("iof", {}).get("cartao_credito", 3.5))

    anterior = serie[-2]["venda"] if len(serie) >= 2 else None
    var_dia = ((venda / anterior - 1) * 100) if anterior else None
    janela = [linha["venda"] for linha in serie]
    var_janela = ((venda / janela[0] - 1) * 100) if len(janela) >= 2 else None
    maior, menor = (max(janela), min(janela)) if janela else (venda, venda)

    # Como descrever o fechamento dentro da faixa do periodo, sem frase boba
    # do tipo "100% acima da minima" quando hoje e' o proprio topo.
    if venda >= maior:
        posicao = f"O fechamento de hoje é o mais alto do período."
    elif venda <= menor:
        posicao = f"O fechamento de hoje é o mais baixo do período."
    else:
        faixa = (venda - menor) / (maior - menor) * 100
        posicao = (f"O fechamento de hoje está {pct(faixa, 0)} acima da mínima "
                   f"do período.")

    dia_semana = DIAS[d.weekday()]
    data_extenso = f"{d.day} de {MESES[d.month - 1]} de {d.year}"

    if var_dia is not None:
        titulo = (f"Dólar fecha em {brl(venda, 4)} nesta {dia_semana} ({d:%d/%m}), "
                  f"{_rumo(var_dia)} de {pct(abs(var_dia))}")
    else:
        titulo = f"Dólar fecha em {brl(venda, 4)} nesta {dia_semana} ({d:%d/%m})"
    titulo = titulo[:110]

    # Bloco-resposta: autossuficiente, com numero, data e fonte.
    resposta = (
        f"A PTAX de venda do dólar fechou em {brl(venda, 4)} em {data_extenso}, "
        f"segundo o Banco Central"
        + (f" — {_rumo(var_dia)} de {pct(abs(var_dia))} ante o pregão anterior"
           if var_dia is not None else "")
        + (f". Nos últimos {len(janela)} pregões, a moeda acumula "
           f"{'alta' if var_janela and var_janela > 0 else 'queda'} de "
           f"{pct(abs(var_janela))}" if var_janela is not None else "")
        + f". A cotação de compra ficou em {brl(hoje['compra'], 4)}."
    )

    linhas_tabela = "\n".join(
        f"| US$ {v:,.0f}".replace(",", ".") +
        f" | {brl(v * venda)} | {brl(v * venda * (1 + iof / 100))} |"
        for v in VALORES_TABELA
    )

    markdown = f"""# {titulo}

*Publicado em {data_extenso}, com base na PTAX de fechamento do Banco Central.*

{resposta}

## Quanto custa comprar dólar hoje?

Pela PTAX de venda de {brl(venda, 4)}, US$ 1.000 equivalem a {brl(1000 * venda)}
antes de qualquer taxa. Na compra com cartão de crédito, incide {pct(iof)} de IOF
sobre o valor convertido — e casas de câmbio e bancos aplicam spread próprio, que
não entra nesta conta.

| Valor em dólar | Pela PTAX | No cartão (com IOF de {pct(iof)}) |
|---|---|---|
{linhas_tabela}

*Cálculo próprio sobre a PTAX de venda de {d:%d/%m/%Y}. A PTAX é a taxa de
referência do Banco Central, não o preço de balcão: ela serve de parâmetro, e o
valor que você paga inclui o spread da instituição.*

## Qual foi a variação recente?

Nos últimos {len(janela)} pregões, a PTAX de venda oscilou entre {brl(menor, 4)} e {brl(maior, 4)}. {posicao}

## Perguntas frequentes

**O que é a PTAX?**
É a taxa média de câmbio do dia calculada pelo Banco Central a partir das
operações do mercado interbancário. Serve de referência para contratos e para
conversões oficiais, e é divulgada em torno das 13h10 de cada dia útil.

**A PTAX é o valor que eu pago na casa de câmbio?**
Não. A PTAX é referência. O preço ao consumidor soma o spread da instituição e
os tributos aplicáveis, e por isso fica acima dela.

**Por que não há cotação no fim de semana?**
A PTAX só é apurada em dias úteis bancários. Em sábados, domingos e feriados o
Banco Central não divulga boletim.

---

**Fonte:** [Banco Central do Brasil — PTAX]\
(https://www.bcb.gov.br/estabilidadefinanceira/historicocotacoes)
"""

    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    jsonld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": titulo,
        "datePublished": agora,
        "dateModified": agora,
        "inLanguage": site.get("idioma", "pt-BR"),
        "isAccessibleForFree": True,
        "publisher": {"@type": "NewsMediaOrganization", "name": site["entidade"]},
        "about": {"@type": "Thing", "name": "Cotação do dólar"},
    }

    return {"titulo": titulo, "markdown": markdown, "resumo": resposta,
            "jsonld": json.dumps(jsonld, ensure_ascii=False, indent=2)}
