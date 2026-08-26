"""Cliente da PTAX do Banco Central (API Olinda) — fonte primaria do site doll.

A PTAX de fechamento sai em torno de 13h10 (Brasilia) em dia util. Nao existe
cotacao em fim de semana e feriado bancario: nesses dias a API devolve lista
vazia, e isso NAO e' erro — e' o comportamento correto.

Pegadinha conhecida da Olinda: a documentacao e os exemplos divergem sobre o
formato da data (MM-DD-AAAA x DD-MM-AAAA). Por isso tentamos os dois e so'
aceitamos a resposta cuja data bater com a que pedimos.
"""
from __future__ import annotations

from datetime import date, datetime

import requests

BASE = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoDolarDia(dataCotacao=@dataCotacao)")
PERIODO = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
           "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinal=@dataFinal)")
CABECALHO = {"User-Agent": "RadarPautas/1.0 (+contato@exemplo.com.br)"}


class SemCotacao(Exception):
    """Dia sem PTAX (fim de semana, feriado) ou boletim ainda nao publicado."""


def _interpreta(bruto: dict) -> list[dict]:
    linhas = []
    for v in bruto.get("value", []):
        try:
            quando = datetime.fromisoformat(v["dataHoraCotacao"])
        except (KeyError, ValueError):
            continue
        linhas.append({
            "data": quando.date(),
            "hora": quando,
            "compra": float(v["cotacaoCompra"]),
            "venda": float(v["cotacaoVenda"]),
        })
    return linhas


def cotacao_do_dia(dia: date) -> dict:
    """Devolve {data, hora, compra, venda} do dia pedido. Levanta SemCotacao."""
    for formato in ("%m-%d-%Y", "%d-%m-%Y"):
        url = (f"{BASE}?@dataCotacao='{dia.strftime(formato)}'"
               f"&$top=1&$format=json")
        r = requests.get(url, headers=CABECALHO, timeout=20)
        # Erro HTTP num formato de data nao encerra a busca: o outro ainda vale.
        if r.status_code != 200:
            continue
        linhas = _interpreta(r.json())
        # So' aceita se a data devolvida for a que pedimos: e' o que descarta
        # a interpretacao errada do formato (12-08 lido como 8 de dezembro).
        if linhas and linhas[0]["data"] == dia:
            return linhas[0]
    raise SemCotacao(f"sem PTAX publicada para {dia.isoformat()}")


def cotacoes_do_periodo(inicio: date, fim: date) -> list[dict]:
    """Serie do periodo — usada para carregar o historico inicial da base."""
    for formato in ("%m-%d-%Y", "%d-%m-%Y"):
        url = (f"{PERIODO}?@dataInicial='{inicio.strftime(formato)}'"
               f"&@dataFinal='{fim.strftime(formato)}'&$format=json")
        r = requests.get(url, headers=CABECALHO, timeout=30)
        if r.status_code != 200:
            continue
        linhas = _interpreta(r.json())
        if linhas and inicio <= linhas[0]["data"] <= fim:
            return sorted(linhas, key=lambda x: x["data"])
    raise SemCotacao(f"sem serie entre {inicio} e {fim}")
