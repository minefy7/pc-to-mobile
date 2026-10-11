#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
UNIT_NAME="lan-chat.service"
TARGET="$HOME/.config/systemd/user/$UNIT_NAME"

echo "Проект:   $PROJECT_DIR"
echo "Юнит:     $TARGET"
echo

mkdir -p "$HOME/.config/systemd/user"

# В юните путь зашит статически; проверим, что он совпадает с реальным проектом.
if ! grep -q "ExecStart=$PROJECT_DIR/.venv/bin/python run.py" lan-chat.service; then
  echo "Ошибка: в $UNIT_NAME указан другой путь." >&2
  exit 1
fi

cp lan-chat.service "$TARGET"
systemctl --user daemon-reload
systemctl --user enable --now "$UNIT_NAME"

echo
echo "Сервис установлен и запущен."
echo
echo "  статус:      systemctl --user status $UNIT_NAME"
echo "  логи:        journalctl --user -u $UNIT_NAME -f"
echo "  перезапуск:  systemctl --user restart $UNIT_NAME"
echo "  остановить:  systemctl --user stop $UNIT_NAME"
