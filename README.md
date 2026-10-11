# Чат — локальный мессенджер по Wi-Fi

Небольшой офлайн-мессенджер для обмена текстом и файлами внутри одной локальной
сети. Сервер запускается на ПК с Arch Linux, клиенты (телефон, планшет, другой
ПК) просто открывают `http://<ip-пк>:8000` в браузере — никаких установок на
телефон не требуется.

Стек: Python 3.14+ · FastAPI · Uvicorn · WebSocket · SQLite · чистые
HTML/CSS/JS без сборщиков и CDN.

## Установка (Arch Linux)

```bash
sudo pacman -S --needed python python-pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

На Arch системный Python управляется pacman (`PEP 668`, externally-managed), а
потому `pip install` в систему запрещён — все зависимости ставятся только в
виртуальное окружение. **Никогда не используйте `pip install
--break-system-packages`.**

Альтернативы (по желанию):

- `pipx install ...` — удобно для одиночных CLI-приложений, но не для этого
  проекта с списком зависимостей.
- `python -m venv --system-site-packages .venv` — виртуалка видит пакеты,
  поставленные через pacman (например, если пакет `python-fastapi` уже стоит);
  тогда часть зависимостей можно не ставить через pip.

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
и без этого пакета приложение падает на импорте.

Версии заданы диапазонами — так pip сам подберёт версию с колёсами под ваш
CPython 3.14. Проверить фактические версии можно в venv:

```bash
python -c "import fastapi, uvicorn; print(fastapi.__version__, uvicorn.__version__)"
```

Все зависимости либо pure-Python, либо имеют колёса под 3.14 — версии в
`requirements.txt` зафиксированы, при установке pip сам подберёт подходящий
вариант.

## Запуск за 3 шага

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

> Если ваша оболочка — **zsh**, файл `.venv/bin/activate` из `venv` может
> не сработать (типичная ошибка: `'case' builtin not inside of switch
> block`). Это лечится без пересоздания окружения — просто вызывайте
> интерпретатор venv напрямую: `.venv/bin/python -m pip ...` и запускайте
> `./run.sh` (он делает то же самое и не зависит от `activate`).

В консоль выведутся все локальные адреса, например:

```
LAN: http://192.168.1.42:8000
LAN: http://10.0.0.15:8000
Local: http://127.0.0.1:8000
```

Наберите один из LAN-адресов в браузере телефона (устройства должны быть в
одной сети).

`run.sh` сам активирует `.venv`, проверяет версию Python (`>= 3.14`) и
запускает сервер. Прямой запуск тоже возможен: `source .venv/bin/activate && python -m app`.

## Как узнать IP ПК

- `run.sh` печатает все LAN-адреса автоматически.
- Вручную: `ip -4 addr show` (команда есть всегда, пакет `iproute2` входит в
  базовую систему Arch) или `hostname -I` (команда `hostname` в Arch обычно
  приходит из `inetutils` — при его отсутствии используйте `ip -4 addr`).

## Открыть с телефона

1. Убедитесь, что телефон и ПК в одной Wi-Fi сети.
2. Откройте в браузере телефона `http://<ip-пк>:8000` (адрес печатается при
   запуске сервера).
3. Введите имя (сохраняется в `localStorage`) и начните общение.

## Фаервол на Arch

На чистом Arch Linux фаервола по умолчанию нет — открывать порт не нужно,
просто заходите по адресу. Если он установлен, откройте TCP-порт 8000:

**ufw**
```bash
sudo ufw allow 8000/tcp
sudo ufw reload   # если правило меняли при активном ufw
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

## Автозапуск через systemd (user-юнит)

Создайте `~/.config/systemd/user/chat.service`:

```ini
[Unit]
Description=Чат (FastAPI over WebSocket)
After=network-online.target

[Service]
WorkingDirectory=%h/PCtoMobile
ExecStart=%h/PCtoMobile/.venv/bin/python -m app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

Замените `%h/PCtoMobile` на реальный путь к проекту, затем:

```bash
systemctl --user daemon-reload
systemctl --user enable --now chat.service
```

Чтобы служба работала и после выхода из системы, включите linger для своего
пользователя (один раз, от своего имени, без sudo):

```bash
loginctl enable-linger $USER
```

Логи: `journalctl --user -u chat.service -f`.

## Настройки

Все настройки — в `app/config.py` (по умолчанию зафиксированы здесь):

| Параметр | Значение по умолчанию | Описание |
|---|---|---|
| `PORT` | `8000` | TCP-порт сервера (переопределяется `CHAT_PORT`) |
| `HOST` | `0.0.0.0` | Интерфейс (переопределяется `CHAT_HOST`) |
| `MAX_UPLOAD_BYTES` | `200 * 1024 * 1024` (200 МБ) | Лимит файла (`CHAT_MAX_UPLOAD_MB`) |
| `PAGE_SIZE` | `50` | Сообщений на страницу истории (`CHAT_PAGE_SIZE`) |
| `TYPING_TIMEOUT` | `2.5` сек | Через сколько сбрасывается «печатает…» |

Папки: `data/chat.db` (SQLite) и `uploads/` (файлы), пути считаются от корня
проекта через `pathlib.Path`.

## Безопасность

- Имена файлов на диске — `UUID4` + санитизированное расширение, исходное имя
  хранится только в БД и отдаётся в `Content-Disposition`.
- Доступ к файлам — только через `/files/{file_id}`, пути с `..` не
  поддерживаются (id валидируется как UUID).
- При загрузке проверяется `Content-Length`, а фактический размер лимитируется
  вручную при стриминге; превышение отклоняется без записи.
- Файлы отдаются через `FileResponse` (стриминг/отдача из файловой системы),
  история хранится в SQLite с параметризованными запросами.

## Дальше

- Аутентификация / комнаты.
- Шифрование сообщений и файлов.
- Индикатор прочтения, редактирование и удаление сообщений.
- Сжатие и миниатюры изображений на сервере.
- Ограничение по количеству одновременных подключений.
