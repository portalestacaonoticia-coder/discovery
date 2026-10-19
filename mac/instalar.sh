#!/bin/bash
# Prepara este Mac para rodar o Radar do doll com IA local. Uma vez so';
# rodar de novo nao estraga nada.
#
#   bash mac/instalar.sh
#
# Precisa: Docker aberto (para o SearXNG) e o exo com o modelo READY.
set -e
cd "$(dirname "$0")/.."

echo "1/4 Python 3.12 e dependencias"
UV="$(command -v uv || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if [ -z "$UV" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV="$HOME/.local/bin/uv"
fi
"$UV" venv --allow-existing --python 3.12 .venv
"$UV" pip install --python .venv/bin/python -r requirements.txt

echo "2/4 Arquivo .env"
[ -f .env ] || cp .env.example .env
if ! grep -q '^LLM_LOCAL_URL=.' .env; then
  cat >> .env <<'X'

# --- Modo local (Mac), acrescentado pelo mac/instalar.sh ---
LLM_LOCAL_URL=http://localhost:52415/v1
LLM_LOCAL_MODELO=mlx-community/Qwen3.8-27B-8bit
SEARXNG_URL=http://localhost:8888
# ensaio = escreve e grava, nao publica. Troque para publicar depois da revisao.
RADAR_MODO=ensaio
X
fi

echo "3/4 Busca local (SearXNG)"
if [ ! -f mac/searxng/settings.local.yml ]; then
  sed "s/TROCAR_PELO_INSTALADOR/$(openssl rand -hex 32)/" \
    mac/searxng/settings.yml > mac/searxng/settings.local.yml
fi
(cd mac/searxng && docker compose up -d)

echo "4/4 Conferindo"
sleep 8
if curl -sf -m 15 "http://localhost:8888/search?q=ptax&format=json" >/dev/null; then
  echo "  SearXNG: ok"
else
  echo "  SearXNG: ainda nao respondeu (espere 1 minuto e rode de novo)"
fi
if curl -sf -m 10 "http://localhost:52415/v1/models" >/dev/null; then
  echo "  exo: ok"
else
  echo "  exo: nao respondeu — abra o EXO e deixe o modelo READY"
fi
echo
echo "Falta preencher no .env: SUPABASE_URL, SUPABASE_SERVICE_KEY,"
echo "WP_DOLL_USUARIO, WP_DOLL_SENHA e PEXELS_API_KEY (abra com: open -e .env)"
