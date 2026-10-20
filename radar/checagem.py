"""Quality / Fact Checker: o UNICO portao antes do WordPress nos sites com
`motor: discover`. Nao ha' revisao humana na fila — entao a checagem tem
que ser cetica.

Duas camadas:
  checa_estrutura  deterministica: tamanho, H2, promessa do titulo entregue
                   no corpo, todo numero do corpo presente nos fatos do
                   brief, todo link numa lista permitida, caca-clique.
  checa_ia         o modelo relê o texto contra os fatos e diz se entrega
                   a manchete, com nota de qualidade e risco factual (schema
                   portado do validate-article/content-audit do conteudo.tihee).

`checa()` junta as duas e devolve {aprovado, motivo, estrutural, qa,
corrigivel}. Reprovado vira artigo 'reprovada' e ideia 'reprovada'.
"""
from __future__ import annotations

import json
import re

from . import llm
from .brief import CACA_CLIQUE

LIMIAR_QUALIDADE = 70
LIMIAR_TOM = 70
PALAVRAS_MIN, PALAVRAS_MAX = 600, 1500
H2_MIN, H2_MAX = 3, 6
PROMESSA_MIN = 0.5      # fracao dos tokens do titulo que precisa aparecer no corpo
SEM_FONTE = re.compile(r"segundo especialistas|estudos (mostram|apontam|indicam)|"
                       r"pesquisas (mostram|apontam|indicam)|dados (mostram|apontam)", re.I)
# numeros que importam: percentuais, valores, anos, prazos. Ignora numeros
# de lista (1., 2.) e horas soltas.
NUMERO = re.compile(r"(?<![\w.])(R\$\s?\d[\d.,]*|\d+(?:[.,]\d+)?\s?%|\d{1,2}/\d{1,2}/\d{2,4}|"
                    r"\b(?:19|20)\d{2}\b|\b\d+(?:[.,]\d+)?\s?(?:mil|milh[oõ]es|bilh[oõ]es|dias|"
                    r"horas|anos|meses|km|kg|g|ml|minutos)\b)")
URL = re.compile(r"\((https?://[^)\s]+)\)")
LINK_MD = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
# IOF (ensaio dos guias de 20/10/2026: o Qwen escreveu 6,38%, dado de 2020,
# e "conta global sem IOF"). A aliquota vem do sites.yaml, nunca do modelo.
IOF_PCT = re.compile(r"\bIOF\b[^.%\n]{0,40}?(\d+(?:[.,]\d+)?)\s?%|"
                     r"(\d+(?:[.,]\d+)?)\s?%\s(?:de\s)?(?:de\s)?IOF\b", re.I)
IOF_ISENTO = re.compile(r"(sem|isen\w*|livre\w* de|zer\w*|reduz\w*|menor|mais baix\w*|"
                        r"descont\w*)\s(?:\w+\s){0,3}?(?:o\s|do\s|de\s)?IOF\b|"
                        r"\bIOF\s(?:\w+\s){0,2}?(menor|reduzid\w*|zero|isent\w*|descontad\w*)", re.I)


def _tokens(t: str) -> set[str]:
    from .normaliza import normaliza_titulo
    return {x for x in normaliza_titulo(t or "").split() if len(x) >= 4}


def _numeros(texto: str) -> list[str]:
    return [m.group(1).strip() for m in NUMERO.finditer(texto or "")]


def _norm_num(n: str) -> str:
    """'3,50%' e '3,5%' sao o mesmo numero; '1.000' vira '1000'."""
    n = re.sub(r"\s+", "", n.lower().replace(".", "").replace(",", "."))
    return re.sub(r"(\.\d*?)0+(?=\D|$)", r"\1", n).replace(".%", "%").rstrip(".")


def aliquotas_iof(site: dict | None) -> list[float]:
    return [float(v) for v in ((site or {}).get("iof") or {}).values()
            if isinstance(v, (int, float))]


