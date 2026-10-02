"""Ideias por categoria: o motor SUGERE, a pessoa MARCA, o motor PRODUZ.

Tabela `ideias` (sql/ideias-2026-10.sql). Status:
  sugerida     o motor achou nos sinais (ou a pessoa escreveu e ainda nao marcou)
  marcada      a pessoa quer este artigo — entra na fila de producao
  em_producao  virou pauta aprovada; a esteira (radar/publicar.py) escreve
  publicada    no ar
  reprovada    o checador barrou (ver artigos.checagem)
  descartada   a pessoa nao quer

Nada sai sem marcacao: o motor so' pesquisa, escreve e publica o que esta'
`marcada`, dentro da meta diaria e do periodo de producao do site.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from . import angulos_ia, brief as mod_brief, pesquisa as mod_pesquisa

SUGESTOES_POR_HUB = 6


def chave_manual(titulo: str) -> str:
    from .normaliza import normaliza_titulo
    return "manual:" + hashlib.sha1(normaliza_titulo(titulo).encode()).hexdigest()[:20]


def sugere_do_motor(banco, nome: str, hub: dict, topicos: list[dict],
                    agora: datetime) -> int:
    """Grava/atualiza as sugestoes do hub a partir dos melhores topicos. A
    chave e' a do topico, entao a mesma sugestao em dias seguidos atualiza a
    nota em vez de duplicar — e preserva a marcacao da pessoa."""
    linhas = []
    for t in topicos[:SUGESTOES_POR_HUB]:
        if t.get("ja_pautado"):
            continue
        linhas.append({
            "site": nome, "hub": hub["id"], "origem": "motor", "chave": t["chave"],
            "topico_id": t.get("id"), "titulo": t["rotulo"][:200],
            "motivo": t.get("motivo"), "pontuacao": int(t.get("pontuacao") or 0),
            "detalhes": {"termos": t.get("termos"), "perguntas": t.get("perguntas"),
                         "relacionadas": t.get("relacionadas"),
                         "manchetes": t.get("manchetes"), "organicos": t.get("organicos"),
                         "componentes": t.get("componentes")},
            "atualizado_em": agora.isoformat(),
        })
    if linhas:
        banco.grava_ideias(linhas)
    return len(linhas)


def produz(ideia: dict, nome: str, site: dict, hub: dict, banco, leitor,
           agora: datetime) -> dict | None:
    """Ideia marcada -> angulo -> pesquisa -> brief -> pauta APROVADA (slot
    imediato). Devolve a pauta gravada ou None (ideia continua marcada e
    tenta na proxima rodada; o motivo sai no log)."""
    publicados = [a.get("titulo") or "" for a in leitor.artigos_publicados_do_hub(nome, hub["id"])]
    angulos = angulos_ia.propoe_angulos(ideia, site, hub, publicados)
    angulo = angulos_ia.escolhe_angulo(angulos or [], hub, site.get("_formato"))
    if not angulo:
        print(f"    [ideia {ideia['id']}] sem angulo utilizavel")
        return None
    evidencias = mod_pesquisa.pesquisa(ideia, angulo, nome, site, hub, leitor)
    b = mod_brief.monta_brief(ideia, angulo, evidencias, site, hub)
    if not b:
        print(f"    [ideia {ideia['id']}] brief nao fechou")
        return None
    pauta = {
        "site": nome, "hub": hub["id"], "tipo": "discover", "status": "aprovada",
        "angulo": angulo["tipo"], "titulo_sug": b["discover_headline"],
        "dado_proprio": None, "prioridade": 10, "pontuacao": int(ideia.get("pontuacao") or 0),
        "motivo_selecao": f"ideia marcada ({ideia.get('origem')}): {ideia.get('motivo') or 'escolha do editor'}"[:200],
        "selecionada_em": agora.isoformat(), "horario_sugerido": agora.isoformat(),
        "topico_id": ideia.get("topico_id"), "brief": b, "evidencias": evidencias,
    }
    pauta_id = banco.grava_pauta(pauta)
    pauta["id"] = pauta_id
    banco.marca_ideia(ideia["id"], "em_producao", pauta_id=pauta_id)
    print(f"    [ideia {ideia['id']}] pauta {pauta_id}: {b['discover_headline']} "
          f"({len(evidencias.get('fatos') or [])} fato(s), angulo {angulo['tipo']})")
    return pauta
