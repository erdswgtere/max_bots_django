from prometheus_client import Gauge, Counter

# Метрика количества активных сессий (ботов)
ACTIVE_SESSIONS = Gauge(
    'max_sessions_active_total',
    'Total number of active bot sessions'
)

# Прогресс отправки сообщений (успешно)
MESSAGES_SENT = Counter(
    'max_messages_sent_total',
    'Total successful messages sent',
    ['session_name', 'device_id']
)

# Ошибки при отправке
MESSAGES_FAILED = Counter(
    'max_messages_failed_total',
    'Total failed messages',
    ['session_name', 'device_id']
)
