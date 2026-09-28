"""Manda para o WordPress, como RASCUNHO, os guias que ficaram escritos e
nunca publicados — para o editor ler no painel do site e publicar na mao.

    python -m radar.rascunhos --seco              # lista o que mandaria
    python -m radar.rascunhos --site pescaria     # so' um site
    python -m radar.rascunhos                     # todos os blogs

De onde vem o estoque: entre 18 e 26/09/2026 o WordPress de quatro blogs
recusava a publicacao (401, usuario sem permissao). A esteira escrevia o guia
de cada pauta aprovada, salvava em `artigos` e falhava no envio. No dia
seguinte ela so' olha as pautas aprovadas DO DIA, entao as de ontem ficaram
orfas: pauta 'aprovada' para sempre, texto pronto no banco.

Este fluxo NAO chama o gpt-6-luna — so' usa o texto ja' salvo (custo zero de API).
Pauta orfa SEM texto salvo e' apenas contada e deixada como esta'.

Vai como rascunho de proposito, mesmo com `publicacao.radar: auto` no
sites.yaml: e' volume antigo entrando de uma vez, e o editor decide o ritmo.
Depois de enviada, a pauta vira 'publicada' — mesmo contrato do publicar.py:
o texto ja' existe no WP e nao se reescreve.

Idempotente: guia que ja' tem wp_post_id nao e' reenviado, so' tem a pauta
fechada. Roda de novo sem duplicar nada.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from .alerta import avisa
from .banco import Banco
from .config import carrega_sites
from .publicar import reaproveita, sites_do_fluxo

FUSO_SP = timezone(timedelta(hours=-3))


def inicio_do_dia_sp() -> str:
    agora = datetime.now(FUSO_SP)
    return agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def roda_site(nome: str, site: dict, banco: Banco, args) -> dict:
    print(f"\n=== {nome} ({site['dominio']}) ===")
    inicio = datetime.now(timezone.utc)
    leitor = banco if not args.seco else Banco(seco=False)

    orfas = leitor.pautas_aprovadas_antes(nome, inicio_do_dia_sp())
    if args.limite:
        orfas = orfas[:args.limite]
    if not orfas:
        print("  nenhuma pauta orfa (aprovada antes de hoje)")
        return {"site": nome, "enviados": 0, "sem_texto": 0, "falhas": 0}

    wp = site["wordpress"]
    enviados = sem_texto = falhas = ja_no_wp = 0
    for pt in orfas:
        ref = f"guia-{pt['id']}"
        existente = leitor.artigo_existente(nome, "guia", ref)
        art = reaproveita(existente)
        quando = str(pt.get("selecionada_em") or "")[:10]
        if not art:
            sem_texto += 1
            print(f"  [sem texto] pauta {pt['id']} ({quando}): "
                  f"{(pt.get('titulo_sug') or '')[:70]}")
            continue

        if existente.get("wp_post_id"):
            # Ja' esta' no WP (a rodada do dia chegou antes deste fluxo):
            # so' fecha a pauta para ela sair da fila.
            ja_no_wp += 1
            if not args.seco:
                banco.marca_pauta_publicada(pt["id"])
            print(f"  [ja no WP] {ref}: {art['titulo']}")
            continue

        if args.seco:
            print(f"  [seco] {ref} ({quando}, hub {pt.get('hub')}): {art['titulo']}")
            enviados += 1
            continue

        from .publicador_wp import ErroWordPress, publica
        try:
            resultado = publica({
                "titulo": art["titulo"], "corpo_md": art["markdown"],
                "resumo": art["resumo"], "jsonld": art["jsonld"],
                "status": "rascunho",          # SEMPRE draft: o editor decide
                "hub": pt.get("hub"),
                "wp_post_id": None,
                "wp_media_id": existente.get("wp_media_id"),
                "imagem_url": existente.get("imagem_url"),
                "imagem_credito": existente.get("imagem_credito"),
            }, {**wp,
                "usuario": os.environ[wp["usuario_env"]],
                "senha_app": os.environ[wp["senha_env"]]}, site)
            banco.marca_publicado(nome, "guia", ref, resultado["id"],
                                  resultado.get("link"), "rascunho",
                                  resultado.get("midia_id"),
                                  resultado.get("imagem_url"),
                                  resultado.get("imagem_credito"))
            banco.marca_pauta_publicada(pt["id"])
            enviados += 1
            print(f"  [rascunho] {art['titulo']} -> post {resultado['id']}")
        except KeyError as erro:
            falhas += 1
            print(f"  falta a variavel de ambiente {erro} — credencial do WP "
                  f"de {nome} nao configurada")
            break   # sem credencial nenhum outro vai passar
        except ErroWordPress as erro:
            falhas += 1
            print(f"  falha ao enviar {ref}: {erro}")

    resumo = (f"{enviados} rascunhos enviados"
              + (f", {ja_no_wp} ja estavam no WP" if ja_no_wp else "")
              + (f", {sem_texto} sem texto" if sem_texto else "")
              + (f", {falhas} falharam" if falhas else ""))
    print(f"  {resumo}")
    if not args.seco:
        banco.registra_execucao({
            "fluxo": "rascunhos", "site": nome,
            "status": "erro" if falhas and not enviados else "ok",
            "resumo": resumo, "inicio": inicio.isoformat()})
    return {"site": nome, "enviados": enviados, "sem_texto": sem_texto,
            "falhas": falhas}


def main() -> int:
    p = argparse.ArgumentParser(
        description="Guias escritos e nunca publicados -> rascunhos no WordPress")
    p.add_argument("--site", help="roda so' esse site (id em config/sites.yaml)")
    p.add_argument("--seco", action="store_true",
                   help="lista o que mandaria, nao grava nem envia")
    p.add_argument("--limite", type=int, default=0,
                   help="no maximo N por site (0 = todos)")
    args = p.parse_args()

    todos = carrega_sites()
    sites = sites_do_fluxo(todos)
    if args.site:
        if args.site not in sites:
            print(f"Site '{args.site}' nao esta no fluxo dos blogs "
                  f"(precisa de 'wordpress' e nao ter 'base')")
            return 1
        sites = {args.site: sites[args.site]}

    banco = Banco(seco=args.seco)
    resumo, falhas = [], 0
    for nome, cfg in sites.items():
        try:
            r = roda_site(nome, cfg, banco, args)
        except Exception as erro:
            print(f"  {nome} falhou: {erro}")
            falhas += 1
            continue
        resumo.append(r)
        falhas += r["falhas"]

    total = sum(r["enviados"] for r in resumo)
    if total and not args.seco:
        linhas = "\n".join(f"• {r['site']}: {r['enviados']} rascunhos"
                           for r in resumo if r["enviados"])
        avisa(f"**Blogs Tihee — guias antigos como rascunho**\n{linhas}")
    print(f"\ntotal: {total} rascunhos" + (f", {falhas} falhas" if falhas else ""))
    return 1 if falhas and not total else 0


if __name__ == "__main__":
    sys.exit(main())
