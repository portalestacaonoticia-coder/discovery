"""Esteira de publicacao dos sites SEM base propria (os blogs Tihee).

    python -m radar.publicar --seco             # monta e mostra, nao grava nem publica
    python -m radar.publicar --site broune      # so' um site
    python -m radar.publicar                    # todos os sites do fluxo generico

Pega as pautas que a selecao aprovou hoje, ja' MADURAS (horario_sugerido
vencido), respeita o teto por hub, escreve o guia de servico com o Claude
(radar/gerador_artigo.py) e publica no WordPress com imagem destacada.
Cada pauta vira 'publicada' depois — nao se repete.

Quem entra aqui: site com bloco `wordpress` e SEM `base` no sites.yaml. Quem
tem base propria (doll, ferrugem) tem esteira dedicada, que sabe usar o dado
— satelites.py, dolar_diario.py, ancoras.py, reserva.py.

O portao continua sendo `publicacao.radar` do sites.yaml:
  auto     -> publica direto
  rascunho -> vai para o WordPress como DRAFT, esperando olho humano

Sem ANTHROPIC_API_KEY nada e' escrito e nada e' publicado: aqui nao ha' base
para um template dizer algo de verdade, e texto vazio e' justamente o que a
politica de conteudo em escala do Google descreve.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from .alerta import avisa
from .banco import Banco
from .config import RAIZ, carrega_sites
from .gerador_artigo import monta

SAIDA = RAIZ / "saida"
FUSO_SP = timezone(timedelta(hours=-3))
TETO_HUB_PADRAO = 2


def inicio_do_dia_sp() -> str:
    agora = datetime.now(FUSO_SP)
    return agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def sites_do_fluxo(todos: dict) -> dict:
    """Site com WordPress configurado e sem base propria."""
    return {nome: cfg for nome, cfg in todos.items()
            if cfg.get("wordpress") and not cfg.get("base")}


def maduras(candidatas: list[dict], por_hub: dict, teto: int) -> tuple[list[dict], int]:
    """Filtra pelo horario e pelo teto do hub, na ordem de pontuacao.

    Pauta agendada para mais tarde NUNCA reserva vaga — ela concorre quando o
    slot dela chegar (licao de 31/08 no doll: pauta futura prendeu a vaga do
    hub e o dia fechou incompleto)."""
    agora = datetime.now(FUSO_SP)
    escolhidas, em_espera = [], 0
    por = dict(por_hub)
    for p in candidatas:
        h = p.get("horario_sugerido")
        if h:
            try:
                if datetime.fromisoformat(h) > agora:
                    em_espera += 1
                    continue
            except ValueError:
                pass
        hub = p.get("hub") or "_"
        if por.get(hub, 0) >= teto:
            continue
        por[hub] = por.get(hub, 0) + 1
        escolhidas.append(p)
    return escolhidas, em_espera


def roda_site(nome: str, site: dict, banco: Banco, args) -> dict:
    print(f"\n=== {nome} ({site['dominio']}) ===")
    inicio = datetime.now(timezone.utc)
    leitor = banco if not args.seco else Banco(seco=False)

    meta = leitor.meta_do_site(nome) or {}
    teto = args.por_hub or int(
        (meta.get("criterios") or {}).get("satelites_por_hub") or TETO_HUB_PADRAO)

    candidatas, por_hub = leitor.pautas_para_satelite(
        nome, inicio_do_dia_sp(), exige_dado=False)
    pautas, em_espera = maduras(candidatas, por_hub, teto)

    if not pautas:
        print(f"  nenhuma pauta madura ({em_espera} aguardando slot, "
              f"{len(candidatas)} aprovadas hoje)")
        if not args.seco:
            banco.registra_execucao({
                "fluxo": "publicar", "site": nome, "status": "ok",
                "resumo": f"0 no ar ({em_espera} aguardando slot)",
                "inicio": inicio.isoformat()})
        return {"site": nome, "publicados": 0, "falhas": 0}

    pode_publicar = site.get("publicacao", {}).get("radar") == "auto"
    leia_tambem = leitor.artigos_recentes(nome)
    SAIDA.mkdir(exist_ok=True)
    publicados = falhas = 0

    for pt in pautas:
        art = monta(pt, site, leia_tambem)
        if not art:
            # Sem chave, ou saida rasa demais: a pauta fica aprovada e tenta
            # de novo no proximo ciclo. Melhor vaga vazia que post vazio.
            print(f"  [pulada] pauta {pt['id']}: nao deu para escrever com seguranca")
            falhas += 1
            continue

        ref = f"guia-{pt['id']}"
        (SAIDA / f"{nome}-{ref}.md").write_text(art["markdown"], encoding="utf-8")

        if args.seco:
            print(f"  [seco] {ref} (hub {pt.get('hub')}, {pt.get('pontuacao')}pts): "
                  f"{art['titulo']}")
            continue

        # O artigo NASCE 'aprovada'/'rascunho' — nunca 'publicada'. So'
        # marca_publicado promove, depois do WordPress confirmar. Gravar
        # 'publicada' aqui deixa no banco artigo que nunca foi ao ar: foi o que
        # aconteceu no primeiro ensaio de 18/09, com os 401 de credencial.
        status = "aprovada" if pode_publicar else "rascunho"
        banco.grava_artigo({
            "site": nome, "tipo": "guia", "hub": pt.get("hub"),
            "titulo": art["titulo"], "resumo": art["resumo"],
            "corpo_md": art["markdown"], "jsonld": art["jsonld"],
            "status": status, "motivo_portao": f"guia da pauta {pt['id']}",
            "referencia": ref,
        })
        print(f"  [{status}] {art['titulo']}")

        if args.sem_publicar:
            continue

        from .publicador_wp import ErroWordPress, publica
        wp = site["wordpress"]
        existente = banco.artigo_existente(nome, "guia", ref)
        try:
            resultado = publica({
                "titulo": art["titulo"], "corpo_md": art["markdown"],
                "resumo": art["resumo"], "jsonld": art["jsonld"],
                # o publicador so' entende 'publicada' (vira publish no WP) ou
                # o resto (draft) — a decisao vai explicita, nao o status
                # persistido, que aqui ainda e' 'aprovada'
                "status": "publicada" if pode_publicar else "rascunho",
                "hub": pt.get("hub"),
                "wp_post_id": (existente or {}).get("wp_post_id"),
                "wp_media_id": (existente or {}).get("wp_media_id"),
            }, {**wp,
                "usuario": os.environ[wp["usuario_env"]],
                "senha_app": os.environ[wp["senha_env"]]}, site)
            # Confirmado no WP: agora sim o status reflete a realidade.
            banco.marca_publicado(nome, "guia", ref, resultado["id"],
                                  resultado.get("link"),
                                  "publicada" if pode_publicar else "rascunho",
                                  resultado.get("midia_id"),
                                  resultado.get("imagem_url"),
                                  resultado.get("imagem_credito"))
            # So' some da fila quando de fato foi para o WP — mesmo como
            # rascunho, porque o texto ja' existe e nao se reescreve.
            banco.marca_pauta_publicada(pt["id"])
            publicados += 1
            print(f"  no ar: {resultado.get('link')}")
        except KeyError as erro:
            falhas += 1
            print(f"  falta a variavel de ambiente {erro} — credencial do WP "
                  f"de {nome} nao configurada")
        except ErroWordPress as erro:
            falhas += 1
            print(f"  falha ao publicar {ref}: {erro}")

    if not args.seco:
        banco.registra_execucao({
            "fluxo": "publicar", "site": nome,
            "status": "erro" if falhas and not publicados else "ok",
            "resumo": f"{publicados} no ar"
                      + (f", {falhas} falharam" if falhas else "")
                      + (f" ({em_espera} aguardando slot)" if em_espera else ""),
            "inicio": inicio.isoformat()})
    return {"site": nome, "publicados": publicados, "falhas": falhas}


def main() -> int:
    p = argparse.ArgumentParser(description="Publicacao dos blogs sem base propria")
    p.add_argument("--site", help="roda so' esse site (id em config/sites.yaml)")
    p.add_argument("--seco", action="store_true",
                   help="escreve e mostra, nao grava nem publica")
    p.add_argument("--sem-publicar", action="store_true",
                   help="gera e grava no banco, mas nao manda para o WordPress")
    p.add_argument("--por-hub", type=int, default=0,
                   help="teto de artigos por hub por dia (0 = pega dos criterios)")
    args = p.parse_args()

    sites = sites_do_fluxo(carrega_sites())
    if args.site:
        todos = carrega_sites()
        if args.site not in todos:
            print(f"Site '{args.site}' nao existe em config/sites.yaml")
            return 1
        if args.site not in sites:
            cfg = todos[args.site]
            motivo = ("tem base propria e esteira dedicada (satelites.py)"
                      if cfg.get("base") else "nao tem bloco 'wordpress' no sites.yaml")
            print(f"Site '{args.site}' fora deste fluxo: {motivo}")
            return 1
        sites = {args.site: sites[args.site]}

    if not sites:
        print("Nenhum site no fluxo generico (precisa de 'wordpress' e nao ter 'base')")
        return 0

    banco = Banco(seco=args.seco)
    resumo, falhas = [], 0
    for nome, cfg in sites.items():
        try:
            r = roda_site(nome, cfg, banco, args)
        except Exception as erro:
            # Um site quebrado nao derruba os outros — mesmo contrato do
            # principal.py.
            print(f"  {nome} falhou: {erro}")
            falhas += 1
            if not args.seco:
                banco.registra_execucao({
                    "fluxo": "publicar", "site": nome, "status": "erro",
                    "resumo": str(erro)[:500],
                    "inicio": datetime.now(timezone.utc).isoformat()})
            continue
        resumo.append(r)
        falhas += r["falhas"]

    total = sum(r["publicados"] for r in resumo)
    if total and not args.seco:
        linhas = "\n".join(f"• {r['site']}: {r['publicados']} no ar"
                           for r in resumo if r["publicados"])
        avisa(f"**Blogs Tihee — publicacao**\n{linhas}")
    print(f"\ntotal: {total} no ar" + (f", {falhas} falhas" if falhas else ""))
    return 1 if falhas and not total else 0


if __name__ == "__main__":
    sys.exit(main())
