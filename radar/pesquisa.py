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
from datetime import datetime
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


def _prefixos_do_hub(hub: dict) -> list[str]:
    """Onde um FATO pode nascer: host + caminho de cada fonte oficial
    ('gov.br/receitafederal'). A busca filtra por host (a API so' aceita
    host), mas fato de 'gov.br/procon-mt' nao e' da Receita (ensaio de
    20/10/2026: o IOF de 6,38% veio de uma pagina do Procon-MT)."""
    prefixos = []
    for f in _fontes_do_hub(hub):
        u = urlparse(f["url"])
        prefixo = ((u.netloc or "").lower().removeprefix("www.") + u.path).rstrip("/")
        if prefixo and prefixo not in prefixos:
            prefixos.append(prefixo)
    for d in hub.get("pesquisa") or []:
        d = str(d).strip().lower().removeprefix("https://").removeprefix("http://")
        d = d.removeprefix("www.").rstrip("/")
        if d and d not in prefixos:
            prefixos.append(d)
    return prefixos


def _dentro(url: str, prefixos: list[str]) -> bool:
    u = urlparse(url or "")
    alvo = ((u.netloc or "").lower().removeprefix("www.") + u.path).rstrip("/")
    for p in prefixos:
        host, _, caminho = p.partition("/")
        alvo_host, _, alvo_caminho = alvo.partition("/")
        if not (alvo_host == host or alvo_host.endswith("." + host)):
            continue
        if not caminho or alvo_caminho == caminho or alvo_caminho.startswith(caminho + "/"):
            return True
    return False


_ANO = re.compile(r"\b(20\d{2})\b")


def _recente(fato: dict, citacoes: list[dict], hoje=None) -> bool:
    """Fato de pagina velha nao entra: o ano mais recente citado no `data` do
    fato (ou, no modo local, no texto da pagina lida) tem de ser deste ano
    ou do anterior. Sem ano nenhum, passa — nao ha' como saber."""
    ano_atual = (hoje or datetime.now()).year
    anos = [int(a) for a in _ANO.findall(str(fato.get("data") or ""))]
    if not anos:
        url = str(fato.get("fonte_url") or "").strip().rstrip("/")
        pagina = next((c for c in citacoes if c.get("texto")
                       and c["url"].rstrip("/") == url), None)
        if pagina:
            anos = [int(a) for a in _ANO.findall(pagina["texto"]) if int(a) <= ano_atual]
    return not anos or max(anos) >= ano_atual - 1


def _busca(site: dict, hub: dict) -> list[str]:
    """Dominios da busca, ou [] se ela esta' desligada: hub sem fontes, ou
    `pesquisa: false` no site."""
    if site.get("pesquisa", True) is False:
        return []
    return _dominios_do_hub(hub)


def _dominio(url: str) -> str:
    return (urlparse(url or "").netloc or "").lower().removeprefix("www.")


def _fato_confiavel(fato: dict, citacoes: list[dict], dominios: list[str],
                    prefixos: list[str] | None = None) -> bool:
    """O fato aponta para dentro de uma fonte oficial (host + caminho). Ser
    pagina citada nao basta: a busca por host traz qualquer *.gov.br."""
    url = str(fato.get("fonte_url") or "").strip()
    if not url.startswith("http"):
        return False
    return _dentro(url, prefixos if prefixos is not None else dominios)


_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


def _so_digitos(n: str) -> str:
    """"1.000,00" -> "1000"; "3,5" -> "35". Centavos zerados (1 ou 2 zeros)
    saem antes; ".000" e' milhar e fica."""
    return re.sub(r"\D", "", re.sub(r"[.,]0{1,2}$", "", n))


def _valor_lido(fato: dict, citacoes: list[dict]) -> bool:
    """Todo numero do `valor` aparece no texto da pagina citada?

    Vale so' quando a citacao traz o `texto` lido — o modo local do llm.py
    (16/10/2026), em que o CODIGO leu a pagina e o modelo local escreveu o
    fato. No teste daquele dia o Qwen deu duas aliquotas de IOF diferentes
    para a mesma pergunta, com toda a seguranca: fato com numero que nao esta'
    na pagina nao entra. Na OpenAI (sem `texto`) nada muda. A comparacao e'
    por digitos, para "3,5%" casar com "3.5 %" e "R$ 1.000" com "1000"."""
    url = str(fato.get("fonte_url") or "").strip().rstrip("/")
    pagina = next((c for c in citacoes if c.get("texto")
                   and c["url"].rstrip("/") == url), None)
    if pagina is None:
        # Citacao sem texto (OpenAI) passa; no modo local, URL fora das
        # paginas lidas nao tem como ser conferida.
        return not any(c.get("texto") for c in citacoes)
    numeros = [_so_digitos(n) for n in _NUMERO.findall(str(fato.get("valor") or ""))]
    if not numeros:
        return True
    lidos = {_so_digitos(n) for n in _NUMERO.findall(pagina["texto"])}
    return all(n in lidos for n in numeros if n)


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
            if (isinstance(f, dict) and f.get("afirmacao")
                    and _fato_confiavel(f, citacoes, dominios, _prefixos_do_hub(hub))
                    and _valor_lido(f, citacoes)
                    and _recente(f, citacoes)):
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