def checa_iof(texto: str, site: dict | None) -> list[str]:
    """Todo IOF do texto e' a aliquota vigente do site, e nada de 'sem IOF'."""
    vigentes = aliquotas_iof(site)
    if not vigentes:
        return []
    certo = "/".join(f"{v:.2f}".replace(".", ",") + "%" for v in sorted(set(vigentes)))
    problemas = []
    for m in IOF_PCT.finditer(texto or ""):
        bruto = m.group(1) or m.group(2)
        if not any(abs(float(bruto.replace(",", ".")) - v) < 0.005 for v in vigentes):
            problemas.append(f"IOF de {bruto}% errado: o vigente e' {certo}")
    m = IOF_ISENTO.search(texto or "")
    if m:
        problemas.append(f"IOF \"{m.group(0)}\": nao ha' IOF menor, isento ou "
                         f"descontado nesses meios; o vigente e' {certo}, somado ao custo")
    return list(dict.fromkeys(problemas))


def checa_estrutura(artigo: dict, brief: dict, evidencias: dict, hub: dict,
                    site: dict | None = None) -> list[str]:
    problemas: list[str] = []
    titulo = artigo.get("titulo") or ""
    corpo = artigo.get("corpo_md") or artigo.get("markdown") or ""
    corpo_sem_fontes = corpo.split("\n## Fontes e onde conferir")[0]

    palavras = len(corpo_sem_fontes.split())
    if not PALAVRAS_MIN <= palavras <= PALAVRAS_MAX:
        problemas.append(f"{palavras} palavras (esperado {PALAVRAS_MIN}-{PALAVRAS_MAX})")
    h2 = len(re.findall(r"^## ", corpo_sem_fontes, re.M))
    if not H2_MIN <= h2 <= H2_MAX:
        problemas.append(f"{h2} subtitulos H2 (esperado {H2_MIN}-{H2_MAX})")
    if re.search(r"^# ", corpo_sem_fontes.split("\n", 1)[-1] if corpo_sem_fontes.startswith("# ") else corpo_sem_fontes, re.M):
        problemas.append("H1 repetido no corpo")
    if len(titulo) > 90:
        problemas.append(f"titulo com {len(titulo)} caracteres")
    if CACA_CLIQUE.search(titulo):
        problemas.append("titulo caca-clique")

    tt = _tokens(titulo)
    if tt:
        presentes = sum(1 for t in tt if t in _tokens(corpo_sem_fontes))
        if presentes / len(tt) < PROMESSA_MIN:
            problemas.append(f"promessa do titulo pouco presente no corpo ({presentes}/{len(tt)} termos)")

    permitidos = set()
    for f in (brief.get("key_facts") or []):
        permitidos |= {_norm_num(n) for n in _numeros(f.get("fato") or "")}
    for f in (evidencias.get("fatos") or []):
        permitidos |= {_norm_num(n) for n in _numeros(f"{f.get('afirmacao') or ''} {f.get('valor') or ''}")}
    # O texto dos links internos ("Dolar fecha em R$ 5,0564...") e' titulo de
    # post do proprio site, nao afirmacao do guia: fica fora da contagem
    # (reprovou 3 de 5 guias no ensaio de 20/10, inclusive o unico limpo).
    so_texto = LINK_MD.sub("", corpo_sem_fontes)
    soltos = sorted({n for n in _numeros(so_texto) if _norm_num(n) not in permitidos})
    if soltos:
        problemas.append("numero(s) sem fato no brief: " + ", ".join(soltos[:6]))

    links_ok = {l["url"].rstrip("/") for l in (brief.get("internal_links") or [])}
    links_ok |= {p["url"].rstrip("/") for p in (brief.get("primary_sources") or [])}
    links_ok |= {str(f.get("url") or "").rstrip("/") for f in (hub.get("fontes") or []) if isinstance(f, dict)}
    fora = sorted({u for u in URL.findall(corpo_sem_fontes) if u.rstrip("/") not in links_ok})
    if fora:
        problemas.append("link(s) fora da lista: " + ", ".join(fora[:4]))

    if SEM_FONTE.search(corpo_sem_fontes):
        problemas.append("afirmacao vaga sem fonte (\"segundo especialistas\")")
    problemas += checa_iof(f"{titulo}\n{so_texto}", site)
    return problemas


def _sistema_qa() -> str:
    return (
        "Voce e' revisor cetico de um site brasileiro. Compare o ARTIGO com o BRIEF "
        "e os FATOS. Avalie: (1) o texto entrega o que a manchete promete? "
        "(2) todo numero, prazo, lei ou valor do texto esta' nos fatos, com a mesma "
        "fonte? (3) qualidade: util, claro, sem encheção, sem repeticao; (4) tom: "
        "direto e pratico, sem sensacionalismo. Liste cada afirmacao suspeita.\n"
        "Responda SO um JSON: {\"qualidade_score\": 0-100, \"tom_score\": 0-100, "
        "\"entrega_promessa\": true|false, \"factcheck\": {\"risco\": \"baixo|medio|alto\", "
        "\"observacoes\": [\"...\"]}, \"problemas\": [\"...\"], "
        "\"evidencias\": [{\"claim\": \"...\", \"fonte_url\": \"...\", "
        "\"valor_no_post\": \"...\", \"valor_correto\": \"...\"}]}")


