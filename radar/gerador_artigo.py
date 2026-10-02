"""Artigo de servico para os sites SEM base propria (os blogs Tihee).

O doll tem PTAX: da' para montar artigo por template, porque existe um numero
proprio para dizer. Aqui nao existe base — e por isso este gerador NAO tem
fallback de template. Sem chave da OpenAI ele devolve None e nada e' publicado.

E' deliberado. Template sem dado produziria texto de encheção — exatamente o
"conteudo em escala" que a politica de spam do Google descreve e que este
projeto inteiro existe para evitar. Melhor nao publicar do que publicar vazio.

O QUE ESTE GERADOR ESCREVE — e o que ele NAO escreve:

  escreve : um guia de servico autonomo sobre o TEMA do hub, util sozinho,
            do tipo que se le inteiro e resolve a duvida de quem chegou.
  nao     : reescrita da noticia que originou a pauta.

A pauta do radar entra aqui como SINAL DE ASSUNTO ("este tema esta' quente
agora"), nao como materia-prima. O fato de terceiro so' aparece se for
concreto e verificavel, em uma frase, atribuido e com link — nunca como
apuracao propria. Sem isso, o artigo simplesmente nao o menciona.

E' o que separa este fluxo do risco descrito no README: o site nao herda o
erro de ninguem porque nao esta' repetindo a apuracao de ninguem.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from . import llm
# As funcoes de fontes/dominios moram em radar/pesquisa.py desde o motor
# Discover; ficam importadas aqui porque este modulo e outros as usam.
from .pesquisa import _busca, _dominios_do_hub, _fontes_do_hub  # noqa: F401

FUSO_SP = timezone(timedelta(hours=-3))

# Tamanho alvo. Guia curto demais nao resolve a duvida e nao segura o leitor;
# longo demais vira enrolacao, que o Discover pune como sensacionalismo.
PALAVRAS = "700-1000"


def _manchete(item: dict) -> str:
    """Titulo da noticia sem o sufixo ' - Veiculo' que o feed do Google cola."""
    t = ((item or {}).get("titulo") or "").strip()
    return t.rsplit(" - ", 1)[0].strip() if " - " in t else t


def _veiculo_limpo(item: dict) -> str:
    v = (item or {}).get("veiculo") or ""
    return "" if not v or "google" in v.lower() else v


def _hub_de(site: dict, hub_id: str | None) -> dict:
    for h in site.get("hubs", []) or []:
        if h.get("id") == hub_id:
            return h
    return {}


def _bloco_fontes(hub: dict, citacoes: list[dict] | None = None) -> str:
    """Bloco FIXO 'Fontes e onde conferir', montado pelo codigo — nunca pelo
    modelo. Primeiro as paginas que o modelo de fato CITOU na busca (URLs que
    ele leu), depois as fontes oficiais configuradas no hub que ainda nao
    apareceram. Referencia escrita por LLM sem ter lido nada e' referencia
    inventada, assinada pelo site; por isso o modelo e' instruido a NAO
    escrever secao propria. Sem citacao e sem configuracao = sem bloco."""
    vistas: set[str] = set()
    consultadas, oficiais = [], []
    for c in citacoes or []:
        chave = c["url"].rstrip("/")
        if chave in vistas:
            continue
        vistas.add(chave)
        consultadas.append(f"- [{c.get('titulo') or c['url']}]({c['url']})")
    for f in _fontes_do_hub(hub):
        chave = f["url"].rstrip("/")
        if chave in vistas:
            continue
        vistas.add(chave)
        oficiais.append(f"- [{f['nome']}]({f['url']})")
    if not consultadas and not oficiais:
        return ""
    partes = ["\n\n## Fontes e onde conferir\n"]
    if consultadas:
        partes.append("\nConsultadas para este guia:\n\n" + "\n".join(consultadas) + "\n")
    if oficiais:
        partes.append("\nRegras, prazos e valores mudam; antes de agir, confira "
                      "na fonte oficial:\n\n" + "\n".join(oficiais) + "\n")
    return "".join(partes)


def _sistema(site: dict, hub: dict) -> str:
    busca = ""
    if _busca(site, hub):
        busca = (
            "- Voce TEM uma ferramenta de busca na web, restrita as fontes "
            "oficiais desta secao. USE-A antes de escrever qualquer ponto que "
            "dependa de prazo, valor, taxa, lei, regra ou procedimento (ate "
            f"{llm.MAX_BUSCAS_PADRAO} buscas, objetivas). Afirme numero, lei ou "
            "prazo SOMENTE se encontrou na busca; nesse caso diga de qual orgao "
            "vem. O que a busca nao trouxer, escreva sem o dado ou mande "
            "conferir na fonte oficial.\n")
    return (
        f"Voce e' redator do {site.get('entidade') or site['dominio']}, um site "
        f"brasileiro. A secao e': {hub.get('titulo') or 'geral'}.\n"
        "Voce escreve GUIAS DE SERVICO: textos que resolvem sozinhos a duvida "
        "de quem chegou pela busca. Regras inegociaveis:\n"
        "- O texto tem que se sustentar SEM a noticia que motivou a pauta. "
        "Voce NAO tem o texto dessa noticia — so' a manchete. Nao reescreva "
        "materia alheia, nao repita apuracao de terceiro como se fosse sua.\n"
        "- NUNCA invente numero, preco, data, lei, prazo, estatistica ou "
        "declaracao. Se um dado especifico seria necessario e voce nao o tem "
        "com seguranca, escreva a orientacao sem ele ou diga onde conferir na "
        "fonte oficial. Numero errado assinado pelo site e' pior que numero "
        "nenhum.\n"
        "- Nada sobre pessoa real especifica: sem fofoca, sem atribuir fala ou "
        "ato a alguem nomeado.\n"
        "- Titulo que entrega o conteudo de verdade, sem caca-clique, sem "
        "promessa exagerada e sem esconder o essencial. No maximo 90 "
        "caracteres.\n"
        f"- Portugues do Brasil, tom direto e pratico, {PALAVRAS} palavras.\n"
        "- Estruture com 3 a 5 subtitulos markdown (##). Use lista quando for "
        "mesmo uma lista (passos, itens); nao transforme o texto inteiro em "
        "topicos soltos.\n"
        + busca +
        "- NAO escreva secao de fontes, referencias ou bibliografia, e nao "
        "invente links: o site acrescenta um bloco de fontes oficiais no fim, "
        "montado por ele. Quando mandar o leitor conferir algo, cite a fonte "
        "oficial pelo NOME (as desta secao estao no pedido), sem URL.\n"
        "Responda SO um JSON valido: {\"titulo\": \"...\", \"resumo\": \"...\", "
        "\"corpo_md\": \"...\"} — resumo com uma frase de ate 200 caracteres, "
        "corpo em markdown SEM repetir o titulo como H1.")


def _prompt(pauta: dict, site: dict, hub: dict, leia_tambem: list[dict]) -> str:
    item = pauta.get("itens") or {}
    manchete = _manchete(item)
    veiculo = _veiculo_limpo(item)
    fonte_url = item.get("url") or ""
    hoje = datetime.now(FUSO_SP).date()

    partes = [
        f"Assunto em alta agora (use como TEMA, nao como materia-prima): "
        f"{pauta.get('titulo_sug') or manchete or hub.get('titulo')}",
        f"Secao do site: {hub.get('titulo')} ({hub.get('id')})",
        f"Angulo pedido pela pauta: {pauta.get('angulo') or 'servico'}",
        f"Data de hoje: {hoje:%d/%m/%Y}",
    ]
    if hub.get("termos"):
        partes.append("Vocabulario da secao (o que os leitores procuram): "
                      + ", ".join(str(t) for t in hub["termos"][:12]))
    fontes = _fontes_do_hub(hub)
    if fontes:
        partes.append("Fontes oficiais desta secao (cite pelo nome ao mandar "
                      "conferir; nao cite outras): "
                      + "; ".join(f["nome"] for f in fontes))

    if manchete and fonte_url:
        partes.append(
            f"\nGancho de atualidade — manchete de terceiro: \"{manchete}\""
            + (f" (fonte: {veiculo})" if veiculo else "")
            + f"\nLink da fonte: {fonte_url}\n"
            "Use o gancho SO' se ele acrescentar algo concreto ao guia. Se "
            "usar, no maximo UMA frase, atribuida ("
            f"\"segundo {veiculo or 'a imprensa'}\") e com o link em markdown. "
            "Se o gancho for vago, sensacionalista ou voce nao conseguir "
            "checa-lo, IGNORE — o guia vale sem ele.")

    uteis = [a for a in (leia_tambem or []) if a.get("url_publicada")][:3]
    if uteis:
        partes.append("\nLinks internos para o bloco final 'Leia tambem' "
                      "(use em markdown, so' os que fizerem sentido):\n"
                      + "\n".join(f"- [{a['titulo']}]({a['url_publicada']})"
                                  for a in uteis))

    partes.append("\nEscreva o guia.")
    return "\n".join(partes)


def _jsonld(titulo: str, resumo: str, site: dict, hub: dict) -> str:
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    return json.dumps({
        "@context": "https://schema.org",
        # Article, nao NewsArticle: isto e' guia de servico, nao cobertura de
        # fato apurado. Marcar como noticia o que nao e' noticia e' mentir
        # para o rastreador.
        "@type": "Article",
        "headline": titulo, "description": resumo,
        "datePublished": agora, "dateModified": agora,
        "inLanguage": site.get("idioma", "pt-BR"), "isAccessibleForFree": True,
        "publisher": {"@type": "Organization", "name": site["entidade"]},
        "about": {"@type": "Thing", "name": hub.get("titulo") or site["entidade"]},
    }, ensure_ascii=False, indent=2)


def _le_json_artigo(saida: str | None) -> tuple[str, str, str] | None:
    """(titulo, corpo, resumo) do JSON do modelo, ou None se nao serve."""
    if not saida:
        return None
    bruto = re.search(r"\{.*\}", saida, re.S)
    if not bruto:
        return None
    try:
        d = json.loads(bruto.group(0))
    except json.JSONDecodeError:
        return None
    titulo = str(d.get("titulo") or "").strip()[:110]
    corpo = str(d.get("corpo_md") or "").strip()
    resumo = str(d.get("resumo") or "").strip()[:280]
    # Portao de qualidade: guia curto demais nao resolve nada e nao deveria
    # ocupar uma vaga do dia. Cai fora em vez de virar post raso.
    if not titulo or len(corpo) < 1200:
        return None
    if not resumo:
        resumo = corpo.split("\n\n")[0][:280]
    return titulo, corpo, resumo


# -- motor Discover: escrita a partir do BRIEF -------------------------------

def _sistema_brief(site: dict, hub: dict, brief: dict | None = None) -> str:
    from .brief import regras_editoriais
    linha = (brief or {}).get("linha_editorial") or {}
    return (
        f"Voce e' redator do {site.get('entidade') or site['dominio']}, um site "
        f"brasileiro. A secao e': {hub.get('titulo') or 'geral'}. Leitor: "
        f"{hub.get('perfil_leitor') or 'publico geral'}.\n"
        "Voce escreve a partir de um BRIEF fechado. Regras inegociaveis:\n"
        "- A manchete promete X; o texto ENTREGA X, logo no comeco e ate o fim.\n"
        "- Numero, preco, data, lei, prazo, estatistica: SOMENTE os que estao em "
        "KEY_FACTS, com o mesmo valor. Fora deles, NENHUM numero. Se faltar "
        "dado, oriente e mande conferir na fonte oficial pelo NOME.\n"
        "- Cada secao do brief vira um subtitulo markdown (##), na ordem dada, "
        "cobrindo os pontos listados. Nao crie secoes extras.\n"
        "- Nada sobre pessoa real nomeada. Nada de \"segundo especialistas\" "
        "ou \"estudos mostram\".\n"
        "- Links: SO' os links internos do brief, em markdown, onde fizerem "
        "sentido. NAO escreva secao de fontes/referencias (o site monta).\n"
        f"- Portugues do Brasil, tom direto e pratico, {PALAVRAS} palavras. "
        "Use lista quando for mesmo lista.\n"
        + regras_editoriais(linha.get("texto"), linha.get("formato")) +
        "Responda SO um JSON valido: {\"titulo\": \"...\", \"resumo\": \"...\", "
        "\"corpo_md\": \"...\"} — titulo = a discover_headline do brief, resumo = "
        "o dek, corpo em markdown SEM repetir o titulo como H1.")


def _prompt_brief(brief: dict, evidencias: dict) -> str:
    fatos = brief.get("key_facts") or []
    partes = [
        f"MANCHETE (use exatamente): {brief.get('discover_headline')}",
        f"DEK: {brief.get('dek')}",
        f"ANGULO: {brief.get('main_angle')}",
        f"POR QUE AGORA: {brief.get('why_now')}",
        f"INSIGHT PROPRIO (o que so' este texto diz): {brief.get('original_insight')}",
        f"Data de hoje: {datetime.now(FUSO_SP).date():%d/%m/%Y}",
        "KEY_FACTS (os unicos numeros/prazos/regras permitidos):\n"
        + ("\n".join(f"- f{i + 1}: {f['fato']}" for i, f in enumerate(fatos)) or "- (nenhum: nao afirme numero)"),
        "SECOES (cada uma vira um ##, nesta ordem):\n"
        + "\n".join(f"{i + 1}. {s['h2']} — {s.get('objetivo') or ''}"
                    + ("\n   pontos: " + "; ".join(s.get("pontos") or []) if s.get("pontos") else "")
                    + ("\n   fatos: " + ", ".join(s.get("fatos_ids") or []) if s.get("fatos_ids") else "")
                    for i, s in enumerate(brief.get("sections") or [])),
    ]
    if evidencias.get("fontes_oficiais"):
        partes.append("Fontes oficiais (cite pelo nome ao mandar conferir): "
                      + "; ".join(f["nome"] for f in evidencias["fontes_oficiais"]))
    if brief.get("internal_links"):
        partes.append("Links internos permitidos:\n"
                      + "\n".join(f"- [{l['titulo']}]({l['url']})" for l in brief["internal_links"]))
    partes.append("\nEscreva o artigo.")
    return "\n".join(partes)


def monta_do_brief(brief: dict, evidencias: dict, site: dict, hub: dict) -> dict | None:
    """Artigo escrito a partir do brief (motor Discover). Sem busca aqui: a
    pesquisa ja' foi feita. Devolve o mesmo formato de `monta`."""
    if not llm.tem_chave():
        return None
    saida = llm.gera(_prompt_brief(brief, evidencias), sistema=_sistema_brief(site, hub, brief),
                     max_tokens=5000)
    lido = _le_json_artigo(saida)
    if not lido:
        return None
    titulo, corpo, resumo = lido
    titulo = brief.get("discover_headline") or titulo
    resumo = brief.get("dek") or resumo
    citacoes = [{"url": p["url"], "titulo": p.get("titulo")} for p in brief.get("primary_sources") or []]
    return {"titulo": titulo, "markdown": f"# {titulo}\n\n{corpo}\n" + _bloco_fontes(hub, citacoes),
            "resumo": resumo, "jsonld": _jsonld(titulo, resumo, site, hub),
            "citacoes": len(citacoes)}


