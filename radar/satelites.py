"""Publica os artigos-satelite do doll: a atualidade que puxa para os ancora.

    python -m radar.satelites --seco          # monta e mostra, nao publica
    python -m radar.satelites --por-hub 1      # ate 1 satelite por hub (padrao)
    python -m radar.satelites                  # gera, grava e publica

Pega as pautas selecionadas hoje COM dado proprio, no maximo uma por hub (o
teto que segura o conteudo em escala), gera o satelite ligado ao texto ancora
do hub e publica. Cada pauta vira 'publicada' depois — nao se repete.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from .alerta import avisa
from .banco import Banco
from .config import RAIZ, carrega_sites
from .gerador_satelite import monta

SITE = "doll"
SAIDA = RAIZ / "saida"
FUSO_SP = timezone(timedelta(hours=-3))


def inicio_do_dia_sp() -> str:
    agora = datetime.now(FUSO_SP)
    return agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def main() -> int:
    p = argparse.ArgumentParser(description="Artigos-satelite do doll")
    p.add_argument("--seco", action="store_true", help="nao grava nem publica")
    p.add_argument("--sem-publicar", action="store_true",
                   help="gera e grava, mas nao manda para o WordPress")
    p.add_argument("--por-hub", type=int, default=0,
                   help="teto de satelites por hub por dia (0 = pega dos "
                        "criterios do site; padrao la' e' 2)")
    args = p.parse_args()

    site = carrega_sites()[SITE]
    banco = Banco(seco=args.seco)
    leitor = banco if not args.seco else Banco(seco=False)
    inicio = datetime.now(timezone.utc)

    serie = leitor.serie_cotacoes(SITE, dias=30)
    if len(serie) < 2:
        print("serie de cotacoes insuficiente")
        return 1

    # O teto por hub e' criterio editorial — mora em metas.criterios (a tela
    # do radar edita), como os pesos da selecao. O Filipe governa o criterio.
    por_hub = args.por_hub
    if not por_hub:
        meta = leitor.meta_do_site(SITE) or {}
        por_hub = int((meta.get("criterios") or {}).get("satelites_por_hub") or 2)

    inicio_dia = inicio_do_dia_sp()
    candidatas, por = leitor.pautas_para_satelite(SITE, inicio_dia)

    # A vaga do hub e' de quem esta' MADURA (horario vencido ou sem horario),
    # na ordem de pontuacao; pauta futura NUNCA reserva vaga — ela concorre
    # quando o slot dela chegar. Licao de 31/08: a #1093 (slot 17h) segurou a
    # vaga de indicadores e prendeu a #1117 (slot 11h) o dia inteiro.
    agora = datetime.now(FUSO_SP)
    pautas, em_espera = [], 0
    for p in candidatas:
        h = p.get("horario_sugerido")
        if h:
            try:
                if datetime.fromisoformat(h) > agora:
                    em_espera += 1
                    print(f"[espera] pauta {p['id']} agendada para "
                          f"{datetime.fromisoformat(h).astimezone(FUSO_SP):%H:%M}")
                    continue
            except ValueError:
                pass
        hub = p.get("hub") or "_"
        if por.get(hub, 0) >= por_hub:
            continue
        por[hub] = por.get(hub, 0) + 1
        pautas.append(p)
    if not pautas:
        print(f"nenhuma pauta madura para virar satelite ({em_espera} em espera)")
        # Registra mesmo sem publicar: o fluxo invisivel na telemetria custou
        # uma manha de diagnostico em 31/08.
        if not args.seco:
            banco.registra_execucao({
                "fluxo": "satelites", "site": SITE, "status": "ok",
                "resumo": f"0 no ar ({em_espera} aguardando slot)",
                "inicio": inicio.isoformat(),
            })
        return 0

    pode_publicar = site["publicacao"].get("radar") == "auto" or \
        site["publicacao"].get("calendario") == "auto"
    SAIDA.mkdir(exist_ok=True)
    publicados = 0

    for pt in pautas:
        # Hub sem ancora propria (politica-monetaria, indicadores) cai no guia
        # de cotacao — todo satelite tem para onde apontar.
        url_ancora = (leitor.ancora_do_hub(SITE, pt.get("hub") or "cotacao")
                      or leitor.ancora_do_hub(SITE, "cotacao"))
        art = monta(pt, serie, url_ancora, site)
        ref = f"satelite-{pt['id']}"
        (SAIDA / f"{SITE}-{ref}.md").write_text(art["markdown"], encoding="utf-8")

        if args.seco:
            print(f"[seco] {ref} (hub {pt.get('hub')}, {pt.get('pontuacao')}pts): "
                  f"{art['titulo']}")
            continue

        status = "aprovada" if pode_publicar else "rascunho"
        banco.grava_artigo({
            "site": SITE, "tipo": "satelite", "hub": pt.get("hub"),
            "titulo": art["titulo"], "resumo": art["resumo"],
            "corpo_md": art["markdown"], "jsonld": art["jsonld"],
            "status": status, "motivo_portao": f"satelite da pauta {pt['id']}",
            "referencia": ref,
        })
        print(f"[{status}] {art['titulo']}")

        wp = site.get("wordpress")
        if wp and not args.sem_publicar and pode_publicar:
            from .publicador_wp import ErroWordPress, publica
            existente = banco.artigo_existente(SITE, "satelite", ref)
            try:
                resultado = publica({
                    "titulo": art["titulo"], "corpo_md": art["markdown"],
                    "resumo": art["resumo"], "jsonld": art["jsonld"],
                    "status": "publicada", "hub": pt.get("hub"),
                    "wp_post_id": (existente or {}).get("wp_post_id"),
                }, {**wp,
                    "usuario": os.environ[wp["usuario_env"]],
                    "senha_app": os.environ[wp["senha_env"]]})
                banco.marca_publicado(SITE, "satelite", ref,
                                      resultado["id"], resultado.get("link"),
                                      "publicada")
                banco.marca_pauta_publicada(pt["id"])
                publicados += 1
                print(f"  no ar: {resultado.get('link')}")
            except (ErroWordPress, KeyError) as erro:
                print(f"  falha ao publicar {ref}: {erro}")

    if args.seco and pautas:
        # Mostra um satelite inteiro para conferir a qualidade.
        exemplo = monta(pautas[0], serie,
                        leitor.ancora_do_hub(SITE, pautas[0].get("hub") or "cotacao"),
                        site)
        print("\n" + "=" * 70 + "\n" + exemplo["markdown"])
    elif not args.seco:
        banco.registra_execucao({
            "fluxo": "satelites", "site": SITE, "status": "ok",
            "resumo": f"{publicados} satelites no ar"
                      + (f" ({em_espera} aguardando slot)" if em_espera else ""),
            "inicio": inicio.isoformat(),
        })
        if publicados:
            avisa(f"**doll — satelites** {publicados} no ar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
