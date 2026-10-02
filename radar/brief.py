"""Editorial Brief: o plano do artigo, em JSON, ANTES de qualquer texto.

Campos (contrato com gerador_artigo.monta_do_brief, checagem e discover):
  headline_options[]  discover_headline  seo_title  dek  main_angle
  reader_profile  why_now  key_facts[{fato, fonte_url}]  primary_sources[{url, titulo}]
  original_insight  sections[{h2, objetivo, pontos[], fatos_ids[]}]
  visual_concept  image_prompt  entities[]  internal_links[{titulo, url}]

Uma chamada ao modelo. Depois, `valida_brief` corrige o que da' e remove o
que nao pode ficar: fato sem fonte citada, link interno que nao existe,
manchete caca-clique, prompt de imagem com pessoa real/marca/texto.
"""
from __future__ import annotations

import json
import re

from . import llm

CACA_CLIQUE = re.compile(
    r"voc[eê] n[aã]o vai acreditar|chocante|bombou|inacredit[aá]vel|!!+|"
    r"o que aconteceu depois|ningu[eé]m esperava|segredo que|m[eé]dicos odeiam",
    re.I)
PROIBIDO_IMAGEM = re.compile(
    r"\b(rosto|face|celebridade|famos[oa]|logo(tipo)?|marca|texto|letreiro|"
    r"placa com|bandeira|crian[cç]a|bebe|beb[eê])\b", re.I)
MIN_HEADLINES = 3
# Pauta-lista ("10 receitas de...", "7 ideias para..."): barrada quando a
# linha editorial do site pede um assunto por pauta (formato "individual").
LISTA = re.compile(
    r"^\s*\d+\s|\b(\d+|duas|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|doze|quinze|vinte)\s+"
    r"(receitas|ideias|dicas|pratos|op[cç][oõ]es|formas|jeitos|lanches|sobremesas|bolos|doces|"
    r"petiscos|sugest[oõ]es|maneiras|truques|combina[cç][oõ]es)\b|\breceitas\b", re.I)


def regras_editoriais(texto: str | None, formato: str | None) -> str:
    """Bloco de regras da linha editorial do site (tela Radar), para colar
    nos prompts de angulo, brief e redacao. Vazio se nao ha' regra."""
    partes = []
    if formato == "individual":
        partes.append("- FORMATO: um unico assunto por artigo (uma receita, um prato, um tema). "
                      "PROIBIDO lista, coletanea ou ranking (\"5 receitas\", \"10 ideias\").")
    if texto and texto.strip():
        partes.append(f"- LINHA EDITORIAL DO SITE (siga a risca): {texto.strip()}")
    return ("\n".join(partes) + "\n") if partes else ""


