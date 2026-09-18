"""Artigo de servico para os sites SEM base propria (os blogs Tihee).

O doll tem PTAX: da' para montar artigo por template, porque existe um numero
proprio para dizer. Aqui nao existe base — e por isso este gerador NAO tem
fallback de template. Sem chave do Claude ele devolve None e nada e' publicado.

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


def _sistema(site: dict, hub: dict) -> str:
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


def monta(pauta: dict, site: dict, leia_tambem: list[dict] | None = None) -> dict | None:
    """Devolve {titulo, markdown, resumo, jsonld} ou None se nao der para
    escrever com seguranca (sem chave, sem SDK, saida pobre ou malformada)."""
    if not llm.tem_chave():
        return None

    hub = _hub_de(site, pauta.get("hub"))
    saida = llm.gera(_prompt(pauta, site, hub, leia_tambem or []),
                     sistema=_sistema(site, hub), max_tokens=4000)
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

    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    jsonld = json.dumps({
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

    return {"titulo": titulo, "markdown": f"# {titulo}\n\n{corpo}\n",
            "resumo": resumo, "jsonld": jsonld}
