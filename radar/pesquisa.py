"""Research Engine: as EVIDENCIAS de uma ideia antes de qualquer texto.

O que entra:
  fatos               lidos pelo modelo nas fontes OFICIAIS do hub (busca na
                      web restrita a esses dominios), cada um com a URL que
                      ele de fato leu. Fato sem URL citada e' descartado.
  noticias_recentes   as manchetes que os sinais trouxeram (so' titulo,
                      veiculo, data, link — nunca o texto)
  cobertura_concorrente  titulo + snippet dos organicos do SERP
  perguntas / relacionadas  o que as pessoas perguntam e buscam
  historico_site      o que o site ja' publicou neste hub (links internos)

Regra do README mantida: texto integral so' de dominio oficial. De
concorrente, so' o que a busca mostra.

As funcoes _fontes_do_hub / _dominios_do_hub / _busca moraram em
gerador_artigo.py; vivem aqui agora e o gerador importa de volta.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from . import llm


def _fontes_do_hub(hub: dict) -> list[dict]:
    """As fontes oficiais configuradas no hub (sites.yaml -> hubs[].fontes):
    lista de {nome, url}. Entrada sem nome ou sem URL e' ignorada."""
    uteis = []
    for f in hub.get("fontes") or []:
        if isinstance(f, dict) and f.get("nome") and f.get("url"):
            uteis.append({"nome": str(f["nome"]).strip(), "url": str(f["url"]).strip()})
    return uteis


def _dominios_do_hub(hub: dict) -> list[str]:
    """Dominios em que a busca pode entrar: os das `fontes` do hub (sem o
    'www.'; a API cobre os subdominios) mais o que estiver em `pesquisa` no
    hub. Sem nada configurado, nao ha' busca — fonte ou e' oficial ou nao
    entra."""
    dominios: list[str] = []
    for f in _fontes_do_hub(hub):
        host = (urlparse(f["url"]).netloc or "").lower().removeprefix("www.")
        if host and host not in dominios:
            dominios.append(host)
    for d in hub.get("pesquisa") or []:
        d = str(d).strip().lower().removeprefix("https://").removeprefix("http://")
        d = d.removeprefix("www.").rstrip("/")
        if d and d not in dominios:
            dominios.append(d)
    return dominios


def _busca(site: dict, hub: dict) -> list[str]:
    """Dominios da busca, ou [] se ela esta' desligada: hub sem fontes, ou
    `pesquisa: false` no site."""
    if site.get("pesquisa", True) is False:
        return []
    return _dominios_do_hub(hub)


def _dominio(url: str) -> str:
    return (urlparse(url or "").netloc or "").lower().removeprefix("www.")


def _fato_confiavel(fato: dict, citacoes: list[dict], dominios: list[str]) -> bool:
    url = str(fato.get("fonte_url") or "").strip()
    if not url.startswith("http"):
        return False
    if any(url.rstrip("/") == c["url"].rstrip("/") for c in citacoes):
        return True
    host = _dominio(url)
    return any(host == d or host.endswith("." + d) for d in dominios)


def _sistema_pesquisa(site: dict, hub: dict) -> str:
    return (
        f"Voce e' pesquisador do {site.get('entidade') or site.get('dominio')}, "
        f"secao \"{hub.get('titulo')}\". Sua unica tarefa: LEVANTAR FATOS nas "
        "fontes oficiais desta secao, usando a ferramenta de busca (ate "
        f"{llm.MAX_BUSCAS_PADRAO} buscas, objetivas). Um fato e' um numero, "
        "prazo, valor, regra, lei ou procedimento que voce LEU numa pagina. "
        "Cada fato traz a URL exata da pagina lida. Se nao encontrou, nao "
        "escreva — lista vazia e' resposta valida. Nada de opiniao, nada de "
        "memoria.\n"
        "Responda SO um JSON: {\"fatos\": [{\"afirmacao\": \"...\", \"valor\": \"...\", "
        "\"fonte_url\": \"https://...\", \"fonte_nome\": \"...\", \"data\": \"...\"}]}")


