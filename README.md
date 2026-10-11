# Чат — локальный мессенджер по Wi-Fi

Небольшой офлайн-мессенджер для обмена текстом внутри одной локальной сети.
Сервер запускается на ПК с Arch Linux, клиенты (телефон, планшет, другой ПК)
просто открывают `http://<ip-пк>:8000` в браузере — никаких установок на
телефон не требуется.

Стек: Python 3.14+ · FastAPI · Uvicorn · WebSocket · SQLite · чистые
HTML/CSS/JS без сборщиков и CDN.

> Загрузка файлов в интерфейсе отключена (кнопка и drag-and-drop убраны).
> Серверный эндпоинт `/api/upload` в коде остался — см. раздел
> «Настройки».

## Быстрый старт

```bash
cd ~/Python/PCtoMobile

# 1. зависимости (venv создаётся один раз)
sudo pacman -S --needed python python-pip
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 2. запуск в фоне как служба (одноразово)
./install.sh
```

Сервер поднимется, напечатает LAN-адрес и будет стартовать автоматически при
каждом входе в систему. Терминал держать не нужно.

Открыть на телефоне: `http://<ip-пк>:8000` (адрес печатается при запуске и
логируется в `journalctl --user -u lan-chat.service`).

### Если нужно запустить вручную (отладка)

```bash
./run.sh              # или ./run.sh --no-browser, чтобы не открывать браузер
```

## Управление службой

| Что сделать | Команда |
|---|---|
| Статус | `systemctl --user status lan-chat.service` |
| Логи в реальном времени | `journalctl --user -u lan-chat.service -f` |
| Перезапустить после правок | `systemctl --user restart lan-chat.service` |
| Остановить | `systemctl --user stop lan-chat.service` |
| Обновить юнит после правки | `./install.sh` |

Чтобы работало и после выхода из системы (без залогина):

```bash
loginctl enable-linger $USER
```

## Установка (Arch Linux)

```bash
sudo pacman -S --needed python python-pip
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

На Arch системный Python управляется pacman (`PEP 668`, externally-managed), а
потому `pip install` в систему запрещён — все зависимости ставятся только в
виртуальное окружение. **Никогда не используйте `pip install
--break-system-packages`.**

**Важно про zsh.** Файл `.venv/bin/activate` создан на bash и в zsh падает с
ошибкой `'case' builtin not inside of switch block`. Поэтому в этом проекте
`activate` **не используется**: всегда вызывайте `.venv/bin/python` напрямую,
а `run.sh` делает именно это. Команда `pip` без пути к venv — гарантированный
`externally-managed-environment`.

### Совместимость с Python 3.14

Проект намеренно **не** использует экстра-фичу `uvicorn[standard]`: `uvloop`
и `httptools` исторически собираются под новые CPython не всегда, а под 3.14
в частности сборка может падать.

Но WebSocket-транспорт обязателен: голый `uvicorn` без `websockets`/`wsproto`
не умеет апгрейдить соединение до WebSocket и отвечает `404` на `/ws`
(в браузере это выглядит как вечное «Переподключение…»). Поэтому в
`requirements.txt` есть `websockets` — он pure-Python (C-расширение
опционально), поэтому под 3.14 собирается без проблем.

Также нужен `python-multipart`: эндпоинт `/api/upload` принимает `Form(...)`,
и без этого пакета приложение падает на импорте и сервер не поднимается.

Версии заданы диапазонами — так pip сам подберёт версию с колёсами под ваш
CPython 3.14. Проверить фактические версии:

```bash
.venv/bin/python -c "import fastapi, uvicorn, websockets; print(fastapi.__version__, uvicorn.__version__, websockets.__version__)"
```

## Как узнать IP ПК

- `run.sh` печатает все LAN-адреса автоматически.
- Вручную: `ip -4 addr show` (пакет `iproute2` входит в базовую систему Arch)
  или `hostname -I` (команда `hostname` в Arch обычно приходит из `inetutils`).

## Открыть с телефона

1. Убедитесь, что телефон и ПК в одной Wi-Fi сети.
2. Откройте в браузере телефона `http://<ip-пк>:8000`.
3. Введите имя (сохраняется в `localStorage`) и начните общение.

