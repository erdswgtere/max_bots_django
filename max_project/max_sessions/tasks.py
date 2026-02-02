"""
Celery tasks for MaxClient operations.
Handles scheduled message sending, statistics aggregation, and maintenance tasks.
"""
import asyncio
import random
import string
import logging
from datetime import date, timedelta
from typing import List
from django.db.models import Sum
from celery import shared_task
from django.utils import timezone
from asgiref.sync import sync_to_async

from .models import MessageSchedule, MessageLog, DailyStatistics, MaxSession, TaskRun
from .services import MaxClientService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_scheduled_messages(self, schedule_id: int):
    """
    Celery задача для отправки сообщений по расписанию.
    Это основная задача, которая заменяет функцию main() из оригинального main.py.
    
    Args:
        schedule_id: ID объекта MessageSchedule из базы данных
    """
    try:
        schedule = MessageSchedule.objects.select_related('session', 'chat_config').get(id=schedule_id)
        
        if not schedule.is_active or not schedule.session.is_active:
            logger.warning(f"Schedule {schedule_id} or session is inactive, skipping")
            return
        
        # Redis Lock to prevent concurrent execution
        from django.core.cache import cache
        lock_id = f"lock:schedule:{schedule_id}"
        # Set lock for 10 minutes (long enough for message sending, cleanup deletes it)
        is_locked = cache.add(lock_id, "true", 600)
        
        if not is_locked:
            logger.warning(f"Schedule {schedule_id} is already running, skipping duplicate task")
            return

        logger.info(f"Starting scheduled message sending for schedule {schedule_id}")
        
        # Определяем количество сообщений для отправки
        num_messages = random.randint(schedule.min_messages, schedule.max_messages)
        logger.info(f"Will send {num_messages} messages")
        
        # Создаем запись о запуске
        task_run = TaskRun.objects.create(
            schedule=schedule,
            session=schedule.session,
            total_expected=num_messages,
            status='running'
        )
        
        # Запускаем асинхронную функцию отправки
        asyncio.run(_send_messages_async(schedule, num_messages, task_run.id))
        
        logger.info(f"Successfully completed schedule {schedule_id}")
        
    except MessageSchedule.DoesNotExist:
        logger.error(f"MessageSchedule {schedule_id} not found")
    except Exception as e:
        logger.error(f"Error in send_scheduled_messages for schedule {schedule_id}: {e}")
        # Повторная попытка через экспоненциальный backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    finally:
        # Release the lock
        from django.core.cache import cache
        cache.delete(f"lock:schedule:{schedule_id}")


async def _send_messages_async(schedule: MessageSchedule, num_messages: int, task_run_id: int):
    """
    Асинхронная функция для отправки сообщений.
    
    Args:
        schedule: Объект MessageSchedule
        num_messages: Количество сообщений для отправки
        task_run_id: ID объекта TaskRun для статистики
    """
    service = MaxClientService(schedule.session)
    
    try:
        # Устанавливаем онлайн сессию
        await service.establish_online_session()
        
        for i in range(num_messages):
            # Генерируем случайное сообщение (как в оригинальном main.py)
            message_length = random.randint(schedule.min_message_length, schedule.max_message_length)
            message_text = ''.join(random.choices(string.ascii_letters, k=message_length))
            
            try:
                # Отправляем сообщение
                await service.send_message(
                    chat_id=schedule.chat_config.chat_id,
                    message_text=message_text,
                    chat_config=schedule.chat_config
                )
                
                logger.info(f"Message {i+1}/{num_messages} sent successfully")
                
                # Обновляем статистику
                await sync_to_async(update_statistics)(schedule.session.id, success=True, task_run_id=task_run_id)
                
            except Exception as e:
                logger.error(f"Error sending message {i+1}/{num_messages}: {e}")
                await sync_to_async(update_statistics)(schedule.session.id, success=False, task_run_id=task_run_id)
            
            # Ждем случайный интервал перед следующим сообщением (кроме последнего)
            if i < num_messages - 1:
                interval = random.randint(schedule.min_interval_seconds, schedule.max_interval_seconds)
                logger.info(f"Waiting {interval} seconds before next message")
                await asyncio.sleep(interval)
                
    finally:
        # Завершаем запись о запуске
        await sync_to_async(finish_task_run)(task_run_id)
        # Закрываем соединение
        await service.close()


from .metrics import ACTIVE_SESSIONS, MESSAGES_SENT, MESSAGES_FAILED