def corrige(artigo: dict, problemas: list[str], brief: dict, evidencias: dict,
            site: dict, hub: dict) -> dict | None:
    """Uma unica rodada de correcao dos problemas listados pela checagem,
    sem inventar dado. None se nao der."""
    if not llm.tem_chave() or not problemas:
        return None
    corpo_atual = (artigo.get("markdown") or "").split("\n## Fontes e onde conferir")[0]
    prompt = (_prompt_brief(brief, evidencias)
              + "\n\nO ARTIGO ABAIXO FOI REPROVADO na checagem. Corrija SOMENTE os "
              "problemas listados, mantendo o resto. Nao acrescente numero que nao "
              "esteja em KEY_FACTS; se o problema e' um numero sem fato, REMOVA o numero.\n"
              "PROBLEMAS:\n- " + "\n- ".join(problemas)
              + "\n\nARTIGO ATUAL:\n" + corpo_atual[:14000])
    saida = llm.gera(prompt, sistema=_sistema_brief(site, hub, brief), max_tokens=5000)
    lido = _le_json_artigo(saida)
    if not lido:
        return None
    titulo, corpo, resumo = lido
    titulo = brief.get("discover_headline") or titulo
    citacoes = [{"url": p["url"], "titulo": p.get("titulo")} for p in brief.get("primary_sources") or []]
    return {**artigo, "titulo": titulo,
            "markdown": f"# {titulo}\n\n{corpo}\n" + _bloco_fontes(hub, citacoes),
            "resumo": brief.get("dek") or resumo}


