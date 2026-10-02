"""Esteira de publicacao dos sites SEM base propria (os blogs Tihee).

    python -m radar.publicar --seco             # monta e mostra, nao grava nem publica
    python -m radar.publicar --site broune      # so' um site
    python -m radar.publicar                    # todos os sites do fluxo generico

Pega as pautas que a selecao aprovou hoje, ja' MADURAS (horario_sugerido
vencido), respeita o teto por hub, escreve o guia de servico com o gpt-5.6-luna
(radar/gerador_artigo.py) e publica no WordPress com imagem destacada.
Cada pauta vira 'publicada' depois — nao se repete.

Quem entra aqui: site com bloco `wordpress` e SEM `base` no sites.yaml. Quem
tem base propria (doll, ferrugem) tem esteira dedicada, que sabe usar o dado
— satelites.py, dolar_diario.py, ancoras.py, reserva.py.

O portao continua sendo `publicacao.radar` do sites.yaml:
  auto     -> publica direto
  rascunho -> vai para o WordPress como DRAFT, esperando olho humano

Sem OPENAI_API_KEY nada e' escrito e nada e' publicado: aqui nao ha' base
para um template dizer algo de verdade, e texto vazio e' justamente o que a
politica de conteudo em escala do Google descreve.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from . import llm
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
    """Site com WordPress configurado e sem base propria — ou qualquer site
    com WordPress no motor Discover (as pautas escolhidas na tela viram guia
    por esta esteira; o doll continua com PTAX diaria, ancoras e reserva
    pelas esteiras dedicadas)."""
    return {nome: cfg for nome, cfg in todos.items()
            if cfg.get("wordpress") and (not cfg.get("base") or cfg.get("motor") == "discover")}


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


def reaproveita(existente: dict | None) -> dict | None:
    """O artigo salvo em `artigos`, no formato que `monta` devolve — ou None
    se nao ha' texto util (nunca foi escrito, ou ficou aquem do portao de
    qualidade do gerador). Artigo ja' 'publicada' tambem volta: rerodar e'
    atualizar o mesmo post, nunca reescrever."""
    if not existente:
        return None
    # Reprovado pelo checador nao volta: a pauta ja' saiu da fila.
    if existente.get("status") == "reprovada":
        return None
    checagem = existente.get("checagem")
    if isinstance(checagem, dict) and not checagem.get("aprovado"):
        return None
    corpo = (existente.get("corpo_md") or "").strip()
    titulo = (existente.get("titulo") or "").strip()
    if not titulo or len(corpo) < 1200:
        return None
    return {"titulo": titulo, "markdown": corpo,
            "resumo": existente.get("resumo") or corpo.split("\n\n")[0][:280],
            "jsonld": existente.get("jsonld")}


def roda_site(nome: str, site: dict, banco: Banco, args) -> dict:
    print(f"\n=== {nome} ({site['dominio']}) ===")
    inicio = datetime.now(timezone.utc)
    leitor = banco if not args.seco else Banco(seco=False)

    meta = leitor.meta_do_site(nome) or {}
    teto = args.por_hub or int(
        (meta.get("criterios") or {}).get("satelites_por_hub") or TETO_HUB_PADRAO)

    candidatas, por_hub = leitor.pautas_para_satelite(
        nome, inicio_do_dia_sp(), exige_dado=False)
    if site.get("motor") == "discover":
        # Motor Discover: so' sai o que a pessoa escolheu na tela (pauta com
        # brief, vinda de ideia marcada). Pauta antiga do radar ou do
        # calendario nao passa — e no doll as pautas de satelite seguem
        # pela esteira dele (satelites.py), sem cair aqui em dobro.
        candidatas = [p for p in candidatas if p.get("brief")]
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
    if not llm.tem_chave():
        # Sem chave o gerador devolve None em silencio (e' o modo sem LLM,
        # por desenho) e cada pauta viraria um "[pulada]" sem motivo. Em
        # 28/09/2026 o secret sumiu do Actions e a rodada ficou 2h vermelha
        # sem dizer por que. Avisa UMA vez, aqui.
        print("  sem OPENAI_API_KEY: nenhum guia sera' escrito (so' reaproveita "
              "texto ja' salvo)")
    leia_tambem = leitor.artigos_recentes(nome)
    SAIDA.mkdir(exist_ok=True)
    publicados = falhas = 0

    # Pauta do motor Discover tem como hub a CATEGORIA DO WORDPRESS (slug);
    # resolve uma vez por site o hub de trabalho (nome da categoria +
    # vocabulario/fontes do hub do yaml correspondente).
    from .ideias import resolve_hub
    from .oportunidade import criterios_discover
    pesquisa = criterios_discover(meta.get("criterios"))["pesquisa"]

    for pt in pautas:
        ref = f"guia-{pt['id']}"
        if pt.get("brief"):
            pt["_hub"] = resolve_hub(site, pt.get("hub") or "", pesquisa)
        # IDEMPOTENTE: o guia ja' escrito numa rodada anterior (e que nao
        # chegou ao WP — 401 de credencial, site fora do ar) e' reaproveitado
        # do banco. So' chama o modelo quando NAO ha' texto salvo. Antes de
        # 26/09/2026 cada ciclo de 30 min reescrevia os mesmos 12 guias
        # enquanto o WP recusasse — o maior custo de API do radar.
        existente = leitor.artigo_existente(nome, "guia", ref)
        art = reaproveita(existente)
        reaproveitado = art is not None
        if reaproveitado:
            print(f"  [reaproveitado] {ref}: {art['titulo']}")
        else:
            art = monta(pt, site, leia_tambem)
        if not art:
            # Sem chave, ou saida rasa demais: a pauta fica aprovada e tenta
            # de novo no proximo ciclo. Melhor vaga vazia que post vazio.
            print(f"  [pulada] pauta {pt['id']}: nao deu para escrever com seguranca")
            falhas += 1
            continue

        # Motor Discover: pauta com brief passa pelo checador (unico portao)
        # e pelo otimizador antes do WP. Reprovada vira artigo 'reprovada' e
        # a ideia de origem acompanha; a pauta sai da fila.
        checagem_resultado = None
        if pt.get("brief") and not reaproveitado:
            from . import checagem as mod_checagem, discover
            from .gerador_artigo import corrige
            hub_cfg = pt.get("_hub") or {}
            ev = pt.get("evidencias") or {}
            checagem_resultado = mod_checagem.checa(art, pt["brief"], ev, hub_cfg)
            if not checagem_resultado["aprovado"] and checagem_resultado["corrigivel"]:
                print(f"  [checagem] corrigindo: {checagem_resultado['motivo'][:120]}")
                corrigido = corrige(art, checagem_resultado["estrutural"], pt["brief"], ev, site, hub_cfg)
                if corrigido:
                    art = corrigido
                    checagem_resultado = mod_checagem.checa(art, pt["brief"], ev, hub_cfg)
            print(f"  [checagem] {checagem_resultado['motivo'][:160]}")
            if not checagem_resultado["aprovado"]:
                (SAIDA / f"{nome}-{ref}-reprovado.md").write_text(art["markdown"], encoding="utf-8")
                falhas += 1
                if not args.seco:
                    banco.grava_artigo({
                        "site": nome, "tipo": "guia", "hub": pt.get("hub"),
                        "titulo": art["titulo"], "resumo": art["resumo"],
                        "corpo_md": art["markdown"], "jsonld": art["jsonld"],
                        "status": "reprovada", "referencia": ref,
                        "motivo_portao": checagem_resultado["motivo"][:300],
                        "checagem": {k: v for k, v in checagem_resultado.items() if k != "corrigivel"},
                    })
                    banco.marca_pauta_status(pt["id"], "descartada")
                    banco.marca_ideia_da_pauta(pt["id"], "reprovada")
                continue
            art = discover.otimiza(art, pt["brief"], site, hub_cfg)

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
        if not reaproveitado:
            registro = {
                "site": nome, "tipo": "guia", "hub": pt.get("hub"),
                "titulo": art["titulo"], "resumo": art["resumo"],
                "corpo_md": art["markdown"], "jsonld": art["jsonld"],
                "status": status,
                "motivo_portao": (checagem_resultado["motivo"][:300] if checagem_resultado
                                  else f"guia da pauta {pt['id']}"
                                  + (f" ({art['citacoes']} fonte(s) citada(s))"
                                     if art.get("citacoes") is not None else "")),
                "referencia": ref,
            }
            if checagem_resultado:
                registro["checagem"] = {k: v for k, v in checagem_resultado.items() if k != "corrigivel"}
            banco.grava_artigo(registro)
        print(f"  [{status}] {art['titulo']}"
              + (f" — {art['citacoes']} fonte(s) citada(s)"
                 if art.get("citacoes") else ""))

        if args.sem_publicar:
            continue

        from .publicador_wp import ErroWordPress, publica
        wp = site["wordpress"]
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
                "imagem_pronta": art.get("imagem_pronta"),
            }, {**wp,
                "usuario": os.environ[wp["usuario_env"]],
                "senha_app": os.environ[wp["senha_env"]]}, site,
                evitar_imagens=banco.imagens_usadas(nome))
            # Confirmado no WP: agora sim o status reflete a realidade.
            banco.marca_publicado(nome, "guia", ref, resultado["id"],
                                  resultado.get("link"),
                                  "publicada" if pode_publicar else "rascunho",
                                  resultado.get("midia_id"),
                                  resultado.get("imagem_url"),
                                  resultado.get("imagem_credito"),
                                  imagem_origem=resultado.get("imagem_origem"))
            # So' some da fila quando de fato foi para o WP — mesmo como
            # rascunho, porque o texto ja' existe e nao se reescreve.
            banco.marca_pauta_publicada(pt["id"])
            if pt.get("brief"):
                banco.marca_ideia_da_pauta(pt["id"], "publicada")
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
                      + (f" ({em_espera} aguardando slot)" if em_espera else "")
                      + llm.resumo_falhas(),
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
        llm.limpa_falhas()
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
