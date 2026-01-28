# Max Bots Django - WebSocket Messenger Automation

Веб-приложение на Django для автоматизации отправки сообщений в мессенджер Max с использованием WebSocket API.

## 🚀 Особенности

- **Django Admin Interface** - удобное управление сессиями и расписаниями
- **Автоматическая отправка сообщений** - планировщик задач через Celery Beat
- **Статистика** - отслеживание успешных/неудачных отправок за день и неделю
- **Микросервисная архитектура** - все компоненты в Docker контейнерах
- **Асинхронный WebSocket клиент** - эффективная работа с Max API
- **PostgreSQL** - надежное хранение данных
- **Redis** - кеширование и очереди задач

## 📋 Технологический стек

- **Backend**: Django 5.x, Django REST Framework
- **Database**: PostgreSQL 16
- **Cache & Queue**: Redis 7
- **Task Queue**: Celery + Celery Beat
- **Web Server**: Nginx + Gunicorn
- **WebSocket**: websockets (async)
- **Monitoring**: Flower (Celery monitoring)
- **Containerization**: Docker + Docker Compose

## 📂 Структура проекта

```
max_bots_django/
├── docker-compose.yml          # Конфигурация всех сервисов
├── Dockerfile                  # Образ Django приложения
├── requirements.txt            # Python зависимости
├── .env.example               # Шаблон переменных окружения
├── nginx/
│   └── nginx.conf             # Конфигурация Nginx
├── max_project/               # Django проект
│   ├── manage.py
│   ├── max_project/           # Настройки проекта
│   │   ├── settings.py        # Основные настройки
│   │   ├── celery.py          # Конфигурация Celery
│   │   └── urls.py
│   └── max_sessions/          # Django app
│       ├── models.py          # Модели БД
│       ├── services.py        # MaxClient WebSocket сервис
│       ├── tasks.py           # Celery задачи
│       ├── admin.py           # Admin интерфейс
│       └── views.py           # API views
└── logs/                      # Логи приложения
```

## 🛠️ Установка и запуск

### Предварительные требования

- Docker
- Docker Compose
- Git

### Быстрый старт

1. **Клонируйте репозиторий**
```bash
cd /home/user/repos/max_bots_django
```

2. **Создайте .env файл**
```bash
cp .env.example .env
# Отредактируйте .env при необходимости
```

3. **Запустите все сервисы**
```bash
docker-compose up --build -d
```

4. **Создайте суперпользователя Django**
```bash
docker-compose exec web sh -c "cd max_project && python manage.py createsuperuser"
```

5. **Откройте веб-интерфейс**
- Django Admin: http://localhost/admin
- Flower (мониторинг Celery): http://localhost:5555

## 📊 Компоненты системы

### Сервисы в Docker Compose

| Сервис | Порт | Описание |
|--------|------|----------|
| `db` | 5432 | PostgreSQL база данных |
| `redis` | 6379 | Redis (кеш + Celery broker) |
| `web` | 8000 | Django + Gunicorn |
| `celery_worker` | - | Celery worker (обработка задач) |
| `celery_beat` | - | Celery Beat (планировщик) |
| `flower` | 5555 | Мониторинг Celery |
| `nginx` | 80 | Reverse proxy + статика |

### Модели базы данных

- **MaxSession** - сессии авторизации Max
- **ChatConfig** - конфигурация чатов для отправки
- **MessageSchedule** - расписания отправки сообщений
- **MessageLog** - логи всех отправленных сообщений
- **DailyStatistics** - ежедневная статистика

## 🎯 Использование

### 1. Создание сессии Max

1. Войдите в Django Admin: http://localhost/admin
2. Перейдите в "Max сессии" → "Добавить"
3. Укажите номер телефона
4. Следуйте процессу авторизации (через код из SMS)

### 2. Настройка чата

1. В Django Admin перейдите в "Конфигурации чатов"
2. Создайте новый чат, указав:
   - Сессию
   - ID чата в Max
   - Название чата

