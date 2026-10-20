"""Ensaio dos GUIAS com o modelo local (20/10/2026).

    python -m radar.ensaio_guias --site doll --ideias 33,29,30

O doll nunca publicou guia: guia so' nasce de ideia MARCADA na tela Radar
(motor Discover), e nenhuma foi marcada. Entao o ensaio parte das ideias
sugeridas e roda, com o modelo do ambiente, a MESMA esteira de
ideias.produz + publicar.py — angulo -> pesquisa (SearXNG) -> brief ->
guia -> checagem (-> corrige -> checagem) — sem gravar nada: nem pauta, nem
ideia, nem artigo. A imagem (discover.otimiza) fica de fora: e' OpenAI.

Sai em saida/ensaio/:
    <site>-guia-ideia-<id>-local.md     o guia + veredito + tempos
    <site>-guia-ideia-<id>-brief.json   angulo, evidencias e brief
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import llm
from .banco import Banco
from .config import RAIZ, carrega_sites, env

PASTA = RAIZ / "saida" / "ensaio"


# Fontes oficiais para simular o hub com pesquisa (--fontes): o doll nao tem
# hubs[].fontes no sites.yaml, entao na esteira real a pesquisa e' pulada.
FONTES_SIMULADAS = [
    {"nome": "Banco Central do Brasil", "url": "https://www.bcb.gov.br"},
    {"nome": "Receita Federal", "url": "https://www.gov.br/receitafederal"},
]


def ensaia(ideia: dict, nome: str, site: dict, banco: Banco, fontes: bool = False) -> dict:
    from . import angulos_ia
    from . import brief as mod_brief
    from . import checagem as mod_checagem
    from . import pesquisa as mod_pesquisa
    from .gerador_artigo import corrige, monta
    from .ideias import resolve_hub
    from .oportunidade import criterios_discover

    meta = banco.meta_do_site(nome) or {}
    pesquisa = criterios_discover(meta.get("criterios")).get("pesquisa") or {}
    hub = resolve_hub(site, ideia["hub"], pesquisa)
    if fontes:
        hub = {**hub, "fontes": FONTES_SIMULADAS}
    site_ed = {**site, "_linha_editorial": pesquisa.get("linha_editorial") or "",
               "_formato": pesquisa.get("formato") or "livre"}
    r: dict = {"tempos": {}, "falhas": []}

    def etapa(nome_etapa, f):
        inicio = time.monotonic()
        llm.limpa_falhas()
        try:
            return f()
        finally:
            r["tempos"][nome_etapa] = round((time.monotonic() - inicio) / 60, 1)
            r["falhas"] += [f"{nome_etapa}: {x}" for x in llm.falhas()]
            print(f"  {nome_etapa}: {r['tempos'][nome_etapa]} min", flush=True)

    publicados = [a.get("titulo") or "" for a in banco.artigos_publicados_do_hub(nome, hub["id"])]
    angulos = etapa("angulos", lambda: angulos_ia.propoe_angulos(ideia, site_ed, hub, publicados))
    angulo = angulos_ia.escolhe_angulo(angulos or [], hub, site_ed.get("_formato"))
    r["angulos"], r["angulo"] = angulos, angulo
    if not angulo:
        r["veredito"] = "sem angulo utilizavel"
        return r
    ev = etapa("pesquisa", lambda: mod_pesquisa.pesquisa(ideia, angulo, nome, site_ed, hub, banco))
    r["evidencias"] = ev
    b = etapa("brief", lambda: mod_brief.monta_brief(ideia, angulo, ev, site_ed, hub))
    r["brief"] = b
    if not b:
        r["veredito"] = "brief nao fechou"
        return r
    pt = {"hub": ideia["hub"], "_hub": hub, "brief": b, "evidencias": ev}
    art = etapa("guia", lambda: monta(pt, site_ed, banco.artigos_recentes(nome)))
    if not art:
        r["veredito"] = "o modelo nao escreveu o guia"
        return r
    res = etapa("checagem", lambda: mod_checagem.checa(art, b, ev, hub, site))
    r["checagem_1"] = res
    if not res["aprovado"] and res["corrigivel"]:
        corrigido = etapa("corrige", lambda: corrige(art, res["estrutural"], b, ev, site_ed, hub))
        if corrigido:
            r["artigo_antes_da_correcao"] = art["markdown"]
            art = corrigido
            res = etapa("checagem_2", lambda: mod_checagem.checa(art, b, ev, hub, site))
            r["checagem_2"] = res
    r["artigo"] = art
    r["veredito"] = ("APROVADO" if res["aprovado"] else "REPROVADO") + f" — {res['motivo']}"
    return r


def main() -> int:
    p = argparse.ArgumentParser(description="Ensaio dos guias com o modelo local")
    p.add_argument("--site", default="doll")
    p.add_argument("--ideias", required=True, help="ids das ideias, separados por virgula")
    p.add_argument("--fontes", action="store_true",
                   help="simula fontes oficiais no hub (BCB, Receita): liga a pesquisa via SearXNG")
    args = p.parse_args()

    site = carrega_sites().get(args.site)
    if not site or not llm.modo_local():
        print("site inexistente ou LLM_LOCAL_URL vazio (o ensaio e' do modelo LOCAL)")
        return 1
    banco = Banco(seco=False)     # so' leitura: nada abaixo grava
    PASTA.mkdir(parents=True, exist_ok=True)
    ids = [int(x) for x in args.ideias.split(",") if x.strip()]
    ideias = (banco.cliente.table("ideias").select("*").eq("site", args.site)
              .in_("id", ids).execute().data or [])
    ideias.sort(key=lambda i: ids.index(i["id"]))
    print(f"{len(ideias)} ideia(s) com {env('LLM_LOCAL_MODELO') or llm.MODELO_LOCAL_PADRAO}")
    for n, ideia in enumerate(ideias, 1):
        ref = f"guia-ideia-{ideia['id']}" + ("-fontes" if args.fontes else "")
        print(f"\n[{n}/{len(ideias)}] {ref}: {ideia['titulo']}", flush=True)
        inicio = time.monotonic()
        try:
            r = ensaia(ideia, args.site, site, banco, args.fontes)
        except Exception as erro:  # noqa: BLE001 — um caso quebrado nao para o ensaio
            r = {"veredito": f"erro: {type(erro).__name__}: {erro}", "tempos": {}, "falhas": []}
        minutos = (time.monotonic() - inicio) / 60
        art = r.pop("artigo", None)
        cabecalho = (f"<!-- ensaio local | {r['veredito']} | {minutos:.1f} min | "
                     f"etapas {r['tempos']} | falhas {r['falhas']} -->\n\n")
        (PASTA / f"{args.site}-{ref}-local.md").write_text(
            cabecalho + (art["markdown"] if art else "(sem texto)"), encoding="utf-8")
        (PASTA / f"{args.site}-{ref}-brief.json").write_text(
            json.dumps({"ideia": ideia, **r}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print(f"  {r['veredito'][:200]} ({minutos:.1f} min)", flush=True)
    print(f"\npronto: {PASTA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
