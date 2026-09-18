"""Confere se o banco do radar tem as colunas que o codigo usa.

    python -m radar.verifica_schema

Sai 0 se esta' tudo la', 1 se falta alguma coisa — e diz QUAL arquivo de
sql/ resolve.

Existe porque nao da' para aplicar migration daqui: a SUPABASE_SERVICE_KEY
fala com o PostgREST, que roda DML mas NAO roda DDL (`alter table`). O
`alter` e' aplicado a mao no SQL Editor do Supabase, e sem um conferidor a
unica forma de descobrir que alguem esqueceu e' a esteira quebrar em
producao, horas depois.

Como funciona: pede a coluna ao PostgREST e le a resposta. Coluna que nao
existe devolve erro 42703 nomeando a coluna; coluna que existe devolve
200 (mesmo sem nenhuma linha na tabela).
"""
from __future__ import annotations

import sys

import requests

from .config import env

TEMPO_LIMITE = 20

# (tabela, coluna, arquivo de sql que cria, para que serve)
EXIGIDAS = [
    ("artigos", "wp_media_id", "sql/imagem-destacada-2026-09.sql",
     "id da midia no WP; sem ela a rerodada duplica a imagem"),
    ("artigos", "imagem_url", "sql/imagem-destacada-2026-09.sql",
     "URL da imagem destacada (vira og:image)"),
    ("artigos", "imagem_credito", "sql/imagem-destacada-2026-09.sql",
     "credito do acervo; obrigatorio nas imagens CC"),
    ("metas", "criterios", "sql/schema.sql",
     "pesos da selecao automatica"),
    ("pautas", "horario_sugerido", "sql/schema.sql",
     "slot da pauta fixa na janela editorial"),
]


def existe(base: str, chave: str, tabela: str, coluna: str) -> bool | None:
    """True/False, ou None se nem deu para perguntar."""
    try:
        r = requests.get(f"{base}/rest/v1/{tabela}",
                         headers={"apikey": chave, "Authorization": f"Bearer {chave}"},
                         params={"select": coluna, "limit": 1},
                         timeout=TEMPO_LIMITE)
    except Exception as erro:
        print(f"  nao consegui perguntar por {tabela}.{coluna}: {erro}")
        return None
    if r.ok:
        return True
    # 42703 = undefined_column no Postgres
    if r.status_code in (400, 404) and ("42703" in r.text or coluna in r.text):
        return False
    print(f"  resposta inesperada para {tabela}.{coluna}: "
          f"HTTP {r.status_code} {r.text[:160]}")
    return None


def main() -> int:
    base = (env("SUPABASE_URL") or "").rstrip("/")
    chave = env("SUPABASE_SERVICE_KEY") or ""
    if not base or not chave:
        print("faltam SUPABASE_URL e SUPABASE_SERVICE_KEY")
        return 1

    faltando: dict[str, list[str]] = {}
    for tabela, coluna, arquivo, para_que in EXIGIDAS:
        estado = existe(base, chave, tabela, coluna)
        marca = {True: "ok   ", False: "FALTA", None: "?    "}[estado]
        print(f"  [{marca}] {tabela}.{coluna:16} — {para_que}")
        if estado is False:
            faltando.setdefault(arquivo, []).append(f"{tabela}.{coluna}")

    if not faltando:
        print("\nSchema completo: nada a aplicar.")
        return 0

    print("\nFALTA APLICAR — o SQL abaixo roda no SQL Editor do Supabase do "
          "radar (nao da' para aplicar daqui: a service key fala com o "
          "PostgREST, que nao executa DDL):")
    for arquivo, colunas in faltando.items():
        print(f"  {arquivo}  ->  {', '.join(colunas)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