### 3. Создание расписания

1. Перейдите в "Расписания сообщений"
2. Создайте расписание:
   - Выберите сессию и чат
   - Укажите частоту и время
   - Настройте параметры отправки:
     - Количество сообщений (мин/макс)
     - Интервалы между сообщениями
     - Длина сообщений

### 4. Просмотр статистики

- **Логи сообщений**: Admin → "Логи сообщений"
- **Дневная статистика**: Admin → "Дневная статистика"
- **Celery задачи**: http://localhost:5555 (Flower)

## 🔧 Управление задачами

### Запуск расписания вручную

В Django Admin откройте расписание и нажмите "Запустить сейчас"

Или через Flower:
1. Откройте http://localhost:5555
2. Перейдите в Tasks
3. Найдите `send_scheduled_messages`
4. Запустите с параметром `schedule_id`

### Мониторинг Celery

Flower предоставляет:
- Список активных задач
- Историю выполнения
- Статистику воркеров
- График нагрузки

## 📝 Логи

Логи доступны в нескольких местах:

1. **Docker logs**:
```bash
docker-compose logs -f web          # Django
docker-compose logs -f celery_worker # Celery worker
docker-compose logs -f celery_beat   # Celery beat
```

2. **Файловые логи**: `./logs/django.log`

3. **Django Admin**: "Логи сообщений"

## 🔄 Миграция из старого main.py

Старое приложение `main.py` было мигрировано следующим образом:

| Старый код | Новое расположение |
|------------|-------------------|
| `class MaxClient` | `max_sessions/services.py` → `MaxClientService` |
| `main()` функция | `max_sessions/tasks.py` → `send_scheduled_messages` |
| Pickle файл сессий | PostgreSQL → `MaxSession` |
| Параметры отправки | PostgreSQL → `MessageSchedule` |

## 🛑 Остановка сервисов

```bash
# Остановить все сервисы
docker-compose down

# Остановить и удалить volumes (БД будет очищена!)
docker-compose down -v
```

## 🔐 Безопасность

⚠️ **Важно для production**:

1. Измените `SECRET_KEY` в `.env`
2. Установите `DEBUG=False`
3. Настройте `ALLOWED_HOSTS`
4. Используйте сильные пароли для БД
5. Настройте SSL/TLS для Nginx
6. Включите firewall

## 📚 API (опционально)

REST API доступен по адресу: http://localhost/api/

Endpoints:
- `/api/sessions/` - управление сессиями
- `/api/chats/` - управление чатами
- `/api/schedules/` - управление расписаниями
- `/api/logs/` - просмотр логов (read-only)
- `/api/statistics/daily/` - дневная статистика
- `/api/statistics/weekly/` - недельная статистика

## 🐛 Troubleshooting

### Проблема: Не подключается к PostgreSQL

**Решение**: Убедитесь, что контейнер `db` запущен:
```bash
docker-compose ps
docker-compose logs db
```

### Проблема: Celery задачи не выполняются

**Решение**: Проверьте логи Celery worker:
```bash
docker-compose logs -f celery_worker
```

### Проблема: Ошибка авторизации Max

**Решение**: 
1. Проверьте актуальность токена в БД
2. Пересоздайте сессию через Django Admin
3. Проверьте логи WebSocket соединения

## 👨‍💻 Разработка

### Локальный запуск без Docker

```bash
# Установка зависимостей
cd max_project
pip install -r ../requirements.txt

# Запуск PostgreSQL и Redis отдельно
# Настройте .env для localhost

# Миграции
python manage.py migrate

# Запуск Django dev server
python manage.py runserver

# В другом терминале - Celery worker
celery -A max_project worker -l info

# В третьем терминале - Celery beat
celery -A max_project beat -l info
```

## 📄 Лицензия

MIT

## 🤝 Поддержка

При возникновении проблем создайте issue в репозитории проекта.
