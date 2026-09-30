"""Motor Discover: sinais -> topicos -> DiscoverScore (-> angulo -> pesquisa
-> brief, nas proximas etapas).

    python -m radar.motor --seco --site broune     # ensaio: coleta, agrupa, pontua, imprime
    python -m radar.motor                          # todos os sites com motor: discover

Roda so' para sites com `motor: discover` no config/sites.yaml. O
radar.principal chama `roda_site_discover` para esses sites a cada rodada,
depois do pipeline antigo (modo sombra da Etapa 1: os dois convivem ate o
motor novo cobrir a escrita).

Plano de producao (metas.pautas_por_dia + producao_inicio/fim): fora do
periodo nada pago roda — nem SerpAPI, nem Reddit/YouTube, nem modelo. So' o
RSS gratis, para o historico de topicos continuar.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import sinais as mod_sinais
from .alerta import avisa
from .banco import Banco
from .config import carrega_sites
from .oportunidade import (avisos_de_producao, componentes, criterios_discover,
                           em_producao, pontua_topico, seleciona_topicos)
from .selecao import FUSO_SP, inicio_do_dia_sp
from .tendencias import agrupa_topicos, funde_com_historico

# Quantos topicos por hub ficam gravados por rodada (os demais sao ruido).
TOPICOS_GRAVADOS_POR_HUB = 8


def sites_discover(todos: dict) -> dict:
    return {nome: cfg for nome, cfg in todos.items() if cfg.get("motor") == "discover"}


def roda_site_discover(nome: str, site: dict, banco: Banco, seco: bool = False,
                       agora: datetime | None = None) -> dict:
    """Etapa 1: coleta os sinais de cada hub, agrupa em topicos, pontua e
    grava. Devolve o resumo com os melhores topicos do site."""
    agora = agora or datetime.now(timezone.utc)
    hoje_sp = agora.astimezone(FUSO_SP).date()
    inicio = agora
    mod_sinais.limpa_falhas()

    meta = banco.meta_do_site(nome) or {}
    criterios = criterios_discover(meta.get("criterios"))
    produzindo, motivo_prod = em_producao(meta, hoje_sp)
    print(f"\n=== {nome} · motor discover ({motivo_prod}) ===")

    # Avisos de entrada/saida do periodo: uma vez por dia, na primeira rodada.
    if not seco and not banco.execucao_hoje("discover", nome, inicio_do_dia_sp()):
        for msg in avisos_de_producao(meta, hoje_sp):
            avisa(f"**{nome}**: {msg}")

    total_sinais = total_topicos = 0
    melhores: list[dict] = []
    for hub in site.get("hubs", []) or []:
        print(f"  [{hub['id']}]")
        novos = mod_sinais.coleta_sinais(nome, site, hub, banco, agora, pagas=produzindo)
        total_sinais += len(novos)

        recentes = banco.sinais_recentes(nome, hub["id"], dias=30)
        topicos = agrupa_topicos(recentes, hub, agora)
        funde_com_historico(topicos, banco.topicos_recentes(nome, hub["id"], dias=7))
        historico = banco.artigos_publicados_do_hub(nome, hub["id"])
        for t in topicos:
            comp = componentes(t, hub, site, historico, agora)
            t["componentes"] = comp
            t["pontuacao"], t["motivo"] = pontua_topico(t, comp, criterios)
        topicos.sort(key=lambda t: t["pontuacao"], reverse=True)

        for t in topicos[:TOPICOS_GRAVADOS_POR_HUB]:
            t["id"] = banco.grava_topico({
                "site": nome, "hub": hub["id"], "chave": t["chave"],
                "rotulo": t["rotulo"], "termos": t["termos"],
                "sinais": {"total": t["total_sinais"], "por_tipo": t["por_tipo"],
                           "ids": t["sinais_ids"][:200],
                           "veiculos_24h": t["veiculos_24h"], "veiculos_7d": t["veiculos_7d"],
                           "veiculos_30d": t["veiculos_30d"],
                           "perguntas": t["perguntas"], "relacionadas": t["relacionadas"],
                           "manchetes": t["manchetes"], "organicos": t["organicos"],
                           "social": t["social"], "trend_rising": t["trend_rising"],
                           "trend_top": t["trend_top"]},
                "componentes": t["componentes"], "pontuacao": t["pontuacao"],
                "motivo": t["motivo"], "primeiro_visto": t["primeiro_visto"],
                "ultimo_visto": t["ultimo_visto"], "dia": hoje_sp.isoformat(),
                "status": "pautado" if t.get("ja_pautado") else "novo",
                "pauta_id": t.get("pauta_id"),
            })
        total_topicos += len(topicos)
        for t in topicos[:3]:
            print(f"    {t['pontuacao']:3} pts  {t['rotulo'][:70]}  ({t['motivo']})")
        melhores.extend(topicos[:TOPICOS_GRAVADOS_POR_HUB])

    candidatos = seleciona_topicos(melhores, criterios)
    if candidatos:
        print(f"  candidatos a pauta (acima de {criterios['minimo']} pts): "
              + "; ".join(f"{t['pontuacao']} {t['rotulo'][:40]}" for t in candidatos))
    else:
        print(f"  nenhum topico acima do piso ({criterios['minimo']} pts)")

    resumo = (f"{total_sinais} sinais novos, {total_topicos} topicos, "
              f"{len(candidatos)} candidatos"
              + ("" if produzindo else f" — {motivo_prod}")
              + mod_sinais.resumo_falhas())
    if not seco:
        banco.registra_execucao({"fluxo": "discover", "site": nome, "status": "ok",
                                 "resumo": resumo[:500], "inicio": inicio.isoformat()})
    return {"site": nome, "sinais": total_sinais, "topicos": total_topicos,
            "candidatos": candidatos, "produzindo": produzindo}


def main() -> int:
    p = argparse.ArgumentParser(description="Motor Discover (sinais, topicos, pontuacao)")
    p.add_argument("--site", help="roda so' esse site (precisa ter motor: discover)")
    p.add_argument("--seco", action="store_true", help="nao grava nada, so' imprime")
    args = p.parse_args()

    sites = sites_discover(carrega_sites())
    if args.site:
        if args.site not in sites:
            print(f"Site '{args.site}' nao tem motor: discover no config/sites.yaml")
            return 1
        sites = {args.site: sites[args.site]}
    if not sites:
        print("Nenhum site com motor: discover")
        return 0

    banco = Banco(seco=args.seco)
    falhas = 0
    linhas = []
    for nome, cfg in sites.items():
        try:
            r = roda_site_discover(nome, cfg, banco, seco=args.seco)
        except Exception as erro:
            print(f"  {nome} falhou: {erro}")
            falhas += 1
            if not args.seco:
                banco.registra_execucao({"fluxo": "discover", "site": nome, "status": "erro",
                                         "resumo": str(erro)[:500],
                                         "inicio": datetime.now(timezone.utc).isoformat()})
            continue
        top = "; ".join(f"{t['pontuacao']} {t['rotulo'][:40]}" for t in r["candidatos"][:5])
        linhas.append(f"• {nome}: {r['sinais']} sinais, {r['topicos']} topicos"
                      + (f" — {top}" if top else ""))
    if linhas and not args.seco:
        avisa("**Motor Discover**\n" + "\n".join(linhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
