#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=".venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Виртуальное окружение не найдено. Создайте его:" >&2
  echo "  python -m venv .venv" >&2
  echo "  .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

# Проверка версии Python (3.14+)
if ! "$PYTHON" -c 'import sys; assert sys.version_info >= (3, 14), sys.version' 2>/dev/null; then
  echo "Ошибка: требуется Python 3.14 или новее." >&2
  echo "Установите: sudo pacman -S --needed python python-pip" >&2
  exit 1
fi

# Активация venv не нужна: PATH не меняем, интерпретатор вызываем напрямую.
# Так скрипт работает из любой оболочки (bash, zsh, fish) — .venv/bin/activate
# написан на bash и в zsh падает с ошибкой про 'case'.
exec "$PYTHON" run.py "$@"
