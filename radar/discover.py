"""Discover Optimizer: o pacote final antes do WordPress.

  escolhe_manchete  entre as headline_options do brief, a que melhor serve
                    ao card do Discover (tamanho, entidade, sem caca-clique)
  gera_imagem       imagem destacada gerada por IA a partir do image_prompt
                    do brief (>= 1200 px, paisagem, sem texto/rosto/marca);
                    se falhar ou estiver desligada, cai no acervo (Pexels)
  jsonld_discover   Article com autor real (Person), dek, entidades e datas
  otimiza           junta tudo num artigo pronto para publicador_wp.publica

IMAGENS_IA=0 desliga a geracao (interruptor de emergencia de custo).
"""
from __future__ import annotations

import json
from datetime import datetime

from . import imagens, llm
from .brief import CACA_CLIQUE
from .config import env

MAX_BYTES = imagens.MAX_BYTES


def escolhe_manchete(brief: dict) -> str:
    """Pontua as opcoes: 45-85 caracteres (+2), contem uma entidade (+1),
    comeca com palavra forte em vez de artigo (+1), caca-clique elimina.
    Empate: a discover_headline do brief."""
    opcoes = [h for h in (brief.get("headline_options") or []) if h and not CACA_CLIQUE.search(h)]
    preferida = brief.get("discover_headline") or (opcoes[0] if opcoes else "")
    entidades = [e.lower() for e in (brief.get("entities") or [])]
    melhor, nota_melhor = preferida, -1
    for h in opcoes:
        nota = 0
        if 45 <= len(h) <= 85:
            nota += 2
        if any(e and e in h.lower() for e in entidades):
            nota += 1
        if not h.split()[0].lower() in ("o", "a", "os", "as", "um", "uma"):
            nota += 1
        if h == preferida:
            nota += 0.5
        if nota > nota_melhor:
            melhor, nota_melhor = h, nota
    return melhor[:90]


def _prompt_imagem(brief: dict, site: dict, hub: dict) -> str:
    estilo = hub.get("estilo_visual") or site.get("estilo_visual") or "editorial photography, natural light"
    conceito = brief.get("image_prompt") or brief.get("visual_concept") or hub.get("imagem") or ""
    return (f"{conceito}. Style: {estilo}. Landscape 3:2 composition for a news card. "
            "No text, no letters, no logos, no brand names, no recognizable faces, no watermark.")


def gera_imagem(brief: dict, site: dict, hub: dict) -> dict | None:
    """Imagem no formato de imagens.busca ({conteudo, tipo, largura, altura,
    alt, credito, origem_url}) ou None."""
    if env("IMAGENS_IA") == "0" or hub.get("imagem") is False:
        return None
    dados = llm.gera_imagem(_prompt_imagem(brief, site, hub))
    if not dados:
        return None
    medida = imagens.dimensoes(dados)
    if not medida or not imagens.serve(*medida) or len(dados) > MAX_BYTES:
        print(f"  [imagem] gerada fora do padrao ({medida}, {len(dados)} bytes)")
        return None
    return {"conteudo": dados, "tipo": "image/jpeg", "largura": medida[0], "altura": medida[1],
            "alt": (brief.get("visual_concept") or "")[:200],
            "credito": "Ilustração gerada por IA", "fonte": "IA",
            "origem_url": f"ia:{llm.MODELO_IMAGEM}:{hash(brief.get('image_prompt') or '') & 0xffffffff:08x}"}


def jsonld_discover(titulo: str, brief: dict, site: dict, hub: dict, agora: datetime | None = None) -> str:
    agora = agora or datetime.now().astimezone()
    quando = agora.isoformat(timespec="seconds")
    autor = (site.get("autor") or {}).get("nome")
    dados = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": titulo,
        "description": brief.get("dek") or "",
        "datePublished": quando, "dateModified": quando,
        "inLanguage": site.get("idioma", "pt-BR"), "isAccessibleForFree": True,
        "publisher": {"@type": "Organization", "name": site.get("entidade") or site.get("dominio")},
        "about": {"@type": "Thing", "name": hub.get("titulo") or site.get("entidade")},
    }
    if autor:
        dados["author"] = {"@type": "Person", "name": autor}
    if brief.get("entities"):
        dados["keywords"] = ", ".join(brief["entities"][:10])
    return json.dumps(dados, ensure_ascii=False, indent=2)


def otimiza(artigo: dict, brief: dict, site: dict, hub: dict) -> dict:
    """Artigo com manchete escolhida, dek como resumo, JSON-LD com autor e
    imagem pronta (IA) quando houver. Nao altera o corpo."""
    titulo = escolhe_manchete(brief) or artigo["titulo"]
    corpo = artigo.get("markdown") or artigo.get("corpo_md") or ""
    if corpo.startswith("# "):
        corpo = f"# {titulo}\n" + corpo.split("\n", 1)[1]
    saida = {**artigo, "titulo": titulo, "markdown": corpo,
             "resumo": (brief.get("dek") or artigo.get("resumo") or "")[:280],
             "jsonld": jsonld_discover(titulo, brief, site, hub)}
    if not artigo.get("wp_media_id"):
        pronta = gera_imagem(brief, site, hub)
        if pronta:
            saida["imagem_pronta"] = pronta
            print(f"  [imagem] gerada por IA {pronta['largura']}x{pronta['altura']}")
    return saida
