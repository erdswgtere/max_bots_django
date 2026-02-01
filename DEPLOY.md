# Инструкция по деплою (Manual Deployment)

Этот проект разворачивается с помощью Docker Compose. Все необходимые сервисы (Django, PostgreSQL, Redis, Celery, Nginx) настроены и готовы к работе.

### 1. Подготовка окружения
Перед запуском необходимо создать файл настроек `.env`.
```bash
cp .env.example .env
```
Отредактируйте `.env`, установив свои значения (пароли, секретные ключи).

### 2. Сборка и запуск контейнеров
Запустите сборку и старт всех сервисов в фоновом режиме:
```bash
docker-compose up -d --build
```

### 3. Обязательные действия после запуска
Эти команды нужно выполнить один раз при первом развертывании или после изменения моделей данных.

**Создание файлов миграций (если были изменения в моделях):**
```bash
docker-compose exec web python max_project/manage.py makemigrations max_sessions
```

**Применение миграций (создание таблиц в БД):**
```bash
docker-compose exec web python max_project/manage.py migrate
```

**Сбор статических файлов (для корректного отображения админки):**
```bash
docker-compose exec web python max_project/manage.py collectstatic --noinput
```

**Создание администратора (суперпользователя):**
```bash
docker-compose exec web python max_project/manage.py createsuperuser
```

### 4. Доступ к приложению
*   **Через Nginx (Продакшн):** `http://<IP-вашего-сервера>/` (порт 80)
*   **Напрямую к Django (Отладка):** `http://<IP-вашего-сервера>:8001/`
*   **Админ-панель Django:** `http://<IP-вашего-сервера>/admin/`
*   **Мониторинг задач Flower:** `http://<IP-вашего-сервера>:5555/`

### 5. Полезные команды управления

**Просмотр логов:**
```bash
docker-compose logs -f web
```

**Перезапуск всех сервисов:**
```bash
docker-compose restart
```

**Остановка и удаление контейнеров:**
```bash
docker-compose down
```

**Полная очистка (включая данные базы данных):**
```bash
docker-compose down -v
```

---
> [!NOTE]
> Логи приложения сохраняются в папку `./logs` в корне проекта.
