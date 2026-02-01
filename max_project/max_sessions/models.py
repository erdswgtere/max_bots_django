from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class MaxSession(models.Model):
    """Хранение сессий Max мессенджера"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='max_sessions')
    name = models.CharField(max_length=255, verbose_name='Название сессии', blank=True, null=True)
    auth_token = models.TextField(verbose_name='Токен авторизации', blank=True, null=True)
    user_agent_data = models.JSONField(verbose_name='Данные User-Agent', blank=True, null=True)
    device_id = models.CharField(max_length=100, verbose_name='ID устройства', blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена')
    
    class Meta:
        db_table = 'max_sessions'
        verbose_name = 'Сессия в Max'
        verbose_name_plural = 'Сессии в Max'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name or self.device_id or 'Новая сессия'} - {'Активна' if self.is_active else 'Неактивна'}"


class ChatConfig(models.Model):
    """Конфигурация чатов для отправки сообщений"""
    session = models.ForeignKey(MaxSession, on_delete=models.CASCADE, related_name='chats')
    chat_id = models.CharField(max_length=100, verbose_name='ID чата')
    chat_name = models.CharField(max_length=255, blank=True, verbose_name='Название чата')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    
    class Meta:
        db_table = 'chat_configs'
        verbose_name = 'Конфигурация чата'
        verbose_name_plural = 'Конфигурации чатов'
        unique_together = ['session', 'chat_id']
        ordering = ['chat_name']
    
    def __str__(self):
        return f"{self.chat_name or self.chat_id} ({self.session.device_id})"


class MessageSchedule(models.Model):
    """Расписание отправки сообщений"""
    FREQUENCY_CHOICES = [
        ('once', 'Один раз'),
        ('daily', 'Ежедневно'),
        ('weekly', 'Еженедельно'),
        ('custom', 'Пользовательское'),
    ]
    
    session = models.ForeignKey(MaxSession, on_delete=models.CASCADE, related_name='schedules')
    chat_config = models.ForeignKey(ChatConfig, on_delete=models.CASCADE, related_name='schedules')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, verbose_name='Частота')
    scheduled_time = models.TimeField(verbose_name='Время запуска')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    # Параметры отправки сообщений
    min_messages = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Мин. количество сообщений'
    )
    max_messages = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Макс. количество сообщений'
    )
    min_interval_seconds = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        verbose_name='Мин. интервал (сек)'
    )
    max_interval_seconds = models.IntegerField(
        default=15,
        validators=[MinValueValidator(1)],
        verbose_name='Макс. интервал (сек)'
    )
    min_message_length = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        verbose_name='Мин. длина сообщения'
    )
    max_message_length = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        verbose_name='Макс. длина сообщения'
    )
    
    # Для Celery periodic task
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, verbose_name='ID задачи Celery')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        db_table = 'message_schedules'
        verbose_name = 'Расписание сообщений'
        verbose_name_plural = 'Расписания сообщений'
        ordering = ['scheduled_time']
    
    def __str__(self):
        return f"{self.chat_config.chat_name} - {self.get_frequency_display()} в {self.scheduled_time}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.min_messages > self.max_messages:
            raise ValidationError('Минимальное количество сообщений не может быть больше максимального')
        if self.min_interval_seconds > self.max_interval_seconds:
            raise ValidationError('Минимальный интервал не может быть больше максимального')
        if self.min_message_length > self.max_message_length:
            raise ValidationError('Минимальная длина не может быть больше максимальной')


class MessageLog(models.Model):
    """Логи отправленных сообщений"""
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
        ('pending', 'В ожидании'),
    ]
    
    session = models.ForeignKey(MaxSession, on_delete=models.CASCADE, related_name='message_logs')
    chat_config = models.ForeignKey(ChatConfig, on_delete=models.CASCADE, related_name='message_logs')
    message_text = models.TextField(verbose_name='Текст сообщения')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='Статус')
    error_message = models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')
    response_data = models.JSONField(blank=True, null=True, verbose_name='Данные ответа')
    
    class Meta:
        db_table = 'message_logs'
        verbose_name = 'Лог сообщения'
        verbose_name_plural = 'Логи сообщений'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['sent_at']),
            models.Index(fields=['status']),
            models.Index(fields=['session', 'sent_at']),
        ]
    
    def __str__(self):
        return f"{self.chat_config.chat_name} - {self.get_status_display()} - {self.sent_at.strftime('%Y-%m-%d %H:%M:%S')}"


class DailyStatistics(models.Model):
    """Ежедневная статистика отправки сообщений"""
    session = models.ForeignKey(MaxSession, on_delete=models.CASCADE, related_name='daily_statistics')
    date = models.DateField(verbose_name='Дата')
    total_messages = models.IntegerField(default=0, verbose_name='Всего сообщений')
    successful_messages = models.IntegerField(default=0, verbose_name='Успешных')
    failed_messages = models.IntegerField(default=0, verbose_name='Неудачных')
    
    class Meta:
        db_table = 'daily_statistics'
        verbose_name = 'Дневная статистика'
        verbose_name_plural = 'Дневная статистика'
        unique_together = ['session', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['session', 'date']),
        ]
    
    def __str__(self):
        return f"{self.session.device_id} - {self.date} - {self.successful_messages}/{self.total_messages}"
    
    @property
    def success_rate(self):
        """Процент успешных отправок"""
        if self.total_messages == 0:
            return 0
        return round((self.successful_messages / self.total_messages) * 100, 2)
