from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json
import logging
from .models import MessageSchedule

logger = logging.getLogger(__name__)

@receiver(post_save, sender=MessageSchedule)
def sync_periodic_task(sender, instance, created, **kwargs):
    """
    Автоматическое создание или обновление периодической задачи Celery при сохранении расписания.
    """
    task_name = f"Send messages: schedule {instance.id}"
    
    if not instance.is_active:
        # Если расписание деактивировано, отключаем задачу
        deleted_count = PeriodicTask.objects.filter(name=task_name).update(enabled=False)
        if deleted_count:
            logger.info(f"Disabled periodic task: {task_name}")
        return

    try:
        # Настраиваем crontab на конкретное время
        # instance.scheduled_time - это объект time
        hour = instance.scheduled_time.hour
        minute = instance.scheduled_time.minute
        
        # Для daily/weekly/once
        # Примечание: 'once' в crontab сложно реализовать без удаления задачи после запуска, 
        # поэтому пока делаем как ежедневную, либо можно добавить логику в саму задачу.
        day_of_week = '*'
        day_of_month = '*'
        month_of_year = '*'
        
        if instance.frequency == 'weekly':
            # По умолчанию понедельник (1)
            day_of_week = '1' 
        
        # Создаем или получаем расписание с привязкой к таймзоне Москвы
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=str(minute),
            hour=str(hour),
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            timezone='Europe/Moscow'
        )

        # Создаем или обновляем PeriodicTask
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'crontab': schedule,
                'task': 'max_sessions.tasks.send_scheduled_messages',
                'args': json.dumps([instance.id]),
                'enabled': True,
                'description': f"Автоматическая задача для расписания {instance.id} ({instance.chat_config.chat_name})"
            }
        )
        logger.info(f"Synced periodic task: {task_name} for {hour}:{minute} Moscow time")
        
    except Exception as e:
        logger.error(f"Error syncing periodic task for schedule {instance.id}: {e}")

@receiver(post_delete, sender=MessageSchedule)
def delete_periodic_task(sender, instance, **kwargs):
    """
    Удаление периодической задачи при удалении расписания.
    """
    task_name = f"Send messages: schedule {instance.id}"
    deleted_count, _ = PeriodicTask.objects.filter(name=task_name).delete()
    if deleted_count:
        logger.info(f"Deleted periodic task: {task_name}")