def checa_ia(artigo: dict, brief: dict, evidencias: dict) -> dict | None:
    if not llm.tem_chave():
        return None
    fatos = "\n".join(f"- {f.get('fato')} ({f.get('fonte_url')})" for f in brief.get("key_facts") or []) or "- (nenhum)"
    prompt = (f"MANCHETE: {artigo.get('titulo')}\nPROMESSA (brief): {brief.get('dek')}\n"
              f"ANGULO: {brief.get('main_angle')}\nFATOS PERMITIDOS:\n{fatos}\n\n"
              f"ARTIGO:\n{(artigo.get('corpo_md') or artigo.get('markdown') or '')[:12000]}\n\nAvalie.")
    d = None
    for _ in range(2):   # JSON falho e' intermitente no modelo local: 1 nova chance
        saida = llm.gera(prompt, sistema=_sistema_qa(), max_tokens=1200, json_obj=True)
        bruto = re.search(r"\{.*\}", saida or "", re.S)
        try:
            d = json.loads(bruto.group(0), strict=False) if bruto else None
        except json.JSONDecodeError:
            d = None
        if isinstance(d, dict):
            break
    if not isinstance(d, dict):
        return None
    fc = d.get("factcheck") if isinstance(d.get("factcheck"), dict) else {}
    risco = str(fc.get("risco") or "medio").lower()
    return {
        "qualidade_score": int(d.get("qualidade_score") or 0),
        "tom_score": int(d.get("tom_score") or 0),
        "entrega_promessa": bool(d.get("entrega_promessa")),
        "factcheck": {"risco": risco if risco in ("baixo", "medio", "alto") else "medio",
                      "observacoes": [str(o)[:300] for o in (fc.get("observacoes") or [])][:10]},
        "problemas": [str(p)[:300] for p in (d.get("problemas") or [])][:10],
        "evidencias": [e for e in (d.get("evidencias") or []) if isinstance(e, dict)][:10],
    }


CORRIGIVEIS = ("numero(s) sem fato", "subtitulos H2", "link(s) fora", "afirmacao vaga",
               "palavras", "H1 repetido", "IOF")


def checa(artigo: dict, brief: dict, evidencias: dict, hub: dict,
          site: dict | None = None) -> dict:
    estrutural = checa_estrutura(artigo, brief, evidencias, hub, site)
    qa = checa_ia(artigo, brief, evidencias)
    motivos: list[str] = list(estrutural)
    if qa is None:
        # Sem o modelo so' passa guia sem numero e estruturalmente limpo
        if estrutural or hub.get("fontes"):
            motivos.append("checagem IA indisponivel")
    else:
        if qa["qualidade_score"] < LIMIAR_QUALIDADE:
            motivos.append(f"qualidade {qa['qualidade_score']} < {LIMIAR_QUALIDADE}")
        if qa["tom_score"] < LIMIAR_TOM:
            motivos.append(f"tom {qa['tom_score']} < {LIMIAR_TOM}")
        if not qa["entrega_promessa"]:
            motivos.append("nao entrega a promessa da manchete")
        if qa["factcheck"]["risco"] == "alto":
            motivos.append("risco factual alto: " + "; ".join(qa["factcheck"]["observacoes"][:2]))
    aprovado = not motivos
    corrigivel = bool(motivos) and all(
        any(m.startswith(c) or c in m for c in CORRIGIVEIS) for m in estrutural) and (
        qa is None or (qa["factcheck"]["risco"] != "alto" and qa["entrega_promessa"]))
    resumo = ("aprovado" + (f" {qa['qualidade_score']}/{qa['tom_score']}, risco {qa['factcheck']['risco']}" if qa else " (sem IA)")
              if aprovado else "reprovado: " + "; ".join(motivos)[:300])
    return {"aprovado": aprovado, "motivo": resumo, "estrutural": estrutural,
            "qa": qa, "corrigivel": corrigivel}