Если с телефона «не подключается», а на самом ПК всё работает — почти всегда
фаервол на ПК:

```bash
sudo ufw status verbose        # ufw
sudo firewall-cmd --list-all   # firewalld
sudo nft list ruleset          # nftables
```

Открыть порт:

**ufw**
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

**firewalld**
```bash
sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload
```

**nftables** — пример правила (фильтр входящих, IPv4/IPv6):
```nft
table inet filter {
  chain input {
    type filter hook input priority 0; policy accept;
    tcp dport 8000 accept
  }
}
```
Добавьте блок в `/etc/nftables.conf` (или в отдельный файл, подключённый из
него) и перезагрузите: `sudo nft -f /etc/nftables.conf`.

Если порт открыт, а телефон всё равно не видит ПК — проверьте роутер:
**гостевая сеть (Guest)** и **изоляция клиентов (AP isolation)** почти всегда
блокируют обмен между устройствами, даже в одной сети.

## Частые проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| `Unable to connect` в Firefox, страница не открывается | сервер не запущен | `./run.sh` или `systemctl --user start lan-chat.service` |
| `could not bind on any address out of [('0.0.0.0', 8000)]` | порт уже занят другим экземпляром | остановить старый: `systemctl --user stop lan-chat.service` |
| `ModuleNotFoundError: No module named 'uvicorn'` | зависимости не установлены | `.venv/bin/python -m pip install -r requirements.txt` |
| `externally-managed-environment` | команда `pip` шла в системный Python | использовать `.venv/bin/python -m pip` |
| В логе `No supported WebSocket library detected`, `/ws` → `404` | не установлен `websockets` | `.venv/bin/python -m pip install -r requirements.txt` |
| `Form data requires "python-multipart"` | не установлен `python-multipart` | то же |
| Висит «Переподключение…», ничего не отправляется | `/ws` не поднимается | см. две строки выше; в логе ждём `101 Switching Protocols` |
| Страница открылась, но пустая и мёртвая | JS упал до `connect()` (см. ниже) | жёстко перезагрузить страницу |
| Старый интерфейс после правок | кэш браузера (`304 Not Modified`) | ПК: `Ctrl+Shift+R`; телефон: «Удалить данные сайта» |
| Телефон не подключается, ПК работает | фаервол или изоляция на роутере | см. раздел выше |

### Правило на будущее: не оставляй мёртвый код в JS

Если удалить элемент из `index.html`, но забыть убрать обращения к нему в
`app.js`, будет `TypeError: null is not an object`. Скрипт обрывается **на
той строке**, а вызовы `loadHistory()` и `connect()` стоят в самом конце файла —
итого страница выглядит живой, но чат полностью мёртвый. При удалении элемента
всегда чистить и JS (а заодно проверять, что все `getElementById` находят
существующие элементы).

### Про `crypto.randomUUID()`

Метод доступен только в secure context — то есть HTTPS или `localhost`. Телефон
заходит по `http://<ip>:8000`, там `crypto.randomUUID` может быть недоступен,
из-за чего скрипт падал ещё до создания WebSocket. В `app.js` на этот случай
есть собственный `randomId()` с цепочкой фоллбэков.

## Настройки

Все настройки — в `app/config.py`:

| Параметр | Значение по умолчанию | Описание |
|---|---|---|
| `PORT` | `8000` | TCP-порт сервера (переопределяется `CHAT_PORT`) |
| `HOST` | `0.0.0.0` | Интерфейс (переопределяется `CHAT_HOST`) |
| `MAX_UPLOAD_BYTES` | `200 * 1024 * 1024` (200 МБ) | Лимит файла (`CHAT_MAX_UPLOAD_MB`) |
| `PAGE_SIZE` | `50` | Сообщений на страницу истории (`CHAT_PAGE_SIZE`) |
| `TYPING_TIMEOUT` | `2.5` сек | Через сколько сбрасывается «печатает…» |

