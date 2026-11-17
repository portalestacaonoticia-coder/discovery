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

# Aberto sem modelo: depois de reiniciar (02/11/2026) ou de um runner cair
# (16-17/11/2026) o exo fica de pe' com 0 instancias, e o doll parava ate'
# alguem carregar o modelo a' mao. Sem instancia, carrega nos 2 Macs e espera
# ate' 5 min os runners ficarem prontos. Runner travado COM instancia nao e'
# isso: segue para o teste abaixo, que avisa para reiniciar o EXO.
EXO_BASE="${LLM_LOCAL_URL:-http://localhost:52415/v1}"
EXO_BASE="${EXO_BASE%/v1}"
EXO_ESPERA_S="${RADAR_EXO_ESPERA_S:-300}"
instancias_exo() {
  curl -sf -m 10 "$EXO_BASE/state" | "$PY" -c "import json,sys; print(len(json.load(sys.stdin).get('instances') or {}))" 2>/dev/null
}
prontos_exo() {
  n=$(curl -sf -m 10 "$EXO_BASE/state" | "$PY" -c "import json,sys; print(sum('RunnerReady' in r for r in (json.load(sys.stdin).get('runners') or {}).values()))" 2>/dev/null)
  echo "${n:-0}"
}
if [ "$(instancias_exo)" = "0" ]; then
  echo "exo sem modelo carregado — carregando nos 2 Macs"
  curl -sf -m 30 -X POST "$EXO_BASE/place_instance" -H 'Content-Type: application/json' \
    -d "{\"model_id\":\"${LLM_LOCAL_MODELO:-mlx-community/Qwen3.8-27B-8bit}\",\"sharding\":\"Tensor\",\"instance_meta\":\"MlxJaccl\",\"min_nodes\":2}" >/dev/null \
    || echo "  o exo recusou o pedido de carga"
  inicio=$SECONDS
  while [ "$(prontos_exo)" -lt 2 ] && [ $((SECONDS - inicio)) -lt "$EXO_ESPERA_S" ]; do
    sleep 10
  done
  echo "  $(prontos_exo) runner(s) pronto(s) apos $((SECONDS - inicio)) s"
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

# Prazo por etapa (29/10/2026: a rodada das 15:38 ficou presa e nenhuma outra
# rodou ate' o reinicio de 01/11). Sem buffer: o log mostra onde parou.
export PYTHONUNBUFFERED=1
PRAZO_ETAPA="${RADAR_PRAZO_ETAPA:-5400}"
com_prazo() {
  "$@" &
  local alvo=$! decorrido=0
  (
    while kill -0 "$alvo" 2>/dev/null; do
      sleep 5
      decorrido=$((decorrido + 5))
      if [ "$decorrido" -ge "$PRAZO_ETAPA" ]; then
        echo "etapa presa ha' $PRAZO_ETAPA s, encerrando: $*"
        osascript -e "display notification \"Uma etapa do doll ficou presa e foi encerrada.\" with title \"Radar do doll\" sound name \"Basso\"" >/dev/null 2>&1 || true
        kill -TERM "$alvo" 2>/dev/null
        sleep 30
        kill -KILL "$alvo" 2>/dev/null
        exit 0
      fi
    done
  ) &
  local vigia=$!
  wait "$alvo"
  wait "$vigia"
}

if [ "$MODO" = "publicar" ]; then
  com_prazo $PY -m radar.principal --site doll || true
  com_prazo $PY -m radar.satelites || true
  com_prazo $PY -m radar.publicar --site doll || true
  com_prazo $PY -m radar.reserva || true

  # 7d (17/11/2026): mesma rodada, mesma trava, DEPOIS do doll — o cluster
  # atende um pedido por vez e o doll nunca fica sem a vez dele. As pautas
  # vem planejadas (tabela ideias, status 'marcada', com os fatos ja'
  # apurados em detalhes.fatos); o modelo local so' escreve. Poucas por
  # rodada (RADAR_IDEIAS_POR_RODADA) para a rodada caber nos 30 min.
  # So' roda com a senha de aplicativo do WP no .env: sem ela nada sairia.
  if [ -n "${WP_7D_USUARIO:-}" ] && [ -n "${WP_7D_SENHA:-}" ]; then
    echo "--- 7d ---"
    export RADAR_IDEIAS_POR_RODADA="${RADAR_IDEIAS_POR_RODADA:-2}"
    com_prazo env RADAR_SITES=7d $PY -m radar.motor --site 7d || true
    com_prazo env RADAR_SITES=7d $PY -m radar.publicar --site 7d || true
  fi
else
  # So' leitura: mesma pauta, texto local x texto no ar, para revisar.
  $PY -m radar.ensaio_local --site doll --limite "${RADAR_ENSAIO_LIMITE:-10}" || true
fi
echo "=== fim $(date '+%H:%M') ==="
