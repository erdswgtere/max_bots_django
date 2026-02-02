# Max Bots Django - WebSocket Messenger Automation

Веб-приложение на Django для автоматизации отправки сообщений в мессенджер Max с использованием WebSocket API.

## 🚀 Особенности

- **Django Admin Interface** - удобное управление сессиями и расписаниями.
- **Многосессионная работа** - конфигурации чатов независимы от ботов, один чат могут «обрабатывать» разные сессии одновременно.
- **История запусков (Task Runs)** - детальный лог каждого срабатывания планировщика с % успеха и счетчиками сообщений.
- **Мониторинг Prometheus** - экспорт метрик (активные сессии, успехи/ошибки) для Grafana через `/metrics`.
- **Автоматическая отправка** - планировщик задач через Celery Beat.
- **Микросервисная архитектура** - все компоненты в Docker контейнерах.
- **Асинхронный WebSocket клиент** - эффективная имитация официального клиента Max.

## 📋 Технологический стек

- **Backend**: Django 5.x, Django REST Framework
- **Database**: PostgreSQL 16
- **Cache & Queue**: Redis 7
- **Task Queue**: Celery + Celery Beat
- **Monitoring**: Prometheus (Metrics), Flower (Celery stats)
- **Web Server**: Nginx + Gunicorn
- **WebSocket**: websockets (async)
- **Monitoring**: Flower (Celery monitoring)
- **Containerization**: Docker + Docker Compose

## 📂 Документация

- 📄 **[DEPLOY.md](DEPLOY.md)** — Подробная инструкция по развертыванию на сервер.
- 📊 **[MONITORING.md](MONITORING.md)** — Настройка Prometheus и рекомендации по Grafana.

---

## 📂 Структура проекта

```text
max_bots_django/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD автоматизация деплоя
├── nginx/
│   └── nginx.conf              # Конфигурация Reverse Proxy
├── max_project/                # Корень Django проекта
│   ├── manage.py               # Утилита управления Django
│   ├── static/                 # Исходная статика проекта
│   ├── templates/              # HTML шаблоны
│   │   └── admin/
│   │       └── max_sessions/
│   │           └── qr_auth.html # Шаблон для QR-авторизации
│   ├── max_project/            # Системная папка проекта
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   ├── celery.py           # Конфигурация Celery
│   │   ├── settings.py         # Основные настройки (БД, кеш, логи)
│   │   ├── urls.py             # Главные роуты
│   │   └── wsgi.py
│   └── max_sessions/           # Основное приложение (Логика ботов)
│       ├── __init__.py
│       ├── admin.py            # Настройка админ-панели и инлайнов
│       ├── apps.py
│       ├── metrics.py          # Prometheus метрики (кастомные)
│       ├── models.py           # Модели (Session, TaskRun, Logs)
│       ├── serializers.py      # Преобразование данных для API
│       ├── services.py         # MaxClientService (WebSocket клиент)
│       ├── tasks.py            # Celery задачи и логика отправки
│       ├── tests.py
│       ├── urls.py             # API эндпоинты приложения
│       ├── views.py            # Обработка запросов
│       └── migrations/         # История изменений БД
├── .env.example                # Шаблон переменных окружения
├── .gitignore                  # Исключения для GIT
├── DEPLOY.md                   # Руководство по развертыванию
├── MONITORING.md               # Руководство по мониторингу
├── README.MD                   # Этот файл
├── Dockerfile                  # Инструкция сборки образа Web/Celery
├── docker-compose.yml          # Оркестрация всех сервисов
└── requirements.txt            # Список Python зависимостей
```

## 🛠️ Установка и запуск

### Быстрый старт

1. **Создайте .env файл**
```bash
cp .env.example .env
```

2. **Запустите все сервисы**
```bash
docker-compose up --build -d
```

3. **Миграции и статика**
```bash
docker-compose exec web python max_project/manage.py migrate
docker-compose exec web python max_project/manage.py collectstatic --noinput
```

4. **Создайте суперпользователя**
```bash
docker-compose exec web python max_project/manage.py createsuperuser
```

5. **Доступ**
- Django Admin: http://localhost/admin
- Flower: http://localhost:5555
- Metrics: http://localhost/metrics

## 📊 Компоненты системы

### Модели базы данных

- **MaxSession** - сессии авторизации Max (с именованием и QR-входом).
- **ChatConfig** - параметры конкретных чатов (ID, название).
- **MessageSchedule** - привязка бота (сессии) к чату с настройкой частоты и параметров текста.
- **TaskRun** - история отдельных запусков (кто, когда, сколько отправил).
- **MessageLog** - детальный лог каждого сообщения.
- **DailyStatistics** - агрегированная статистика по дням.

## 🎯 Использование

### 1. Создание сессии и вход через QR
1. В Admin перейдите в "Max сессии" → "Добавить".
2. Создайте сессию, затем в списке выберите "Вход через QR".
3. Отсканируйте код в мобильном приложении Max. Статус обновится автоматически.

### 2. Настройка рассылки
1. Создайте **Конфигурацию чата** (укажите ID чата).
2. Создайте **Расписание сообщений**, выбрав нужную сессию и чат.
3. Настройте диапазоны количества сообщений и интервалы.

### 3. Мониторинг
- Посетите `/metrics` для просмотра сырых данных Prometheus.
- Используйте Flower для контроля очереди задач Celery.
- Смотрите "Историю запусков" прямо внутри страницы "Расписания" в админке.

## 🔧 Управление и Логи

- **Запуск вручную**: Кнопка "Запустить сейчас" в списке расписаний.
- **Логи контейнеров**: `docker-compose logs -f web`.
- **Файловые логи**: `./logs/django.log`.

## 🔄 Миграция из старого main.py

| Старый код | Новое расположение |
|------------|-------------------|
| `class MaxClient` | `max_sessions/services.py` → `MaxClientService` |
| `main()` функция | `max_sessions/tasks.py` → `send_scheduled_messages` |
| Pickle файлы | PostgreSQL → `MaxSession` |

## � Troubleshooting

- **Ошибка 502**: Проверьте логи Nginx и статус контейнера `web`.
- ** Celery не шлет**: Убедитесь, что `celery_beat` и `celery_worker` запущены и видят Redis.
- **QR не сканируется**: Проверьте сетевую доступность вашего сервера для интернета или корректность `ALLOWED_HOSTS`.

## 👨‍💻 Разработка

Для локального запуска без Docker используйте `pip install -r requirements.txt` и настройте `.env` на локальные инстансы БД и Redis.

## 📄 Лицензия

MIT