Папки: `data/chat.db` (SQLite) и `uploads/` (файлы), пути считаются от корня
проекта через `pathlib.Path`.

## Очистка истории

История лежит в `data/chat.db`. Очистить — остановить сервер и удалить БД:

```bash
systemctl --user stop lan-chat.service     # или Ctrl+C, если запускали вручную
rm -f data/chat.db data/chat.db-shm data/chat.db-wal
systemctl --user start lan-chat.service
```

Схема пересоздастся при следующем старте. Если в `uploads/` были файлы —
`rm -f uploads/*` (кроме `.gitkeep`).

Важно: **сначала остановить сервер**, иначе из-за WAL-режима SQLite часть
данных может «вернуться» после удаления файлов.

## Структура проекта

| Файл | Назначение |
|---|---|
| `run.sh` | запуск: проверяет Python 3.14+, зовёт `.venv/bin/python run.py` |
| `run.py` | печатает LAN-адреса, открывает браузер, стартует uvicorn |
| `install.sh` | ставит `lan-chat.service` и включает автозапуск |
| `lan-chat.service` | systemd user-юнит |
| `app/config.py` | пути, порт, лимиты через переменные окружения (`CHAT_*`) |
| `app/main.py` | REST (`/`, `/api/history`, `/api/upload`, `/files/{id}`) и `/ws` |
| `app/db.py` | SQLite: схема, история сообщений, файлы |
| `app/ws_manager.py` | WebSocket-клиенты, presence, typing, broadcast |
| `app/utils.py` | безопасные имена файлов, поиск LAN-адресов |
| `static/` | `index.html`, `style.css`, `app.js` |
| `data/chat.db` | SQLite с историей (в `.gitignore`) |
| `uploads/` | загруженные файлы (в `.gitignore`) |
| `AGENTS.md` | контекст проекта для ИИ-агента |

Подробный разбор архитектуры и всех известных ловушек — в `AGENTS.md`.

## Безопасность

- Имена файлов на диске — `UUID4` + санитизированное расширение, исходное имя
  хранится только в БД и отдаётся в `Content-Disposition`.
- Доступ к файлам — только через `/files/{file_id}`, пути с `..` не
  поддерживаются (id валидируется как UUID).
- При загрузке проверяется `Content-Length`, а фактический размер лимитируется
  вручную при стриминге; превышение отклоняется без записи.
- Файлы отдаются через `FileResponse` (стриминг/отдача из файловой системы),
  история хранится в SQLite с параметризованными запросами.
- Аутентификации нет: любой, кто откроет адрес в сети, сможет читать и писать.
  Для домашней сети это нормально, для интернета — нет.

## Git и публикация

Первичная инициализация:

```bash
cd ~/Python/PCtoMobile
git init
git config user.name  "Твоё Имя"
git config user.email "твоя-почта@example.com"
git add .
git status          # убедись, что .venv и data/chat.db не попали
git commit -m "Первая версия чата"
```

Отправка на GitHub (репозиторий уже создан на github.com и пуст):

```bash
git remote add origin https://github.com/<логин>/<репозиторий>.git
git branch -M main
git push -u origin main
```

При `push` GitHub попросит логин и **Personal Access Token**, а не пароль:
GitHub → Settings → Developer settings → Personal access tokens → Generate new
token (classic), отметить галочку `repo`.

Через `gh` вместо браузера:

```bash
sudo pacman -S github-cli
gh auth login
gh repo create PCtoMobile --private --source=. --push
```

## Дальше

- Аутентификация / комнаты.
- Шифрование сообщений.
- Индикатор прочтения, редактирование и удаление сообщений.
- Ограничение по количеству одновременных подключений.