def _caixa_alta_demais(t: str) -> bool:
    letras = [c for c in t if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.4


def manchete_ok(t: str) -> bool:
    t = (t or "").strip()
    return 20 <= len(t) <= 90 and not CACA_CLIQUE.search(t) and not _caixa_alta_demais(t)


def _sistema(site: dict, hub: dict) -> str:
    autor = (site.get("autor") or {}).get("nome") or site.get("entidade")
    return (
        f"Voce e' editor-chefe do {site.get('entidade') or site.get('dominio')}, secao "
        f"\"{hub.get('titulo')}\". Assina como {autor}. Monte o BRIEF de um artigo "
        "para o Google Discover. Regras:\n"
        "- A manchete promete exatamente o que o texto vai entregar. Sem "
        "caca-clique, sem exagero, sem pergunta vazia. Ate 90 caracteres.\n"
        "- Numeros, prazos, leis e valores SO' dos FATOS fornecidos, cada um "
        "com a mesma fonte_url. Sem fato fornecido, o artigo nao afirma numero.\n"
        "- Nada sobre pessoa real nomeada. Nenhuma marca no conceito visual; "
        "a imagem nao tem texto nem rosto reconhecivel.\n"
        "- Links internos SO' da lista fornecida.\n"
        "- `original_insight`: a leitura propria que nenhum concorrente da lista fez.\n"
        + regras_editoriais(site.get("_linha_editorial"), site.get("_formato")) +
        "Responda SO um JSON com EXATAMENTE estas chaves: headline_options "
        "(3 a 6 strings), discover_headline (uma das options), seo_title (ate 60), "
        "dek (120 a 200 caracteres), main_angle, reader_profile, why_now, "
        "key_facts (lista de {fato, fonte_url}), primary_sources (lista de {url, titulo}), "
        "original_insight, sections (3 a 6 de {h2, objetivo, pontos: [..], fatos_ids: [..]}), "
        "visual_concept, image_prompt (em ingles, cena concreta, sem texto/logo/rosto), "
        "entities (lista de strings), internal_links (lista de {titulo, url}).")


def _prompt(ideia: dict, angulo: dict, ev: dict, hub: dict) -> str:
    partes = [
        f"IDEIA: {ideia.get('titulo')}",
        f"ANGULO: {angulo.get('titulo_trabalho')} (tipo {angulo.get('tipo')})",
        f"Promessa ao leitor: {angulo.get('promessa')}",
        f"Por que agora: {angulo.get('por_que_agora') or ideia.get('motivo') or ''}",
        f"Leitor: {hub.get('perfil_leitor') or 'publico geral da secao'}",
    ]
    if angulo.get("perguntas_respondidas"):
        partes.append("Perguntas a responder:\n- " + "\n- ".join(angulo["perguntas_respondidas"]))
    if ev.get("fatos"):
        partes.append("FATOS (os unicos numeros/prazos/regras permitidos; ids f1..fn):\n"
                      + "\n".join(f"- f{i + 1}: {f['afirmacao']} [{f.get('valor') or ''}] "
                                  f"— fonte_url: {f['fonte_url']}"
                                  for i, f in enumerate(ev["fatos"])))
    else:
        partes.append("FATOS: nenhum levantado. O artigo NAO deve afirmar numero, "
                      "prazo ou lei; oriente e mande conferir na fonte oficial.")
    if ev.get("fontes_oficiais"):
        partes.append("Fontes oficiais da secao (cite pelo nome): "
                      + "; ".join(f["nome"] for f in ev["fontes_oficiais"]))
    if ev.get("perguntas"):
        partes.append("Perguntas das pessoas (PAA): " + " | ".join(ev["perguntas"][:8]))
    if ev.get("noticias_recentes"):
        partes.append("Manchetes recentes (so' titulos): "
                      + " | ".join(f"{m.get('titulo')} ({m.get('veiculo') or ''})"
                                   for m in ev["noticias_recentes"][:5]))
    if ev.get("cobertura_concorrente"):
        partes.append("O que os concorrentes ja' dizem (titulo: snippet):\n- "
                      + "\n- ".join(f"{o.get('titulo')}: {o.get('snippet') or ''}"
                                    for o in ev["cobertura_concorrente"][:5]))
    if ev.get("historico_site"):
        partes.append("Links internos disponiveis (use so' estes):\n- "
                      + "\n- ".join(f"{a['titulo']} -> {a['url']}" for a in ev["historico_site"]))
    partes.append("\nMonte o brief.")
    return "\n".join(partes)


def monta_brief(ideia: dict, angulo: dict, evidencias: dict, site: dict, hub: dict) -> dict | None:
    if not llm.tem_chave():
        return None
    saida = llm.gera(_prompt(ideia, angulo, evidencias, hub), sistema=_sistema(site, hub),
                     max_tokens=3000, json_obj=True)
    if not saida:
        return None
    bruto = re.search(r"\{.*\}", saida, re.S)
    try:
        dados = json.loads(bruto.group(0)) if bruto else None
    except json.JSONDecodeError:
        dados = None
    if not isinstance(dados, dict):
        return None
    formato = site.get("_formato") or "livre"
    brief, problemas = valida_brief(dados, evidencias, formato)
    if brief is None:
        print(f"  [brief] rejeitado: {'; '.join(problemas)[:200]}")
        return None
    if problemas:
        print(f"  [brief] ajustado: {'; '.join(problemas)[:200]}")
    brief["angulo"] = {k: angulo.get(k) for k in ("id", "tipo", "titulo_trabalho", "promessa",
                                                   "por_que_agora", "risco_factual")}
    # A linha editorial viaja no brief: o redator e a correcao a obedecem
    # sem precisar ler `metas` de novo.
    brief["linha_editorial"] = {"texto": site.get("_linha_editorial") or "", "formato": formato}
    return brief


def _lista(v) -> list:
    return v if isinstance(v, list) else []


def valida_brief(b: dict, ev: dict, formato: str = "livre") -> tuple[dict | None, list[str]]:
    """Corrige o que da', remove o que nao pode, lista o que mudou. Devolve
    (None, motivos) quando o brief nao serve. `formato="individual"` barra
    manchete de lista."""
    problemas: list[str] = []
    saida: dict = {}

    opcoes = [str(h).strip() for h in _lista(b.get("headline_options")) if str(h).strip()]
    validas = [h for h in opcoes if manchete_ok(h)
               and not (formato == "individual" and LISTA.search(h))]
    if len(validas) < len(opcoes):
        problemas.append(f"{len(opcoes) - len(validas)} manchete(s) removida(s) (caca-clique/tamanho/lista)")
    if len(validas) < MIN_HEADLINES:
        return None, problemas + [f"menos de {MIN_HEADLINES} manchetes validas"]
    saida["headline_options"] = validas[:6]
    dh = str(b.get("discover_headline") or "").strip()
    if dh not in validas:
        problemas.append("discover_headline fora das opcoes; usando a primeira")
        dh = validas[0]
    saida["discover_headline"] = dh

    seo = str(b.get("seo_title") or dh).strip()
    saida["seo_title"] = seo[:60]
    dek = " ".join(str(b.get("dek") or "").split())
    if not 80 <= len(dek) <= 240:
        problemas.append(f"dek com {len(dek)} caracteres")
    saida["dek"] = dek[:240]

    for chave in ("main_angle", "reader_profile", "why_now", "original_insight",
                  "visual_concept", "image_prompt"):
        saida[chave] = str(b.get(chave) or "").strip()[:600]

    # fatos: so' os que apontam para fonte de verdade levantada
    permitidas = {f["fonte_url"].rstrip("/") for f in ev.get("fatos") or []}
    permitidas |= {p["url"].rstrip("/") for p in ev.get("fontes_primarias") or []}
    fatos = []
    for f in _lista(b.get("key_facts")):
        if not isinstance(f, dict) or not f.get("fato"):
            continue
        url = str(f.get("fonte_url") or "").strip().rstrip("/")
        if url in permitidas:
            fatos.append({"fato": str(f["fato"]).strip()[:400], "fonte_url": url})
    removidos = len(_lista(b.get("key_facts"))) - len(fatos)
    if removidos > 0:
        problemas.append(f"{removidos} key_fact(s) sem fonte levantada removido(s)")
    saida["key_facts"] = fatos[:15]

    fontes = []
    vistas: set[str] = set()
    for p in _lista(b.get("primary_sources")):
        if not isinstance(p, dict):
            continue
        url = str(p.get("url") or "").strip().rstrip("/")
        if url in permitidas and url not in vistas:
            vistas.add(url)
            fontes.append({"url": url, "titulo": str(p.get("titulo") or url).strip()[:160]})
    for p in ev.get("fontes_primarias") or []:
        u = p["url"].rstrip("/")
        if u not in vistas and any(f["fonte_url"] == u for f in fatos):
            vistas.add(u)
            fontes.append({"url": u, "titulo": p.get("titulo") or u})
    saida["primary_sources"] = fontes[:12]

    secoes = []
    for s in _lista(b.get("sections")):
        if isinstance(s, dict) and s.get("h2"):
            secoes.append({"h2": str(s["h2"]).strip()[:120],
                           "objetivo": str(s.get("objetivo") or "").strip()[:300],
                           "pontos": [str(p)[:200] for p in _lista(s.get("pontos"))][:8],
                           "fatos_ids": [str(x) for x in _lista(s.get("fatos_ids"))][:8]})
    if not 3 <= len(secoes) <= 6:
        if len(secoes) < 3:
            return None, problemas + [f"{len(secoes)} secao(oes); minimo 3"]
        problemas.append(f"{len(secoes)} secoes; cortadas para 6")
        secoes = secoes[:6]
    saida["sections"] = secoes

    if PROIBIDO_IMAGEM.search(saida["image_prompt"]):
        problemas.append("image_prompt com pessoa/marca/texto; usando o visual_concept")
        saida["image_prompt"] = saida["visual_concept"]
    saida["entities"] = [str(e).strip()[:80] for e in _lista(b.get("entities")) if str(e).strip()][:12]

    internos = {a["url"].rstrip("/"): a["titulo"] for a in ev.get("historico_site") or [] if a.get("url")}
    links = []
    for l in _lista(b.get("internal_links")):
        if isinstance(l, dict):
            u = str(l.get("url") or "").strip().rstrip("/")
            if u in internos:
                links.append({"titulo": str(l.get("titulo") or internos[u]).strip()[:160], "url": u})
    rem = len(_lista(b.get("internal_links"))) - len(links)
    if rem > 0:
        problemas.append(f"{rem} link(s) interno(s) inexistente(s) removido(s)")
    saida["internal_links"] = links[:5]
    return saida, problemas
