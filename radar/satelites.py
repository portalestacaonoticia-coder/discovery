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
from .config import RAIZ, carrega_sites, site_ativo
from .gerador_satelite import monta
from .pontua import criterios_com_padrao, teto_do_hub, velha

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

    if not site_ativo(SITE):
        print(f"{SITE} roda em outro ambiente (RADAR_SITES/RADAR_IGNORA_SITES)")
        return 0
    site = carrega_sites()[SITE]
    banco = Banco(seco=args.seco)
    leitor = banco if not args.seco else Banco(seco=False)
    inicio = datetime.now(timezone.utc)

    # Um ano de serie: o texto ganha semana, mes, sequencia e extremos —
    # profundidade honesta, direto da base (pedido do Filipe, 01/09).
    serie = leitor.serie_cotacoes(SITE, dias=370)
    if len(serie) < 2:
        print("serie de cotacoes insuficiente")
        return 1
    leia_tambem = leitor.artigos_recentes(SITE) + leitor.ancoras_publicadas(SITE)

    # O teto por hub e' criterio editorial — mora em metas.criterios (a tela
    # do radar edita), como os pesos da selecao. O Filipe governa o criterio.
    por_hub = args.por_hub
    if not por_hub:
        meta = leitor.meta_do_site(SITE) or {}
        por_hub = int((meta.get("criterios") or {}).get("satelites_por_hub") or 2)

    inicio_dia = inicio_do_dia_sp()
    candidatas, por = leitor.pautas_para_satelite(SITE, inicio_dia)
    publicados_antes = dict(por)   # por categoria, ja' no ar hoje (define o recorte)

    # A vaga do hub e' de quem esta' MADURA (horario vencido ou sem horario),
    # na ordem de pontuacao; pauta futura NUNCA reserva vaga — ela concorre
    # quando o slot dela chegar. Licao de 31/08: a #1093 (slot 17h) segurou a
    # vaga de indicadores e prendeu a #1117 (slot 11h) o dia inteiro.
    agora = datetime.now(FUSO_SP)
    criterios = criterios_com_padrao((leitor.meta_do_site(SITE) or {}).get("criterios"))
    pautas, em_espera = [], 0
    for p in candidatas:
        # pauta aprovada antes do corte de idade (ou que envelheceu esperando
        # o horario) nao vira satelite: o gancho seria noticia velha
        publicado = (p.get("itens") or {}).get("publicado_em")
        if velha(publicado, criterios, agora):
            print(f"[velha] pauta {p['id']}: noticia de {str(publicado)[:10]}, fica de fora")
            continue
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
        teto = teto_do_hub({**criterios, "satelites_por_hub": por_hub}, hub)
        if por.get(hub, 0) >= teto:
            continue
        por[hub] = por.get(hub, 0) + 1
        pautas.append(p)

    # Fora da janela editorial (criterios.janela, horas de Sao Paulo) nada
    # sai, nem pauta "quente": em 21/10/2026, a 00:12, a virada do dia soltou
    # 8 satelites quase iguais de uma vez.
    janela = criterios.get("janela") or {}
    if pautas and not (int(janela.get("inicio", 8)) <= agora.hour < int(janela.get("fim", 20))):
        print(f"[janela] {agora:%H:%M} fora da janela {janela.get('inicio', 8)}h-"
              f"{janela.get('fim', 20)}h: {len(pautas)} madura(s) esperam")
        em_espera += len(pautas)
        pautas = []

    # No maximo 1 satelite por rodada, e so' se o ultimo saiu ha' pelo menos
    # intervalo_min_minutos. As outras maduras esperam a proxima rodada.
    if pautas:
        intervalo = timedelta(minutes=int(criterios.get("intervalo_min_minutos") or 0))
        ultimo = leitor.ultimo_satelite_publicado(SITE)
        if ultimo and intervalo:
            quando = datetime.fromisoformat(str(ultimo).replace("Z", "+00:00"))
            if agora - quando < intervalo:
                print(f"[intervalo] ultimo satelite as {quando.astimezone(FUSO_SP):%H:%M}; "
                      f"proximo depois das {(quando + intervalo).astimezone(FUSO_SP):%H:%M} "
                      f"({len(pautas)} madura(s) esperando)")
                em_espera += len(pautas)
                pautas = []
        pautas = pautas[:1] if intervalo else pautas
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
        # 2o satelite da categoria no dia usa o 2o recorte (dado_categoria)
        pt["_recorte"] = publicados_antes.get(pt.get("hub") or "_", 0)
        art = monta(pt, serie, url_ancora, site, leia_tambem)
        # o proximo satelite da rodada tambem nao pode repetir este titulo
        # (sem url: nao entra no Leia tambem, so' na lista de titulos)
        leia_tambem.insert(0, {"titulo": art["titulo"]})
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
                    "wp_media_id": (existente or {}).get("wp_media_id"),
                }, {**wp,
                    "usuario": os.environ[wp["usuario_env"]],
                    "senha_app": os.environ[wp["senha_env"]]}, site,
                    evitar_imagens=banco.imagens_usadas(SITE))
                banco.marca_publicado(SITE, "satelite", ref,
                                      resultado["id"], resultado.get("link"),
                                      "publicada", resultado.get("midia_id"),
                                      resultado.get("imagem_url"),
                                      resultado.get("imagem_credito"),
                                      imagem_origem=resultado.get("imagem_origem"))
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