def _prompt_pesquisa(ideia: dict, angulo: dict, hub: dict) -> str:
    partes = [f"Ideia: {ideia.get('titulo')}",
              f"Angulo: {angulo.get('titulo_trabalho')} — {angulo.get('promessa')}"]
    if angulo.get("perguntas_respondidas"):
        partes.append("Perguntas que o artigo precisa responder:\n- "
                      + "\n- ".join(angulo["perguntas_respondidas"]))
    fontes = _fontes_do_hub(hub)
    if fontes:
        partes.append("Fontes oficiais onde buscar: "
                      + "; ".join(f"{f['nome']} ({f['url']})" for f in fontes))
    partes.append("\nLevante os fatos.")
    return "\n".join(partes)


def pesquisa(ideia: dict, angulo: dict, nome: str, site: dict, hub: dict, banco) -> dict:
    """Evidencias da ideia. Chama o modelo (1x, com busca) so' se o hub tem
    fontes oficiais; sem elas o artigo sai sem numero — por desenho.
    `nome` e' o id do site (chave do sites.yaml), para o historico."""
    detalhes = ideia.get("detalhes") or {}
    dominios = _busca(site, hub)
    fatos: list[dict] = []
    citacoes: list[dict] = []
    buscas = 0
    if dominios and llm.tem_chave():
        texto, citacoes = llm.gera_com_busca(
            _prompt_pesquisa(ideia, angulo, hub), dominios,
            sistema=_sistema_pesquisa(site, hub), max_tokens=3000)
        bruto = re.search(r"\{.*\}", texto or "", re.S)
        try:
            dados = json.loads(bruto.group(0)) if bruto else {}
        except json.JSONDecodeError:
            dados = {}
        for f in (dados.get("fatos") or []) if isinstance(dados, dict) else []:
            if isinstance(f, dict) and f.get("afirmacao") and _fato_confiavel(f, citacoes, dominios):
                fatos.append({
                    "afirmacao": str(f["afirmacao"]).strip()[:400],
                    "valor": str(f.get("valor") or "").strip()[:120],
                    "fonte_url": str(f["fonte_url"]).strip(),
                    "fonte_nome": str(f.get("fonte_nome") or _dominio(f["fonte_url"])).strip()[:120],
                    "data": str(f.get("data") or "").strip()[:40],
                })
        buscas = len(citacoes)

    vistas: set[str] = set()
    fontes_primarias = []
    for c in citacoes:
        if c["url"].rstrip("/") in vistas:
            continue
        vistas.add(c["url"].rstrip("/"))
        fontes_primarias.append({"url": c["url"], "titulo": c.get("titulo") or c["url"],
                                 "dominio": _dominio(c["url"])})
    for f in fatos:
        if f["fonte_url"].rstrip("/") not in vistas:
            vistas.add(f["fonte_url"].rstrip("/"))
            fontes_primarias.append({"url": f["fonte_url"], "titulo": f["fonte_nome"],
                                     "dominio": _dominio(f["fonte_url"])})

    return {
        "fatos": fatos[:20],
        "fontes_primarias": fontes_primarias[:20],
        "fontes_oficiais": _fontes_do_hub(hub),
        "perguntas": [str(p) for p in (detalhes.get("perguntas") or [])][:10],
        "relacionadas": [str(r) for r in (detalhes.get("relacionadas") or [])][:10],
        "noticias_recentes": [m for m in (detalhes.get("manchetes") or [])][:5],
        "cobertura_concorrente": [{"titulo": o.get("titulo"), "snippet": o.get("snippet"),
                                   "url": o.get("url")}
                                  for o in (detalhes.get("organicos") or [])][:5],
        "historico_site": [{"titulo": a.get("titulo"), "url": a.get("url_publicada")}
                           for a in banco.artigos_publicados_do_hub(nome, hub.get("id"))
                           if a.get("url_publicada")][:12] if banco else [],
        "buscas": buscas,
        "dominios": dominios,
    }
