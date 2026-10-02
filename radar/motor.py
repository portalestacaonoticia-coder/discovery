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

from . import ideias as mod_ideias, llm, sinais as mod_sinais
from .alerta import avisa
from .banco import Banco
from .config import carrega_sites, env
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
    llm.limpa_falhas()

    # No ensaio (--seco) nada e' gravado, mas a LEITURA e' real quando ha'
    # banco: metas (periodo de producao), historico de sinais/topicos e TTL
    # das fontes. Mesmo padrao do publicar.py. Sem SUPABASE_* no ambiente,
    # cai no banco seco (tudo em memoria). Atencao: em --seco a coleta nao
    # e' registrada, entao rodar o ensaio varias vezes repete a SerpAPI.
    leitor = banco
    if seco and env("SUPABASE_URL") and env("SUPABASE_SERVICE_KEY"):
        leitor = Banco(seco=False)
        print("  (ensaio: lendo o banco de verdade, sem gravar)")

    meta = leitor.meta_do_site(nome) or {}
    criterios = criterios_discover(meta.get("criterios"))
    produzindo, motivo_prod = em_producao(meta, hoje_sp)
    print(f"\n=== {nome} · motor discover ({motivo_prod}) ===")

    # Avisos de entrada/saida do periodo: uma vez por dia, na primeira rodada.
    if not seco and not banco.execucao_hoje("discover", nome, inicio_do_dia_sp()):
        for msg in avisos_de_producao(meta, hoje_sp):
            avisa(f"**{nome}**: {msg}")

    total_sinais = total_topicos = total_sugeridas = 0
    melhores: list[dict] = []
    # Pesquisa de pautas da tela Radar: so' os hubs que a pessoa ativou, com
    # os temas macro que ela escreveu como consultas de sinal. Sem lista de
    # ativos (tela nunca salva), todos os hubs entram com os padroes.
    pesquisa = criterios.get("pesquisa") or {}
    hubs_ativos = pesquisa.get("hubs_ativos") or []
    temas_por_hub = pesquisa.get("temas") or {}
    if hubs_ativos:
        print(f"  categorias ativas: {', '.join(hubs_ativos)}")

    for hub in site.get("hubs", []) or []:
        if hubs_ativos and hub["id"] not in hubs_ativos:
            continue
        print(f"  [{hub['id']}]")
        temas = [t.strip() for t in str(temas_por_hub.get(hub["id"]) or "").split(",") if t.strip()]
        novos = mod_sinais.coleta_sinais(nome, site, hub, banco, agora,
                                         pagas=produzindo, leitor=leitor, temas=temas)
        total_sinais += len(novos)

        recentes = leitor.sinais_recentes(nome, hub["id"], dias=30)
        if leitor is not banco:
            # ensaio: junta o historico do banco com o que acabou de coletar
            # (so' na memoria), sem contar o mesmo sinal duas vezes
            vistos = {(s["fonte"], s["dia"], s["hash_dedup"]) for s in recentes}
            recentes = recentes + [s for s in banco.sinais_recentes(nome, hub["id"])
                                   if (s["fonte"], s["dia"], s["hash_dedup"]) not in vistos]
        topicos = agrupa_topicos(recentes, hub, agora)
        funde_com_historico(topicos, leitor.topicos_recentes(nome, hub["id"], dias=7))
        historico = leitor.artigos_publicados_do_hub(nome, hub["id"])
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
        # Sugestoes para a tela: os melhores topicos do hub viram ideias
        # 'sugerida' (marcacao de quem ja' esta' la' e' preservada).
        total_sugeridas += mod_ideias.sugere_do_motor(banco, nome, hub, topicos, agora)

    candidatos = seleciona_topicos(melhores, criterios)
    if candidatos:
        print(f"  candidatos a pauta (acima de {criterios['minimo']} pts): "
              + "; ".join(f"{t['pontuacao']} {t['rotulo'][:40]}" for t in candidatos))
    else:
        print(f"  nenhum topico acima do piso ({criterios['minimo']} pts)")

    # Producao: SO' ideias marcadas pela pessoa, dentro do periodo e da meta
    # do dia. Cada uma vira pauta aprovada com brief; radar/publicar.py
    # escreve, checa e publica no mesmo ciclo.
    produzidas = 0
    marcadas = leitor.ideias_marcadas(nome)
    if marcadas and produzindo:
        inicio_dia = inicio_do_dia_sp()
        vagas = int(meta.get("pautas_por_dia") or 0) - leitor.selecionadas_hoje(nome, inicio_dia)
        print(f"  {len(marcadas)} ideia(s) marcada(s), {max(vagas, 0)} vaga(s) hoje")
        hubs = {h["id"]: h for h in site.get("hubs", []) or []}
        for ideia in marcadas:
            if vagas <= 0:
                break
            hub = hubs.get(ideia.get("hub"))
            if not hub:
                print(f"    [ideia {ideia['id']}] hub {ideia.get('hub')} nao existe no sites.yaml")
                continue
            if seco:
                print(f"    [seco] produziria: {ideia['titulo'][:70]}")
                continue
            # A linha editorial da tela (regras + formato) vai junto para o
            # angulo, o brief e, dentro do brief, para o redator.
            site_ed = {**site, "_linha_editorial": pesquisa.get("linha_editorial") or "",
                       "_formato": pesquisa.get("formato") or "livre"}
            pauta = mod_ideias.produz(ideia, nome, site_ed, hub, banco, leitor, agora)
            if pauta:
                produzidas += 1
                vagas -= 1
    elif marcadas:
        print(f"  {len(marcadas)} ideia(s) marcada(s) esperando: {motivo_prod}")

    resumo = (f"{total_sinais} sinais novos, {total_topicos} topicos, "
              f"{total_sugeridas} sugeridas, {len(marcadas)} marcadas, {produzidas} em producao"
              + ("" if produzindo else f" — {motivo_prod}")
              + mod_sinais.resumo_falhas() + llm.resumo_falhas())
    if not seco:
        banco.registra_execucao({"fluxo": "discover", "site": nome, "status": "ok",
                                 "resumo": resumo[:500], "inicio": inicio.isoformat()})
    return {"site": nome, "sinais": total_sinais, "topicos": total_topicos,
            "candidatos": candidatos, "produzindo": produzindo,
            "marcadas": len(marcadas), "produzidas": produzidas}


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
