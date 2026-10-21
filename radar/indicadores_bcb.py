"""Dados oficiais do Banco Central para o dado proprio de cada categoria do
doll (21/10/2026). A PTAX do dolar continua em radar/ptax.py e na base
`cotacoes`; aqui ficam as outras series, buscadas na hora de escrever (sem
tabela nova): sao gratuitas, rapidas e o texto precisa do numero do dia.

    focus("Câmbio", 2026)   mediana do boletim Focus e a de ~4 semanas antes
    selic_meta()            meta Selic vigente e desde quando
    ipca_12m()              IPCA acumulado em 12 meses (ultimo mes divulgado)
    moeda(codigo)           PTAX de venda de outra moeda: dia, anterior e 30 dias

Falha de rede devolve None: quem chama cai no dado da cotacao (PTAX do dolar).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import requests
from urllib.parse import quote, urlencode

CABECALHO = {"User-Agent": "RadarPautas/1.0 (+contato@exemplo.com.br)"}
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
FOCUS = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
         "ExpectativasMercadoAnuais")
MOEDA = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
         "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,"
         "dataFinalCotacao=@dataFinalCotacao)")

SERIE_SELIC_META = 432
SERIE_IPCA_12M = 13522
SERIE_IPCA_MES = 433

# Moedas da categoria viagem (todas com PTAX no BC; peso argentino, chileno
# e mexicano nao tem, e o iene sai a R$ 0,03 por unidade). O euro, destino
# mais comum, entra em dia sim, dia nao no rodizio.
MOEDAS_VIAGEM = {
    "EUR": "euro", "GBP": "libra esterlina", "CAD": "dólar canadense",
    "CHF": "franco suíço", "AUD": "dólar australiano",
}
RODIZIO_VIAGEM = ["EUR", "GBP", "EUR", "CAD", "EUR", "CHF", "EUR", "AUD"]
PLURAL = {"EUR": "euros", "GBP": "libras esterlinas", "CAD": "dólares canadenses",
          "CHF": "francos suíços", "AUD": "dólares australianos"}


def _get(url: str, params: dict | None = None, prazo: int = 60):
    """GET com espacos como %20: a OData do BC recusa o '+' que o requests
    usa por padrao ("Edm.Boolean e Edm.String nao sao compativeis")."""
    if params:
        url += ("&" if "?" in url else "?") + urlencode(
            params, quote_via=quote, safe="$@'(),:/")
    try:
        r = requests.get(url, headers=CABECALHO, timeout=prazo)
        return r.json() if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def _sgs(serie: int, inicio: date, fim: date) -> list[tuple[date, float]]:
    dados = _get(SGS.format(serie=serie), {
        "formato": "json", "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": fim.strftime("%d/%m/%Y")}) or []
    linhas = []
    for d in dados if isinstance(dados, list) else []:
        try:
            linhas.append((datetime.strptime(d["data"], "%d/%m/%Y").date(),
                           float(d["valor"])))
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(linhas)


def selic_meta(hoje: date | None = None) -> dict | None:
    """{valor, desde}: a meta vigente hoje e a data em que passou a valer.
    A serie 432 traz dias futuros (meta ja' definida): corta em hoje."""
    hoje = hoje or date.today()
    serie = [x for x in _sgs(SERIE_SELIC_META, hoje - timedelta(days=500), hoje)
             if x[0] <= hoje]
    if not serie:
        return None
    valor = serie[-1][1]
    desde = serie[-1][0]
    for d, v in reversed(serie):
        if abs(v - valor) > 1e-9:
            break
        desde = d
    anterior = next((v for d, v in reversed(serie) if abs(v - valor) > 1e-9), None)
    return {"valor": valor, "desde": desde, "anterior": anterior}


def ipca_12m(hoje: date | None = None) -> dict | None:
    """{valor, referencia}: IPCA acumulado em 12 meses do ultimo mes divulgado."""
    hoje = hoje or date.today()
    serie = _sgs(SERIE_IPCA_12M, hoje - timedelta(days=200), hoje)
    if not serie:
        return None
    ref, valor = serie[-1]
    return {"valor": valor, "referencia": ref}


def ipca_mes(hoje: date | None = None) -> dict | None:
    """{valor, referencia, anterior}: IPCA do ultimo mes divulgado e o do mes
    anterior (variacao mensal, em %)."""
    hoje = hoje or date.today()
    serie = _sgs(SERIE_IPCA_MES, hoje - timedelta(days=120), hoje)
    if len(serie) < 2:
        return None
    return {"valor": serie[-1][1], "referencia": serie[-1][0], "anterior": serie[-2][1],
            "referencia_anterior": serie[-2][0]}


def focus(indicador: str, ano: int, hoje: date | None = None) -> dict | None:
    """{mediana, data, mediana_antes, data_antes}: o boletim Focus mais
    recente para o ano pedido e o de ~4 semanas antes (para a revisao).
    indicador: 'Câmbio', 'IPCA' ou 'Selic' (como a API chama)."""
    hoje = hoje or date.today()
    dados = _get(FOCUS, {
        "$filter": (f"Indicador eq '{indicador}' and DataReferencia eq '{ano}' "
                    f"and baseCalculo eq 0 and Data ge "
                    f"'{(hoje - timedelta(days=60)).isoformat()}'"),
        "$orderby": "Data desc", "$top": "40", "$format": "json",
        "$select": "Data,Mediana"})
    linhas = []
    for v in (dados or {}).get("value", []):
        try:
            linhas.append((date.fromisoformat(v["Data"]), float(v["Mediana"])))
        except (KeyError, ValueError, TypeError):
            continue
    linhas = sorted({d: m for d, m in linhas if d <= hoje}.items())
    if not linhas:
        return None
    data, mediana = linhas[-1]
    alvo = data - timedelta(days=28)
    antes = min(linhas, key=lambda x: abs((x[0] - alvo).days))
    if antes[0] == data:
        antes = (None, None)
    return {"mediana": mediana, "data": data,
            "mediana_antes": antes[1], "data_antes": antes[0]}


def moeda(codigo: str, hoje: date | None = None) -> dict | None:
    """PTAX de venda (fechamento) de outra moeda: {codigo, nome, venda, data,
    venda_anterior, var_dia, venda_30d, var_30d, menor_30d, maior_30d}."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=45)
    dados = None
    for formato in ("%m-%d-%Y", "%d-%m-%Y"):
        dados = _get(MOEDA, {
            "@moeda": f"'{codigo}'", "@dataInicial": f"'{inicio.strftime(formato)}'",
            "@dataFinalCotacao": f"'{hoje.strftime(formato)}'",
            "$format": "json", "$top": "500"})
        if dados and dados.get("value"):
            break
    linhas = []
    for v in (dados or {}).get("value", []):
        # o periodo traz Abertura/Intermediario/Fechamento: so' o fechamento
        # e' a PTAX do dia (o filtro OData por tipoBoletim volta vazio)
        if v.get("tipoBoletim") != "Fechamento":
            continue
        try:
            linhas.append((datetime.fromisoformat(v["dataHoraCotacao"]).date(),
                           float(v["cotacaoVenda"])))
        except (KeyError, ValueError, TypeError):
            continue
    linhas = sorted({d: x for d, x in linhas if inicio <= d <= hoje}.items())
    if len(linhas) < 2:
        return None
    data, venda = linhas[-1]
    anterior = linhas[-2][1]
    janela = [x for _, x in linhas[-22:]]
    base_30 = janela[0]
    return {"codigo": codigo, "nome": MOEDAS_VIAGEM.get(codigo, codigo),
            "plural": PLURAL.get(codigo, MOEDAS_VIAGEM.get(codigo, codigo) + "s"),
            "venda": venda, "data": data, "venda_anterior": anterior,
            "var_dia": (venda / anterior - 1) * 100,
            "venda_30d": base_30, "var_30d": (venda / base_30 - 1) * 100,
            "menor_30d": min(janela), "maior_30d": max(janela), "pregoes": len(janela)}


def moeda_do_dia(hoje: date | None = None, ordem: int = 0) -> str:
    """Rodizio: a moeda de viagem do dia (ordem 0) e, para o 2o satelite de
    viagem do dia (ordem 1), a proxima moeda DIFERENTE do rodizio."""
    hoje = hoje or date.today()
    i = hoje.timetuple().tm_yday % len(RODIZIO_VIAGEM)
    primeira = RODIZIO_VIAGEM[i]
    if not ordem:
        return primeira
    for passo in range(1, len(RODIZIO_VIAGEM)):
        outra = RODIZIO_VIAGEM[(i + passo) % len(RODIZIO_VIAGEM)]
        if outra != primeira:
            return outra
    return primeira
