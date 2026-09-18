"""Garante a linha de `metas` de cada site do sites.yaml.

    python -m radar.configurar_metas --seco     # mostra o que faria
    python -m radar.configurar_metas            # aplica

Sem linha em `metas`, `selecao.py` devolve 0 na primeira instrucao: o site
coleta pautas que ficam eternamente 'nova' e nenhuma esteira publica nada.
Foi exatamente o que segurou os 5 blogs Tihee em 18/09/2026 — a coleta estava
perfeita, a fila enchia, e nada saia.

Idempotente e NAO destrutivo: meta que ja' existe fica como esta' (a
pautas_por_dia e os criterios sao governados na aba Radar do conteudo.tihee, e
um configurador nao pode desfazer decisao editorial). So' preenche `wp_url`
quando esta' vazio, porque ele e' derivado do proprio sites.yaml.

Rodar depois de adicionar site novo. Site novo passa a ser: um bloco no
sites.yaml + este comando.
"""
from __future__ import annotations

import argparse
import sys

from .banco import Banco
from .config import carrega_sites

# Ponto de partida conservador para site novo; a aba Radar ajusta depois.
PAUTAS_POR_DIA_PADRAO = 3


def wp_url_de(site: dict) -> str | None:
    """A URL publica do site: a do bloco wordpress, senao o dominio.

    Alimenta o contador "ja' saiu hoje" da aba Radar (X-WP-Total do endpoint
    publico do WP) — funciona mesmo em site sem credencial configurada."""
    wp = site.get("wordpress") or {}
    if wp.get("url"):
        return str(wp["url"]).rstrip("/")
    dominio = site.get("dominio")
    return f"https://{dominio}" if dominio else None


def main() -> int:
    p = argparse.ArgumentParser(description="Metas dos sites do radar")
    p.add_argument("--site", help="so' esse site (id em config/sites.yaml)")
    p.add_argument("--pautas-por-dia", type=int, default=PAUTAS_POR_DIA_PADRAO,
                   help=f"meta das linhas NOVAS (padrao {PAUTAS_POR_DIA_PADRAO})")
    p.add_argument("--seco", action="store_true", help="nao grava nada")
    args = p.parse_args()

    sites = carrega_sites()
    if args.site:
        if args.site not in sites:
            print(f"Site '{args.site}' nao existe em config/sites.yaml")
            return 1
        sites = {args.site: sites[args.site]}

    banco = Banco(seco=args.seco)
    contagem: dict[str, int] = {}
    for nome, cfg in sites.items():
        try:
            resultado = banco.garante_meta(nome, args.pautas_por_dia, wp_url_de(cfg))
        except Exception as erro:
            print(f"  {nome}: FALHOU — {erro}")
            contagem["erro"] = contagem.get("erro", 0) + 1
            continue
        contagem[resultado] = contagem.get(resultado, 0) + 1
        print(f"  {nome:18} {resultado}")

    print("\n" + ", ".join(f"{n} {k}" for k, n in sorted(contagem.items())))
    if contagem.get("criada"):
        print("Meta criada: a selecao automatica passa a rodar no proximo "
              "ciclo do radar.")
    return 1 if contagem.get("erro") else 0


if __name__ == "__main__":
    sys.exit(main())