def monta(pauta: dict, site: dict, leia_tambem: list[dict] | None = None) -> dict | None:
    """Devolve {titulo, markdown, resumo, jsonld} ou None se nao der para
    escrever com seguranca (sem chave, sem SDK, saida pobre ou malformada).

    Pauta com `brief` (motor Discover) vai por `monta_do_brief`; as demais
    (radar antigo, calendario) seguem o caminho da manchete."""
    if not llm.tem_chave():
        return None

    hub = pauta.get("_hub") or _hub_de(site, pauta.get("hub"))
    if pauta.get("brief"):
        return monta_do_brief(pauta["brief"], pauta.get("evidencias") or {}, site, hub)
    dominios = _busca(site, hub)
    if dominios:
        # Com busca: o modelo le as fontes oficiais antes de escrever, e as
        # citacoes viram o bloco de fontes. Sai mais caro (cada busca e'
        # cobrada a parte, mais os tokens das paginas lidas) e e' o que da'
        # prazo, lei e valor de verdade ao texto.
        saida, citacoes = llm.gera_com_busca(
            _prompt(pauta, site, hub, leia_tambem or []), dominios,
            sistema=_sistema(site, hub), max_tokens=6000)
    else:
        saida = llm.gera(_prompt(pauta, site, hub, leia_tambem or []),
                         sistema=_sistema(site, hub), max_tokens=4000)
        citacoes = []
    lido = _le_json_artigo(saida)
    if not lido:
        return None
    titulo, corpo, resumo = lido
    markdown = f"# {titulo}\n\n{corpo}\n" + _bloco_fontes(hub, citacoes)
    return {"titulo": titulo, "markdown": markdown,
            "resumo": resumo, "jsonld": _jsonld(titulo, resumo, site, hub),
            "citacoes": len(citacoes)}
