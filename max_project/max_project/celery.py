"""
Celery configuration for max_project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Установка переменной окружения для Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'max_project.settings')

app = Celery('max_project')

# Загрузка конфигурации из Django settings с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение tasks.py в Django apps
app.autodiscover_tasks()

# Конфигурация периодических задач (Celery Beat)
app.conf.beat_schedule = {
    # Очистка старых логов каждую ночь в 3:00
    'cleanup-old-logs': {
        'task': 'max_sessions.tasks.cleanup_old_logs',
        'schedule': crontab(hour=3, minute=0),
        'kwargs': {'days_to_keep': 30}
    },
    
    # Очистка неактивных сессий каждую неделю в воскресенье в 4:00
    'cleanup-inactive-sessions': {
        'task': 'max_sessions.tasks.cleanup_inactive_sessions',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
        'kwargs': {'days_inactive': 90}
    },
    
    # Агрегация недельной статистики каждый понедельник в 1:00
    'aggregate-weekly-stats': {
        'task': 'max_sessions.tasks.aggregate_weekly_statistics',
        'schedule': crontab(hour=1, minute=0, day_of_week=1),
    },
}

# Настройки для задач
app.conf.task_routes = {
    'max_sessions.tasks.send_scheduled_messages': {'queue': 'default'},
    'max_sessions.tasks.cleanup_old_logs': {'queue': 'maintenance'},
    'max_sessions.tasks.cleanup_inactive_sessions': {'queue': 'maintenance'},
}

# Тайм-аут задач (в секундах)
app.conf.task_time_limit = 600  # 10 минут
app.conf.task_soft_time_limit = 540  # 9 минут

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
