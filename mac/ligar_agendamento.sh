#!/bin/bash
# Liga (ou religa) a rodada automatica do doll, de 30 em 30 min.
#
#   bash mac/ligar_agendamento.sh            # liga
#   bash mac/ligar_agendamento.sh desligar   # desliga
#   tail -f ~/Library/Logs/radar-doll.log    # acompanha
set -e
cd "$(dirname "$0")/.."
ROTULO=com.tihee.radar-doll
DEST="$HOME/Library/LaunchAgents/$ROTULO.plist"
LOG="$HOME/Library/Logs/radar-doll.log"

launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null || true
if [ "${1:-}" = "desligar" ]; then
  rm -f "$DEST"
  echo "agendamento desligado"
  exit 0
fi
set -a; [ -f .env ] && . ./.env; set +a
if [ "${RADAR_MODO:-ensaio}" != "publicar" ]; then
  echo "o .env esta' em RADAR_MODO=${RADAR_MODO:-ensaio}: o ensaio roda a' mao"
  echo "(bash mac/rodar_doll.sh). Agende so' depois de trocar para publicar."
  exit 1
fi
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s#__PASTA__#$(pwd)#g" -e "s#__LOG__#$LOG#g" mac/$ROTULO.plist > "$DEST"
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "agendamento ligado: roda agora e depois de 30 em 30 min"
echo "acompanhe com: tail -f $LOG"