def update_statistics(session_id: int, success: bool = True, task_run_id: int = None):
    """
    Обновление ежедневной статистики и статистики конкретного запуска.
    Также обновление внешних Prometheus метрик.
    """
    try:
        session = MaxSession.objects.get(id=session_id)
        session_name = session.name or "Unnamed"
        device_id = session.device_id or "Unknown"
    except MaxSession.DoesNotExist:
        session_name = "Unknown"
        device_id = "Unknown"

    today = date.today()
    
    # 1. Django ORM Stats
    stats, created = DailyStatistics.objects.get_or_create(
        session_id=session_id,
        date=today,
        defaults={
            'total_messages': 0,
            'successful_messages': 0,
            'failed_messages': 0
        }
    )
    
    stats.total_messages += 1
    if success:
        stats.successful_messages += 1
        # Prometheus: Успешная отправка
        MESSAGES_SENT.labels(session_name=session_name, device_id=device_id).inc()
    else:
        stats.failed_messages += 1
        # Prometheus: Ошибка
        MESSAGES_FAILED.labels(session_name=session_name, device_id=device_id).inc()
    stats.save()

    # 2. Update Active Sessions Gauge
    ACTIVE_SESSIONS.set(MaxSession.objects.filter(is_active=True).count())

    # 3. Обновляем TaskRun если есть ID
    if task_run_id:
        try:
            run = TaskRun.objects.get(id=task_run_id)
            if success:
                run.sent_success += 1
            else:
                run.sent_failed += 1
            run.save()
        except TaskRun.DoesNotExist:
            pass
    
    logger.info(f"Updated statistics for session {session_id}: {stats.successful_messages}/{stats.total_messages}")


def finish_task_run(task_run_id: int):
    """Помечает запуск как завершенный"""
    try:
        run = TaskRun.objects.get(id=task_run_id)
        run.finished_at = timezone.now()
        run.status = 'completed'
        run.save()
    except TaskRun.DoesNotExist:
        pass


@shared_task
def aggregate_weekly_statistics(session_id: int = None):
    """
    Агрегация недельной статистики.
    Используется для отчетов и дашбордов.
    
    Args:
        session_id: ID сессии (если None, агрегирует для всех)
    """
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        sessions = MaxSession.objects.filter(id=session_id) if session_id else MaxSession.objects.all()
        
        results = []
        for session in sessions:
            stats = DailyStatistics.objects.filter(
                session=session,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total=Sum('total_messages'),
                successful=Sum('successful_messages'),
                failed=Sum('failed_messages')
            )
            
            results.append({
                'session_id': session.id,
                'device_id': session.device_id,
                'total_messages': stats['total'] or 0,
                'successful_messages': stats['successful'] or 0,
                'failed_messages': stats['failed'] or 0
            })
        
        logger.info(f"Weekly statistics aggregated for {len(results)} sessions")
        return results
        
    except Exception as e:
        logger.error(f"Error in aggregate_weekly_statistics: {e}")
        raise


@shared_task
def cleanup_old_logs(days_to_keep: int = 30):
    """
    Очистка старых логов сообщений.
    Запускается периодически для предотвращения переполнения БД.
    
    Args:
        days_to_keep: Количество дней для хранения логов
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        deleted_count, _ = MessageLog.objects.filter(sent_at__lt=cutoff_date).delete()
        
        logger.info(f"Cleaned up {deleted_count} old message logs (older than {days_to_keep} days)")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_logs: {e}")
        raise


@shared_task
def test_session_connection(session_id: int):
    """
    Тестирование подключения для сессии.
    Используется для проверки работоспособности сессий.
    
    Args:
        session_id: ID сессии для проверки
    """
    try:
        session = MaxSession.objects.get(id=session_id)
        service = MaxClientService(session)
        
        # Пытаемся установить онлайн сессию
        async def test_connection():
            try:
                await service.establish_online_session()
                await service.close()
                return True
            except Exception as e:
                logger.error(f"Connection test failed for session {session_id}: {e}")
                return False
        
        result = asyncio.run(test_connection())
        
        if result:
            logger.info(f"Connection test passed for session {session_id}")
        else:
            logger.warning(f"Connection test failed for session {session_id}")
            # Можно деактивировать сессию
            # session.is_active = False
            # session.save()
        
        return result
        
    except MaxSession.DoesNotExist:
        logger.error(f"Session {session_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error in test_session_connection: {e}")
        raise


@shared_task
def cleanup_inactive_sessions(days_inactive: int = 90):
    """
    Очистка неактивных сессий.
    
    Args:
        days_inactive: Количество дней неактивности для удаления
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_inactive)
        
        inactive_sessions = MaxSession.objects.filter(
            is_active=False,
            updated_at__lt=cutoff_date
        )
        
        count = inactive_sessions.count()
        inactive_sessions.delete()
        
        logger.info(f"Cleaned up {count} inactive sessions (inactive for {days_inactive} days)")
        return count
        
    except Exception as e:
        logger.error(f"Error in cleanup_inactive_sessions: {e}")
        raise



