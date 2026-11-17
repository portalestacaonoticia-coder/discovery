#!/bin/bash
# Liga (ou religa) o agente do cluster: de minuto em minuto ele publica o
# estado do exo no banco e executa os comandos da tela Qwen do conteudo.tihee.
#
#   bash mac/ligar_agente.sh              # liga
#   bash mac/ligar_agente.sh desligar     # desliga
#   tail -f ~/Library/Logs/cluster-agente.log
set -e
cd "$(dirname "$0")/.."
ROTULO=com.tihee.cluster-agente
DEST="$HOME/Library/LaunchAgents/$ROTULO.plist"
LOG="$HOME/Library/Logs/cluster-agente.log"

launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null || true
if [ "${1:-}" = "desligar" ]; then
  rm -f "$DEST"
  echo "agente desligado: a tela Qwen vai mostrar o Mac mini como parado"
  exit 0
fi
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s#__PASTA__#$(pwd)#g" -e "s#__LOG__#$LOG#g" mac/$ROTULO.plist > "$DEST"
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "agente ligado: publica o estado agora e depois de minuto em minuto"
echo "acompanhe com: tail -f $LOG"
