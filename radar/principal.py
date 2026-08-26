"""Orquestrador. Roda por site: coleta -> deduplica -> classifica -> gera pautas.

Uso:
    python -m radar.principal --seco                 # testa sem gravar nada
    python -m radar.principal --site ferrugem        # so' um site
    python -m radar.principal                        # todos os sites do sites.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from .alerta import avisa
from .banco import Banco
from .classifica import avalia, sugere
from .config import carrega_sites
from .fontes import coleta
from .normaliza import canoniza_url, hash_dedup, sem_acento, veiculo_de

LIMITE_POR_FONTE = 40


def detecta_cidade(titulo: str, cidades: list[str]) -> str | None:
    """Cidade citada no titulo, comparando com as que a base ja conhece.
    Base vazia -> nenhuma cidade detectada -> nenhum angulo de contagem.
    E' de proposito: sem historico proprio, nao ha' dado proprio a oferecer."""
    alvo = sem_acento(titulo.lower())
    for cidade in sorted(cidades, key=len, reverse=True):
        if sem_acento(cidade.lower()) in alvo:
            return cidade
    return None


def dado_proprio(banco: Banco, nome_site: str, site: dict, titulo: str,
                 leitura: dict) -> dict | None:
    """Busca na base do site o numero que justifica o artigo existir."""
    base = site.get("base")

    if base == "eventos":
        cidade = leitura.get("lugar") or detecta_cidade(
            titulo, banco.cidades_conhecidas(nome_site))
        if not cidade:
            return None
        total = banco.conta_eventos_na_cidade(nome_site, cidade)
        if total <= 0:
            return None
        ultimo = banco.ultimo_evento_na_cidade(nome_site, cidade)
        leitura["lugar"] = cidade
        curto = f"{total + 1}ª"
        detalhe = (f"ultima vez em {ultimo['data']}, {ultimo.get('local') or 'local nao informado'}"
                   if ultimo else "sem registro anterior de local")
        return {"curto": curto,
                "detalhe": detalhe,
                "texto": f"{total} shows registrados em {cidade}; este e' o {curto}. {detalhe}."}

    if base == "cotacoes":
        v = banco.variacao_cotacao(nome_site)
        if not v:
            return None
        curto = f"{v['variacao_pct']:+.2f}% em {v['dias']} dias"
        return {"curto": curto,
                "detalhe": f"maior R$ {v['maior']:.4f}, menor R$ {v['menor']:.4f}",
                "texto": (f"PTAX de venda em R$ {v['atual']:.4f}; {curto}. "
                          f"maior R$ {v['maior']:.4f}, menor R$ {v['menor']:.4f}.")}

    return None


def roda_site(nome: str, site: dict, banco: Banco) -> dict:
    print(f"\n=== {nome} ({site['dominio']}) ===")
    novos = pautas = 0

    for fonte in site.get("fontes", []):
        try:
            itens = coleta(fonte)[:LIMITE_POR_FONTE]
        except Exception as erro:
            print(f"  fonte {fonte} falhou: {erro}")
            continue

        for cru in itens:
            h = hash_dedup(cru["titulo"], cru.get("publicado_em"))
            if banco.item_existe(nome, h):
                continue

            leitura = avalia(cru["titulo"], cru.get("resumo", ""), site)
            if not leitura["relevante"]:
                continue

            item_id = banco.grava_item({
                "site": nome,
                "titulo": cru["titulo"],
                "url": cru["url"],
                "url_canonica": canoniza_url(cru["url"]),
                "hash_dedup": h,
                "veiculo": veiculo_de(cru["url"]),
                "resumo": (cru.get("resumo") or "")[:500],
                "publicado_em": cru["publicado_em"].isoformat() if cru.get("publicado_em") else None,
            })
            novos += 1

            dado = dado_proprio(banco, nome, site, cru["titulo"], leitura)
            for sugestao in sugere(cru["titulo"], leitura, dado, site):
                banco.grava_pauta({
                    "item_id": item_id,
                    "site": nome,
                    "hub": leitura.get("hub"),
                    "tipo": "radar",
                    "status": "nova",
                    **sugestao,
                })
                pautas += 1

    print(f"  {novos} itens novos, {pautas} pautas geradas")
    return {"site": nome, "itens": novos, "pautas": pautas}


def main() -> int:
    p = argparse.ArgumentParser(description="Radar de pautas")
    p.add_argument("--site", help="roda so' esse site (id em config/sites.yaml)")
    p.add_argument("--seco", action="store_true", help="nao grava nada, so' imprime")
    args = p.parse_args()

    sites = carrega_sites()
    if args.site:
        if args.site not in sites:
            print(f"Site '{args.site}' nao existe em config/sites.yaml")
            return 1
        sites = {args.site: sites[args.site]}

    banco = Banco(seco=args.seco)
    resumo = []
    falhas = 0
    for nome, cfg in sites.items():
        inicio = datetime.now(timezone.utc)
        try:
            r = roda_site(nome, cfg, banco)
        except Exception as erro:
            # Um site quebrado nao derruba a rodada dos outros: o painel mostra
            # o erro e a saida != 0 marca a execucao no Actions.
            print(f"  {nome} falhou: {erro}")
            falhas += 1
            banco.registra_execucao({
                "fluxo": "radar", "site": nome, "status": "erro",
                "resumo": str(erro)[:500], "inicio": inicio.isoformat(),
            })
            continue
        resumo.append(r)
        banco.registra_execucao({
            "fluxo": "radar", "site": nome, "status": "ok",
            "resumo": f"{r['itens']} itens novos, {r['pautas']} pautas",
            "inicio": inicio.isoformat(),
        })

    total = sum(r["pautas"] for r in resumo)
    if total and not args.seco:
        linhas = "\n".join(f"• {r['site']}: {r['itens']} itens, {r['pautas']} pautas"
                           for r in resumo if r["pautas"])
        avisa(f"**Radar de pautas**\n{linhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
