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
