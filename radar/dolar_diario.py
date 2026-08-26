"""Pauta de calendario do doll.com.br: PTAX do dia -> base -> artigo pronto.

    python -m radar.dolar_diario --seco            # nao grava, imprime o artigo
    python -m radar.dolar_diario                   # roda de verdade (dia de hoje)
    python -m radar.dolar_diario --data 2026-08-21
    python -m radar.dolar_diario --historico 90    # carrega a serie inicial na base

Este e' o unico caminho do projeto autorizado a publicar sozinho, e so' porque
o dado e' deterministico e vem da fonte primaria. Os portoes abaixo decidem
entre 'publicada' e 'rascunho'. Qualquer duvida cai para rascunho — nunca ao ar.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import os

from .alerta import avisa
from .banco import Banco
from .config import RAIZ, carrega_sites
from .gerador_dolar import monta
from .ptax import SemCotacao, cotacao_do_dia, cotacoes_do_periodo

SITE = "doll"
FAIXA_PLAUSIVEL = (1.0, 20.0)   # BRL por USD: fora disso, o dado esta' corrompido
SALTO_MAXIMO_PCT = 5.0          # variacao diaria acima disso pede olho humano
SAIDA = RAIZ / "saida"


def portoes(hoje: dict, serie: list[dict]) -> tuple[bool, str]:
    """Devolve (pode_publicar_sozinho, motivo). Falha grave levanta excecao."""
    piso, teto = FAIXA_PLAUSIVEL
    if not (piso <= hoje["venda"] <= teto):
        raise ValueError(f"PTAX fora da faixa plausivel: {hoje['venda']}")
    if hoje["compra"] > hoje["venda"]:
        raise ValueError("compra maior que venda: dado inconsistente")
    if hoje["data"] > date.today():
        raise ValueError("data da cotacao no futuro")

    if len(serie) >= 2:
        anterior = serie[-2]["venda"]
        salto = abs(hoje["venda"] / anterior - 1) * 100
        if salto > SALTO_MAXIMO_PCT:
            return False, f"salto de {salto:.2f}% ante o pregao anterior"
    else:
        return False, "serie historica insuficiente para calcular variacao"
    return True, "dado dentro do esperado"


def carrega_historico(banco: Banco, dias: int) -> int:
    fim = date.today()
    inicio = fim - timedelta(days=dias)
    linhas = cotacoes_do_periodo(inicio, fim)
    for linha in linhas:
        banco.grava_cotacao({
            "site": SITE, "data": linha["data"].isoformat(), "moeda": "USD",
            "ptax_compra": linha["compra"], "ptax_venda": linha["venda"],
            "fonte": "https://olinda.bcb.gov.br/olinda/servico/PTAX",
        })
    return len(linhas)


def main() -> int:
    p = argparse.ArgumentParser(description="Artigo diario de cotacao do dolar")
    p.add_argument("--data", help="AAAA-MM-DD (padrao: hoje)")
    p.add_argument("--seco", action="store_true", help="nao grava nada")
    p.add_argument("--historico", type=int, metavar="DIAS",
                   help="carrega a serie dos ultimos N dias e sai")
    p.add_argument("--sem-publicar", action="store_true",
                   help="gera e grava, mas nao manda para o WordPress")
    args = p.parse_args()

    site = carrega_sites()[SITE]
    banco = Banco(seco=args.seco)

    if args.historico:
        total = carrega_historico(banco, args.historico)
        print(f"{total} cotacoes carregadas na base")
        return 0

    dia = date.fromisoformat(args.data) if args.data else date.today()

    try:
        hoje = cotacao_do_dia(dia)
    except SemCotacao as erro:
        # Fim de semana e feriado nao sao falha: o dia simplesmente nao tem pauta.
        print(f"sem pauta hoje: {erro}")
        return 0

    banco.grava_cotacao({
        "site": SITE, "data": hoje["data"].isoformat(), "moeda": "USD",
        "ptax_compra": hoje["compra"], "ptax_venda": hoje["venda"],
        "fonte": "https://olinda.bcb.gov.br/olinda/servico/PTAX",
    })

    serie = banco.serie_cotacoes(SITE, dias=30) or [hoje]
    if serie[-1]["data"] != hoje["data"]:
        serie = serie + [hoje]

    liberado, motivo = portoes(hoje, serie)
    artigo = monta(hoje, serie, site)
    status = "publicada" if (liberado and site["publicacao"]["calendario"] == "auto") else "rascunho"

    SAIDA.mkdir(exist_ok=True)
    base_nome = f"{SITE}-cotacao-{hoje['data'].isoformat()}"
    (SAIDA / f"{base_nome}.md").write_text(artigo["markdown"], encoding="utf-8")
    (SAIDA / f"{base_nome}.jsonld").write_text(artigo["jsonld"], encoding="utf-8")

    banco.grava_artigo({
        "site": SITE, "tipo": "calendario", "hub": "cotacao",
        "titulo": artigo["titulo"], "resumo": artigo["resumo"],
        "corpo_md": artigo["markdown"], "jsonld": artigo["jsonld"],
        "status": status, "motivo_portao": motivo,
        "referencia": hoje["data"].isoformat(),
    })

    link = None
    wp = site.get("wordpress")
    if wp and not args.sem_publicar and not args.seco:
        from .publicador_wp import ErroWordPress, publica
        existente = banco.artigo_existente(SITE, "calendario", hoje["data"].isoformat())
        try:
            resultado = publica({
                "titulo": artigo["titulo"], "corpo_md": artigo["markdown"],
                "resumo": artigo["resumo"], "jsonld": artigo["jsonld"],
                "status": status, "hub": "cotacao",
                "wp_post_id": (existente or {}).get("wp_post_id"),
            }, {**wp,
                "usuario": os.environ[wp["usuario_env"]],
                "senha_app": os.environ[wp["senha_env"]]})
            banco.marca_publicado(SITE, "calendario", hoje["data"].isoformat(),
                                  resultado["id"], resultado.get("link"))
            link = resultado.get("link")
        except (ErroWordPress, KeyError) as erro:
            # Falha de publicacao nao pode perder o artigo: ele ja' esta' no banco
            # e em saida/. Avisa e sai com codigo de erro para o Actions marcar.
            avisa(f"**doll** artigo gerado mas NAO publicado: {erro}")
            print(f"falha ao publicar: {erro}")
            return 2

    print(f"[{status}] {artigo['titulo']}\n  portao: {motivo}\n  arquivo: saida/{base_nome}.md"
          + (f"\n  no ar: {link}" if link else ""))
    if args.seco:
        print("\n" + artigo["markdown"])
    else:
        avisa(f"**doll — cotacao {hoje['data']:%d/%m}** [{status}]\n{artigo['titulo']}\n_{motivo}_"
              + (f"\n{link}" if link else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
