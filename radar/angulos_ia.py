"""Angle Generator: a IA propoe angulos para uma ideia, a partir do que a
pessoa configurou no hub (termos, perfil do leitor) e do que os sinais
trouxeram (perguntas do PAA, buscas relacionadas, manchetes).

Substitui, para os sites com `motor: discover`, os 6 angulos fixos de
radar/angulos.py. O angulo escolhido vira o `main_angle` do brief; o TIPO
(enum curto abaixo) vai em `pautas.angulo`, que a tela Radar exibe.

Uma chamada ao modelo por ideia. Sem chave devolve None — a ideia fica
marcada e tenta na proxima rodada.
"""
from __future__ import annotations

import json
import re

from . import llm
from .brief import LISTA, regras_editoriais

TIPOS = ("servico", "explicador", "comparacao", "lista", "passo_a_passo", "analise")
RISCOS = ("baixo", "medio", "alto")


def _sistema(site: dict, hub: dict) -> str:
    return (
        f"Voce e' editor de pauta do {site.get('entidade') or site.get('dominio')}, "
        f"secao \"{hub.get('titulo') or hub.get('id')}\". Leitor desta secao: "
        f"{hub.get('perfil_leitor') or 'o publico geral do site'}.\n"
        "Para a IDEIA pedida, proponha de 3 a 5 ANGULOS diferentes de artigo "
        "para o Google Discover: cada um responde uma duvida real do leitor, "
        "entrega o que a manchete promete e nao repete o que o site ja' "
        "publicou. Sem caca-clique, sem pessoa real nomeada, sem promessa que "
        "o texto nao cumpra.\n"
        + regras_editoriais(site.get("_linha_editorial"), site.get("_formato")) +
        f"Tipos permitidos: {', '.join(t for t in TIPOS if not (t == 'lista' and site.get('_formato') == 'individual'))}.\n"
        "Responda SO um JSON: {\"angulos\": [{\"id\": \"a1\", \"tipo\": \"servico\", "
        "\"titulo_trabalho\": \"...\", \"promessa\": \"o que o leitor leva\", "
        "\"por_que_agora\": \"...\", \"perguntas_respondidas\": [\"...\"], "
        "\"risco_factual\": \"baixo|medio|alto\", \"afinidade\": 0.0-1.0, "
        "\"lacuna\": 0.0-1.0, \"canibaliza\": false}]}. "
        "`afinidade` = quanto interessa a ESTE leitor; `lacuna` = quanto o "
        "site ainda nao cobre; `canibaliza` = true se ja' existe artigo "
        "publicado sobre a mesma coisa; `risco_factual` alto quando o texto "
        "depende de numero, lei ou prazo que precisa ser checado.")


def _prompt(ideia: dict, hub: dict, publicados: list[str]) -> str:
    d = ideia.get("detalhes") or {}
    partes = [f"IDEIA: {ideia.get('titulo')}"]
    if ideia.get("motivo"):
        partes.append(f"Por que esta' em alta: {ideia['motivo']}")
    if d.get("termos"):
        partes.append("Vocabulario do topico: " + ", ".join(str(t) for t in d["termos"][:10]))
    if hub.get("termos"):
        partes.append("Termos da secao: " + ", ".join(str(t) for t in hub["termos"][:12]))
    if d.get("perguntas"):
        partes.append("Perguntas que as pessoas fazem (People Also Ask):\n- "
                      + "\n- ".join(str(p) for p in d["perguntas"][:8]))
    if d.get("relacionadas"):
        partes.append("Buscas relacionadas: " + "; ".join(str(r) for r in d["relacionadas"][:8]))
    if d.get("manchetes"):
        partes.append("Manchetes recentes (so' o titulo; nao temos o texto):\n- "
                      + "\n- ".join(f"{m.get('titulo')} ({m.get('veiculo') or 'imprensa'})"
                                    for m in d["manchetes"][:5]))
    if publicados:
        partes.append("Ja' publicado no site (nao repita):\n- " + "\n- ".join(publicados[:15]))
    partes.append("\nProponha os angulos.")
    return "\n".join(partes)


def _num(v, padrao=0.5) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return padrao


def propoe_angulos(ideia: dict, site: dict, hub: dict,
                   publicados: list[str] | None = None) -> list[dict] | None:
    """3-5 angulos validados, ou None (sem chave, falha de API, JSON ruim)."""
    if not llm.tem_chave():
        return None
    saida = llm.gera(_prompt(ideia, hub, publicados or []), sistema=_sistema(site, hub),
                     max_tokens=1500, json_obj=True)
    if not saida:
        return None
    bruto = re.search(r"\{.*\}", saida, re.S)
    try:
        dados = json.loads(bruto.group(0)) if bruto else None
    except json.JSONDecodeError:
        dados = None
    if not isinstance(dados, dict):
        return None
    angulos = []
    for i, a in enumerate(dados.get("angulos") or []):
        if not isinstance(a, dict) or not a.get("titulo_trabalho"):
            continue
        tipo = str(a.get("tipo") or "servico").strip().lower().replace("-", "_")
        risco = str(a.get("risco_factual") or "medio").strip().lower()
        angulos.append({
            "id": str(a.get("id") or f"a{i + 1}"),
            "tipo": tipo if tipo in TIPOS else "servico",
            "titulo_trabalho": str(a["titulo_trabalho"]).strip()[:120],
            "promessa": str(a.get("promessa") or "").strip()[:300],
            "por_que_agora": str(a.get("por_que_agora") or "").strip()[:300],
            "perguntas_respondidas": [str(p)[:200] for p in (a.get("perguntas_respondidas") or [])][:6],
            "risco_factual": risco if risco in RISCOS else "medio",
            "afinidade": _num(a.get("afinidade")),
            "lacuna": _num(a.get("lacuna")),
            "canibaliza": bool(a.get("canibaliza")),
        })
    return angulos[:5] or None


def escolhe_angulo(angulos: list[dict], hub: dict, formato: str | None = None) -> dict | None:
    """Deterministico: 0.4 afinidade + 0.4 lacuna + 0.2 (1 - risco). Descarta
    o que canibaliza, em hub SEM fontes oficiais o de risco alto (nao ha'
    onde checar o numero), e — no formato "individual" — qualquer lista."""
    risco_n = {"baixo": 0.0, "medio": 0.5, "alto": 1.0}
    tem_fontes = bool(hub.get("fontes"))
    melhor, nota_melhor = None, -1.0
    for a in angulos or []:
        if a.get("canibaliza"):
            continue
        if formato == "individual" and (a.get("tipo") == "lista"
                                        or LISTA.search(a.get("titulo_trabalho") or "")):
            continue
        if a.get("risco_factual") == "alto" and not tem_fontes:
            continue
        nota = 0.4 * a["afinidade"] + 0.4 * a["lacuna"] + 0.2 * (1 - risco_n[a["risco_factual"]])
        if nota > nota_melhor:
            melhor, nota_melhor = a, nota
    return melhor
