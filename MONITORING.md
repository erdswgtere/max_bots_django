# Мониторинг с помощью Prometheus

Этот проект экспортирует метрики для Prometheus через эндпоинт `/metrics`.

## Доступные метрики

| Метрика | Тип | Описание |
| --- | --- | --- |
| `max_sessions_active_total` | Gauge | Общее количество активных сессий ботов в базе данных. |
| `max_messages_sent_total` | Counter | Общее количество успешно отправленных сообщений (метки: `session_name`, `device_id`). |
| `max_messages_failed_total` | Counter | Общее количество неудачных попыток отправки (метки: `session_name`, `device_id`). |
| `django_http_requests_before_middlewares_total` | Counter | Общее количество HTTP-запросов. |
| `django_db_query_duration_seconds_sum` | Summary | Общее время, затраченное на запросы к базе данных. |

## Интеграция с Grafana

### Рекомендуемая структура дашборда

Я рекомендую разделить панель на 3 логические зоны:

#### 1. Основные KPI (Верхняя панель, тип "Stat")
- **Активные боты**: `max_sessions_active_total` — сколько ботов сейчас в сети.
- **Общий % успеха**: `sum(rate(max_messages_sent_total[1h])) / (sum(rate(max_messages_sent_total[1h])) + sum(rate(max_messages_failed_total[1h]))) * 100` — процент успеха за последний час.
- **Всего за 24ч**: `sum(increase(max_messages_sent_total[24h]))` — сколько сообщений успешно ушло за сутки.

#### 2. Аналитика по сессиям (Тип "Time series")
- **Интенсивность по ботам**: `rate(max_messages_sent_total[5m])` — распределение потока по `session_name`. Помогает увидеть, если какой-то конкретный бот стал менее активен.
- **График ошибок**: `rate(max_messages_failed_total[5m])` — позволяет быстро заметить всплеск ошибок или блокировок.

#### 3. Состояние системы (Технический раздел)
- **Нагрузка на БД**: `rate(django_db_query_duration_seconds_sum[5m])` — время, которое Django тратит на запросы к Postgres.
- **Потребление памяти (RAM)**: `process_resident_memory_bytes` — объем оперативной памяти, используемый процессом в Docker.
- **Ошибки 500**: `django_http_responses_total_by_status_total{status="500"}` — отслеживание внутренних ошибок сервера.

## Как настроить сбор метрик (Scrape)

Добавьте следующую конфигурацию в ваш файл `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'max_bots'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['web:8000'] # Или IP вашего сервера, если Prometheus снаружи
```
