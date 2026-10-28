#!/bin/bash
# Uma rodada do doll no Mac, com o modelo local (exo) e a busca local (SearXNG).
# Quem chama de 30 em 30 min e' o launchd (mac/com.tihee.radar-doll.plist).
#
#   RADAR_MODO=ensaio   (padrao) reescreve as 10 ultimas pautas JA' publicadas
#                       e poe cada texto ao lado do que esta' no ar, em
#                       saida/ensaio/ (radar/ensaio_local.py). So' le o banco:
#                       o GitHub segue dono do doll. Roda a' mao.
#   RADAR_MODO=publicar o Mac vira dono do doll (coleta, grava e publica),
#                       junto com RADAR_IGNORA_SITES=doll no GitHub.
set -u
cd "$(dirname "$0")/.." || exit 1

# Uma rodada por vez: o modelo local leva minutos por post.
TRAVA=/tmp/radar-doll.trava
if ! mkdir "$TRAVA" 2>/dev/null; then
  echo "$(date '+%d/%m %H:%M') rodada anterior ainda em curso — pulando"
  exit 0
fi
trap 'rmdir "$TRAVA"' EXIT

set -a; [ -f .env ] && . ./.env; set +a
export RADAR_SITES=doll
PY=.venv/bin/python
MODO="${RADAR_MODO:-ensaio}"
echo "=== $(date '+%d/%m/%Y %H:%M') — doll, modo $MODO ==="

# Sem o exo de pe' nao adianta rodar: tudo cairia no fallback sem texto.
# Aviso no Mac quando o exo falha 2 rodadas seguidas (24-25/10/2026: travou
# as 19:55 e so' foi notado na manha seguinte). Avisa de novo a cada 2 horas.
FALHAS_EXO=/tmp/radar-doll.falhas-exo
avisa_exo() {
  n=$(( $(cat "$FALHAS_EXO" 2>/dev/null || echo 0) + 1 ))
  echo "$n" > "$FALHAS_EXO"
  if [ "$n" -ge 2 ] && [ $(( (n - 2) % 4 )) -eq 0 ]; then
    osascript -e "display notification \"$1 ha' $n rodadas (o doll nao publica). Reinicie o EXO nos dois Macs.\" with title \"Radar do doll\" sound name \"Basso\"" >/dev/null 2>&1 || true
  fi
}

if ! curl -sf -m 10 "${LLM_LOCAL_URL:-http://localhost:52415/v1}/models" >/dev/null; then
  echo "exo fora do ar em ${LLM_LOCAL_URL:-http://localhost:52415/v1} — nada rodou"
  avisa_exo "o exo esta' fora do ar"
  exit 0
fi

# De pe' nao basta: em 19/10/2026 o exo respondia /models mas deixava toda
# geracao em "Pending" ate' o prazo de 20 min (um runner parado). Uma frase
# curta de verdade, com prazo de 2 min; sem resposta, a rodada nao comeca
# (senao cada satelite cairia no template depois de 20 min de espera).
TESTE=$(curl -sf -m 120 "${LLM_LOCAL_URL:-http://localhost:52415/v1}/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${LLM_LOCAL_MODELO:-mlx-community/Qwen3.8-27B-8bit}\",\"messages\":[{\"role\":\"user\",\"content\":\"Responda so: ok\"}],\"max_tokens\":20,\"enable_thinking\":false,\"stream\":false}" \
  | "$PY" -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'].strip()[:20])" 2>/dev/null)
if [ -z "$TESTE" ]; then
  echo "exo de pe' mas nao gera texto (travado?) — nada rodou; reinicie o EXO nos dois Macs"
  avisa_exo "o exo esta' de pe' mas nao gera texto"
  exit 0
fi
rm -f "$FALHAS_EXO"

if [ "$MODO" = "publicar" ]; then
  $PY -m radar.principal --site doll || true
  $PY -m radar.satelites || true
  $PY -m radar.publicar --site doll || true
  $PY -m radar.reserva || true
else
  # So' leitura: mesma pauta, texto local x texto no ar, para revisar.
  $PY -m radar.ensaio_local --site doll --limite "${RADAR_ENSAIO_LIMITE:-10}" || true
fi
echo "=== fim $(date '+%H:%M') ==="
