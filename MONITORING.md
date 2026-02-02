# Monitoring with Prometheus

This project exports metrics for Prometheus at the `/metrics` endpoint.

## Available Metrics

| Metric | Type | Description |
| --- | --- | --- |
| `max_sessions_active_total` | Gauge | Total number of active bot sessions in the database. |
| `max_messages_sent_total` | Counter | Total successful messages sent per bot (labels: `session_name`, `device_id`). |
| `max_messages_failed_total` | Counter | Total failed messages per bot (labels: `session_name`, `device_id`). |
| `django_http_requests_before_middlewares_total` | Counter | Total HTTP requests. |
| `django_db_query_duration_seconds_sum` | Summary | Total time spent in DB queries. |

## How to Scrape

Add the following to your `prometheus.yml` configuration:

```yaml
scrape_configs:
  - job_name: 'max_bots'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['web:8000'] # Or your server IP if external
```

## Grafana Integration

You can use these metrics to build a dashboard.
- **Success Rate Calculation**: `sum(rate(max_messages_sent_total[5m])) / (sum(rate(max_messages_sent_total[5m])) + sum(rate(max_messages_failed_total[5m])))`
- **Active Bots**: `max_sessions_active_total`

### Recommended Dashboard Structure

Я рекомендую разделить панель на 3 логические зоны:

#### 1. Основные KPI (Верхняя панель, тип "Stat")
- **Активные боты**: `max_sessions_active_total` — сколько ботов сейчас в сети.
- **Общий Success Rate**: `sum(rate(max_messages_sent_total[1h])) / (sum(rate(max_messages_sent_total[1h])) + sum(rate(max_messages_failed_total[1h]))) * 100` — % успеха за последний час.
- **Всего за 24ч**: `sum(increase(max_messages_sent_total[24h]))` — сколько сообщений ушло за сутки.

#### 2. Аналитика по сессиям (Тип "Time series")
- **Интенсивность по ботам**: `rate(max_messages_sent_total[5m])` — расщепление потока по `session_name`. Поможет увидеть, если какой-то один бот начал слать меньше других.
- **График ошибок**: `rate(max_messages_failed_total[5m])` — если кривая пошла вверх, значит есть проблемы с соединением или баны.

#### 3. Здоровье системы (Технический раздел)
- **Нагрузка на БД**: `rate(django_db_query_duration_seconds_sum[5m])` — сколько времени тратит Django на запросы к Postgres.
- **Потребление RAM**: `process_resident_memory_bytes` — сколько оперативной памяти ест проект в Docker.
- **Ошибки 500**: `django_http_responses_total_by_status_total{status="500"}` — любые внутренние ошибки сервера.

## How to Scrape
