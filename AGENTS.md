# Контекст проекта (для ИИ-агента и для себя через пару месяцев)

## Что это

Локальный мессенджер по Wi-Fi. Сервер живёт на одном ПК (Arch Linux), клиенты
(телефон, планшет, второй ПК) открывают `http://<ip-пк>:8000` в браузере.
Без регистрации, без интернета, без сборщиков и CDN.

**Загрузка файлов в интерфейсе отключена** (кнопка и drag-and-drop удалены),
но серверный эндпоинт `/api/upload` в коде остался.

## Стек

Python 3.14 · FastAPI · Uvicorn · WebSocket (websockets) · SQLite · чистые
HTML/CSS/JS. Сборщика нет.

## Команды

```bash
# зависимости (venv уже создан)
.venv/bin/python -m pip install -r requirements.txt

# запуск вручную (в отдельном терминале)
./run.sh

# запуск как фоновой службы (после установки — самостарт при входе)
./install.sh
systemctl --user status  lan-chat.service
systemctl --user restart lan-chat.service
journalctl --user -u lan-chat.service -f

# чтобы работало и без залогина (один раз)
loginctl enable-linger $USER
```

## Важные особенности, на которые уже наступали

1. **`.venv/bin/activate` ломается в zsh** — ошибка
   `'case' builtin not inside of switch block`. Поэтому `run.sh` вызывает
   `.venv/bin/python run.py` напрямую, без `source activate`.
   Всегда: `.venv/bin/python -m pip ...`, а не просто `pip`.

2. **Нужен `websockets`.** Голый uvicorn без WebSocket-транспорта отвечает
   `404` на `/ws` — в браузере это вечное «Переподключение…». Признак в логе:
   `No supported WebSocket library detected`.

3. **Нужен `python-multipart`.** Эндпоинт `/api/upload` принимает `Form(...)`;
   без пакета приложение падает **на импорте** (`app/main.py`, ~строка 61) и
   сервер не поднимается вообще.

4. **`crypto.randomUUID()` недоступен на http://<ip>:8000.** Это secure context
   только для localhost/HTTPS. Отсюда был баг: страница открывалась, но JS
   падал на строке 19 и WebSocket не создавался. В `app.js` есть свой
   `randomId()` с фоллбэками.

5. **Удаление элемента из `index.html` = авария.** В `app.js` оставалась строка
   вида `fileInput.addEventListener(...)`, и `null.addEventListener` бросает
   `TypeError`. Скрипт обрывался **до** вызовов `loadHistory()` и `connect()`
   в конце файла — страница выглядела живой, но чат был мёртвым. При удалении
   элемента всегда чистить и JS.

6. **Кэш браузера.** Раньше Firefox отдавал `304 Not Modified` и держал старый
   JS/CSS. После правок статики — жёсткая перезагрузка: ПК `Ctrl+Shift+R`,
   телефон — «Удалить данные сайта».

## Структура

| Файл | Назначение |
|---|---|
| `run.sh` | запуск: проверяет Python 3.14+, зовёт `.venv/bin/python run.py` |
| `run.py` | печатает LAN-адреса, открывает браузер, стартует uvicorn |
| `app/config.py` | пути, порт, лимиты — всё через переменные окружения (`CHAT_*`) |
| `app/main.py` | REST (`/`, `/api/history`, `/api/upload`, `/files/{id}`) и `/ws` |
| `app/db.py` | SQLite: схема, история сообщений, файлы |
| `app/ws_manager.py` | WebSocket-клиенты, presence, typing, broadcast |
| `app/utils.py` | безопасные имена файлов, поиск LAN-адресов |
| `static/` | `index.html`, `style.css`, `app.js` |
| `data/chat.db` | SQLite с историей (в `.gitignore`) |
| `uploads/` | загруженные файлы (в `.gitignore`) |
| `lan-chat.service` | systemd user-юнит |
| `install.sh` | ставит юнит в `~/.config/systemd/user` и включает автозапуск |

## Настройки (app/config.py)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CHAT_HOST` | `0.0.0.0` | интерфейс |
| `CHAT_PORT` | `8000` | порт |
| `CHAT_MAX_UPLOAD_MB` | `200` | лимит файла |
| `CHAT_PAGE_SIZE` | `50` | сообщений на страницу истории |
| `CHAT_TYPING_TIMEOUT` | `2.5` | сброс «печатает…», сек |

## Мелочи, которые стоит помнить

- Приложение работает, пока включён ПК. Данные лежат на диске, поэтому
  перезагрузка их не теряет.
- Порт 8000 на Arch пришлось открыть: `sudo ufw allow 8000/tcp`.
- `ufw`/`firewalld`/`nftables` в песочнице агента не видны (нужен root) —
  проверять фаервол приходится вручную.
- `python-multipart` пришлось ставить руками, сети у агента нет.
