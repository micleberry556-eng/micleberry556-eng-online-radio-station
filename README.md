# Online Radio Station

Самостоятельное онлайн-радио с админ-панелью, загрузкой MP3 и синхронной трансляцией.
Все слушатели слышат одну и ту же музыку одновременно — как настоящее радио.

## Возможности

- **Синхронная трансляция** — все слушатели на одной волне
- **Админ-панель** — полное управление станциями, треками и пользователями
- **Загрузка MP3** — drag & drop, множественная загрузка
- **SQLite** — база данных создаётся автоматически, без внешних зависимостей
- **Docker** — один `docker compose up` и радио работает
- **Адаптивный дизайн** — работает на десктопе и мобильных

## Быстрый старт

### Docker (рекомендуется)

```bash
git clone <repo-url> && cd online-radio-station

# Запуск
docker compose up -d

# Радио доступно на http://localhost:8000
# Админ-панель: http://localhost:8000/admin
```

### Без Docker

```bash
git clone <repo-url> && cd online-radio-station

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Запустить
python run.py
```

## Настройка

Переменные окружения (или `.env` файл):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | Секретный ключ Flask |
| `ADMIN_USERNAME` | `admin` | Логин администратора |
| `ADMIN_PASSWORD` | `admin123` | Пароль администратора |

## Использование

1. Откройте `http://localhost:8000/admin` и войдите (admin / admin123)
2. Создайте станцию или используйте предустановленные
3. Загрузите MP3 файлы в станцию
4. Откройте `http://localhost:8000` — радио готово к прослушиванию

## Архитектура

```
online-radio-station/
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── models.py            # SQLite models, auto-init, seed data
│   ├── admin.py             # Admin panel CRUD routes
│   ├── auth.py              # Authentication (login/logout)
│   ├── routes.py            # Public radio player routes
│   ├── stream.py            # Synchronized MP3 streaming engine
│   ├── static/
│   │   ├── css/             # Styles (admin + public)
│   │   ├── js/player.js     # Radio player JavaScript
│   │   └── uploads/         # Uploaded MP3 files
│   └── templates/
│       ├── admin/           # Admin panel templates
│       └── public/          # Public player templates
├── config.py                # Configuration
├── run.py                   # Entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container image
└── docker-compose.yml       # One-command deployment
```

### Как работает трансляция

Каждая станция имеет фоновый поток (`StationBroadcaster`), который:
1. Читает MP3 файлы из плейлиста последовательно
2. Парсит MP3 фреймы и отправляет их в кольцевой буфер в реальном времени
3. Все подключённые слушатели читают из одного буфера
4. Когда плейлист заканчивается — начинается сначала

## Лицензия

MIT
