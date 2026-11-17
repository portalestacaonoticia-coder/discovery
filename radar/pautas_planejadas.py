"""Pautas PLANEJADAS: o plano chega pronto, o modelo local so' escreve.

    python -m radar.pautas_planejadas plano.json --site 7d --seco   # confere e mostra
    python -m radar.pautas_planejadas plano.json --site 7d          # poe na fila

Esquema do 7d (17/11/2026): quem planeja (o Claude, numa sessao de
planejamento) escolhe as pautas e APURA os fatos; cada pauta entra na tabela
`ideias` ja' como 'marcada', com os fatos em detalhes.fatos. O motor
(radar/motor.py) pega dali: angulo -> brief -> texto -> checagem, tudo no
modelo local, e os fatos da pauta sao os unicos numeros permitidos
(radar/pesquisa.py).

O plano e' um array JSON; cada pauta:
  {"hub": "<id do hub no sites.yaml>", "titulo": "...", "motivo": "...",
   "perguntas": ["..."],
   "fatos": [{"afirmacao": "...", "valor": "...", "fonte_url": "https://...",
              "fonte_nome": "...", "data": "AAAA-MM-DD"}]}

Pauta com menos de MIN_FATOS fatos validos NAO entra: sem fato o modelo local
preenche o vazio com invencao. Pauta ja' carregada (mesmo titulo no mesmo
hub) e' pulada — recarregar o plano nao devolve para a fila o que ja' saiu.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .banco import Banco
from .config import carrega_sites
from .ideias import chave_manual

MIN_FATOS = 5
PONTUACAO = 90     # so' para ordenar na tela; quem decide a fila e' marcada_em


def _fatos_validos(fatos) -> list[dict]:
    uteis = []
    for f in fatos or []:
        if (isinstance(f, dict) and str(f.get("afirmacao") or "").strip()
                and str(f.get("fonte_url") or "").startswith(("http://", "https://"))):
            uteis.append({k: str(f.get(k) or "").strip()
                          for k in ("afirmacao", "valor", "fonte_url", "fonte_nome", "data")})
    return uteis


def monta_linhas(plano: list, nome: str, site: dict,
                 agora: datetime | None = None) -> tuple[list[dict], list[str]]:
    """(linhas prontas para a tabela ideias, recusas com o motivo). A ordem
    do plano e' a ordem da fila: marcada_em anda 1 s por pauta."""
    agora = agora or datetime.now(timezone.utc)
    hubs = {h.get("id") for h in site.get("hubs", []) or []}
    linhas, recusas, vistas = [], [], set()
    for p in plano if isinstance(plano, list) else []:
        titulo = str((p or {}).get("titulo") or "").strip() if isinstance(p, dict) else ""
        if not titulo:
            recusas.append("pauta sem titulo")
            continue
        hub = str(p.get("hub") or "").strip()
        if hub not in hubs:
            recusas.append(f"{titulo[:60]}: hub '{hub}' nao existe em {nome}")
            continue
        fatos = _fatos_validos(p.get("fatos"))
        if len(fatos) < MIN_FATOS:
            recusas.append(f"{titulo[:60]}: so' {len(fatos)} fato(s) com fonte (minimo {MIN_FATOS})")
            continue
        chave = chave_manual(titulo)
        if (hub, chave) in vistas:
            recusas.append(f"{titulo[:60]}: repetida no plano")
            continue
        vistas.add((hub, chave))
        momento = (agora + timedelta(seconds=len(linhas))).isoformat()
        linhas.append({
            "site": nome, "hub": hub, "origem": "planejada", "chave": chave,
            "titulo": titulo[:200], "motivo": str(p.get("motivo") or "").strip()[:300] or None,
            "pontuacao": PONTUACAO, "status": "marcada", "marcada_em": momento,
            "atualizado_em": momento,
            "detalhes": {"fonte": "planejada", "fatos": fatos,
                         "perguntas": [str(q).strip() for q in (p.get("perguntas") or [])
                                       if str(q).strip()][:10]},
        })
    return linhas, recusas


def main() -> int:
    p = argparse.ArgumentParser(description="Carrega um plano de pautas na fila do motor")
    p.add_argument("plano", help="arquivo JSON com as pautas")
    p.add_argument("--site", required=True, help="id do site em config/sites.yaml")
    p.add_argument("--seco", action="store_true", help="so' confere e mostra, nao grava")
    args = p.parse_args()

    sites = carrega_sites()
    if args.site not in sites:
        print(f"Site '{args.site}' nao existe em config/sites.yaml")
        return 1
    plano = json.loads(Path(args.plano).read_text(encoding="utf-8"))
    linhas, recusas = monta_linhas(plano, args.site, sites[args.site])
    for l in linhas:
        print(f"  [{l['hub']}] {l['titulo']}  ({len(l['detalhes']['fatos'])} fatos)")
    for r in recusas:
        print(f"  RECUSADA — {r}")
    if args.seco:
        print(f"(seco) {len(linhas)} pauta(s) entrariam, {len(recusas)} recusada(s)")
        return 0
    novas = Banco().grava_ideias_planejadas(linhas)
    print(f"{novas} pauta(s) nova(s) na fila de {args.site} "
          f"({len(linhas) - novas} ja' estavam la'), {len(recusas)} recusada(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
