"""Publica os textos ancora do doll — as paginas de servico permanentes.

    python -m radar.ancoras --seco   # monta e imprime, nao grava nem publica
    python -m radar.ancoras          # gera, grava e publica/atualiza no WP

Idempotente: cada guia tem referencia fixa, entao rodar de novo ATUALIZA a
mesma pagina (numeros do dia) em vez de criar outra. Sao dado proprio
verificavel — publicam sozinhos, como o artigo diario do dolar.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from .alerta import avisa
from .banco import Banco
from .config import RAIZ, carrega_sites
from .gerador_ancora import monta_ancoras

SITE = "doll"
SAIDA = RAIZ / "saida"


def main() -> int:
    p = argparse.ArgumentParser(description="Textos ancora (guias de servico) do doll")
    p.add_argument("--seco", action="store_true", help="nao grava nem publica")
    p.add_argument("--sem-publicar", action="store_true",
                   help="gera e grava, mas nao manda para o WordPress")
    args = p.parse_args()

    site = carrega_sites()[SITE]
    banco = Banco(seco=args.seco)
    inicio = datetime.now(timezone.utc)

    # A serie e' leitura read-only: le do banco real mesmo em modo seco, senao
    # nao haveria numero para o guia — o --seco so' segura gravacao e publicacao.
    leitor = banco if not args.seco else Banco(seco=False)
    serie = leitor.serie_cotacoes(SITE, dias=30)
    if len(serie) < 2:
        print("serie de cotacoes insuficiente — rode o historico primeiro "
              "(python -m radar.dolar_diario --historico 90)")
        return 1

    ancoras = monta_ancoras(serie, site)
    SAIDA.mkdir(exist_ok=True)
    pode_publicar = site["publicacao"].get("calendario") == "auto"
    publicados = 0

    for a in ancoras:
        (SAIDA / f"{SITE}-{a['referencia']}.md").write_text(a["markdown"], encoding="utf-8")
        # Nasce 'aprovada'; so' vira 'publicada' quando o WP confirmar (mesma
        # regra honesta do artigo do dolar).
        status = "aprovada" if pode_publicar else "rascunho"
        banco.grava_artigo({
            "site": SITE, "tipo": "ancora", "hub": a["hub"],
            "titulo": a["titulo"], "resumo": a["resumo"],
            "corpo_md": a["markdown"], "jsonld": a["jsonld"],
            "status": status, "motivo_portao": "texto ancora (dado proprio)",
            "referencia": a["referencia"],
        })

        if args.seco:
            print(f"[seco] {a['referencia']}: {a['titulo']}")
            continue
        print(f"[{status}] {a['titulo']}  (saida/{SITE}-{a['referencia']}.md)")

        wp = site.get("wordpress")
        if wp and not args.sem_publicar and pode_publicar:
            from .publicador_wp import ErroWordPress, publica
            existente = banco.artigo_existente(SITE, "ancora", a["referencia"])
            try:
                resultado = publica({
                    "titulo": a["titulo"], "corpo_md": a["markdown"],
                    "resumo": a["resumo"], "jsonld": a["jsonld"],
                    "status": "publicada", "hub": a["hub"],
                    "wp_post_id": (existente or {}).get("wp_post_id"),
                }, {**wp,
                    "usuario": os.environ[wp["usuario_env"]],
                    "senha_app": os.environ[wp["senha_env"]]})
                banco.marca_publicado(SITE, "ancora", a["referencia"],
                                      resultado["id"], resultado.get("link"),
                                      "publicada")
                publicados += 1
                print(f"  no ar: {resultado.get('link')}")
            except (ErroWordPress, KeyError) as erro:
                print(f"  falha ao publicar {a['referencia']}: {erro}")

    if args.seco:
        # No modo seco, mostra um guia inteiro para conferir a qualidade.
        print("\n" + "=" * 70 + "\n" + ancoras[0]["markdown"])
    else:
        banco.registra_execucao({
            "fluxo": "ancoras", "site": SITE, "status": "ok",
            "resumo": f"{publicados}/{len(ancoras)} guias no ar",
            "inicio": inicio.isoformat(),
        })
        if publicados:
            avisa(f"**doll — textos ancora** {publicados}/{len(ancoras)} atualizados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
