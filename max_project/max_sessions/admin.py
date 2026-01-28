"""
Django admin configuration for max_sessions app.
Provides user-friendly interface for managing sessions, schedules, and viewing statistics.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from datetime import date, timedelta

from .models import (
    MaxSession,
    ChatConfig,
    MessageSchedule,
    MessageLog,
    DailyStatistics
)
from .tasks import send_scheduled_messages, test_session_connection


@admin.register(MaxSession)
class MaxSessionAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'user', 'is_active', 'created_at', 'chats_count', 'success_rate_today', 'action_buttons']
    list_filter = ['is_active', 'created_at']
    search_fields = ['phone_number', 'user__username']
    readonly_fields = ['device_id', 'created_at', 'updated_at', 'user_agent_display']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'phone_number', 'is_active')
        }),
        ('Технические данные', {
            'fields': ('auth_token', 'device_id', 'user_agent_display'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_sessions', 'deactivate_sessions', 'test_connections']
    
    def user_agent_display(self, obj):
        """Красивое отображение user_agent_data"""
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.user_agent_data, indent=2, ensure_ascii=False))
    user_agent_display.short_description = 'User Agent'
    
    def chats_count(self, obj):
        """Количество подключенных чатов"""
        return obj.chats.filter(is_active=True).count()
    chats_count.short_description = 'Активных чатов'
    
    def success_rate_today(self, obj):
        """Процент успешных отправок сегодня"""
        today = date.today()
        stats = DailyStatistics.objects.filter(session=obj, date=today).first()
        if stats and stats.total_messages > 0:
            rate = stats.success_rate
            color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
            return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)
        return '-'
    success_rate_today.short_description = 'Успешность сегодня'
    
    def action_buttons(self, obj):
        """Кнопки действий"""
        return format_html(
            '<a class="button" href="{}">Тест подключения</a>',
            reverse('admin:max_sessions_maxsession_test', args=[obj.pk])
        )
    action_buttons.short_description = 'Действия'
    
    def activate_sessions(self, request, queryset):
        """Активировать выбранные сессии"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'Активировано сессий: {count}')
    activate_sessions.short_description = 'Активировать выбранные сессии'
    
    def deactivate_sessions(self, request, queryset):
        """Деактивировать выбранные сессии"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано сессий: {count}')
    deactivate_sessions.short_description = 'Деактивировать выбранные сессии'
    
    def test_connections(self, request, queryset):
        """Тестировать подключения для выбранных сессий"""
        for session in queryset:
            test_session_connection.delay(session.id)
        self.message_user(request, f'Запущены тесты для {queryset.count()} сессий')
    test_connections.short_description = 'Тестировать подключения'


class MessageScheduleInline(admin.TabularInline):
    """Inline для расписаний в ChatConfig"""
    model = MessageSchedule
    extra = 0
    fields = ['frequency', 'scheduled_time', 'is_active', 'min_messages', 'max_messages']
    readonly_fields = []


@admin.register(ChatConfig)
class ChatConfigAdmin(admin.ModelAdmin):
    list_display = ['chat_name', 'chat_id', 'session', 'is_active', 'schedules_count', 'messages_today']
    list_filter = ['is_active', 'session']
    search_fields = ['chat_name', 'chat_id', 'session__phone_number']
    inlines = [MessageScheduleInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('session', 'chat_id', 'chat_name', 'is_active')
        }),
    )
    
    def schedules_count(self, obj):
        """Количество активных расписаний"""
        return obj.schedules.filter(is_active=True).count()
    schedules_count.short_description = 'Активных расписаний'
    
    def messages_today(self, obj):
        """Сообщений отправлено сегодня"""
        today = date.today()
        count = MessageLog.objects.filter(
            chat_config=obj,
            sent_at__date=today,
            status='success'
        ).count()
        return count
    messages_today.short_description = 'Сообщений сегодня'


@admin.register(MessageSchedule)
class MessageScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'chat_config',
        'frequency',
        'scheduled_time',
        'is_active',
        'message_range',
        'interval_range',
        'last_run',
        'run_now_button'
    ]
    list_filter = ['is_active', 'frequency', 'session']
    search_fields = ['chat_config__chat_name', 'session__phone_number']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('session', 'chat_config', 'frequency', 'scheduled_time', 'is_active')
        }),
        ('Параметры сообщений', {
            'fields': (
                ('min_messages', 'max_messages'),
                ('min_interval_seconds', 'max_interval_seconds'),
                ('min_message_length', 'max_message_length')
            )
        }),
        ('Технические данные', {
            'fields': ('celery_task_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['celery_task_id', 'created_at', 'updated_at']
    actions = ['run_schedules_now', 'activate_schedules', 'deactivate_schedules']
    
    def message_range(self, obj):
        """Диапазон количества сообщений"""
        return f"{obj.min_messages}-{obj.max_messages}"
    message_range.short_description = 'Кол-во сообщений'
    
    def interval_range(self, obj):
        """Диапазон интервалов"""
        return f"{obj.min_interval_seconds}-{obj.max_interval_seconds}с"
    interval_range.short_description = 'Интервал'
    
    def last_run(self, obj):
        """Последний запуск"""
        last_log = MessageLog.objects.filter(
            chat_config=obj.chat_config,
            session=obj.session
        ).order_by('-sent_at').first()
        
        if last_log:
            return last_log.sent_at.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    last_run.short_description = 'Последний запуск'
    
    def run_now_button(self, obj):
        """Кнопка запуска сейчас"""
        if obj.is_active:
            return format_html(
                '<button type="button" onclick="location.href=\'{}\'">Запустить сейчас</button>',
                reverse('admin:max_sessions_messageschedule_run', args=[obj.pk])
            )
        return '-'
    run_now_button.short_description = 'Действия'
    
    def run_schedules_now(self, request, queryset):
        """Запустить выбранные расписания немедленно"""
        for schedule in queryset.filter(is_active=True):
            send_scheduled_messages.delay(schedule.id)
        self.message_user(request, f'Запущено расписаний: {queryset.filter(is_active=True).count()}')
    run_schedules_now.short_description = 'Запустить сейчас'
    
    def activate_schedules(self, request, queryset):
        """Активировать выбранные расписания"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'Активировано расписаний: {count}')
    activate_schedules.short_description = 'Активировать'
    
    def deactivate_schedules(self, request, queryset):
        """Деактивировать выбранные расписания"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано расписаний: {count}')
    deactivate_schedules.short_description = 'Деактивировать'


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ['sent_at', 'session', 'chat_config', 'status', 'message_preview', 'error_preview']
    list_filter = ['status', 'sent_at', 'session', 'chat_config']
    search_fields = ['message_text', 'error_message', 'session__phone_number']
    readonly_fields = ['session', 'chat_config', 'message_text', 'status', 'error_message', 'sent_at', 'response_display']
    date_hierarchy = 'sent_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('session', 'chat_config', 'status', 'sent_at')
        }),
        ('Содержимое', {
            'fields': ('message_text', 'error_message')
        }),
        ('Технические данные', {
            'fields': ('response_display',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Запрет на создание логов вручную"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешить удаление только для старых логов"""
        return True
    
    def message_preview(self, obj):
        """Превью сообщения"""
        return obj.message_text[:50] + '...' if len(obj.message_text) > 50 else obj.message_text
    message_preview.short_description = 'Сообщение'
    
    def error_preview(self, obj):
        """Превью ошибки"""
        if obj.error_message:
            error = obj.error_message[:100] + '...' if len(obj.error_message) > 100 else obj.error_message
            return format_html('<span style="color: red;">{}</span>', error)
        return '-'
    error_preview.short_description = 'Ошибка'
    
    def response_display(self, obj):
        """Красивое отображение response_data"""
        if obj.response_data:
            import json
            return format_html('<pre>{}</pre>', json.dumps(obj.response_data, indent=2, ensure_ascii=False))
        return '-'
    response_display.short_description = 'Ответ сервера'


@admin.register(DailyStatistics)
class DailyStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        'date',
        'session',
        'total_messages',
        'successful_messages',
        'failed_messages',
        'success_rate_display'
    ]
    list_filter = ['date', 'session']
    search_fields = ['session__phone_number']
    readonly_fields = ['session', 'date', 'total_messages', 'successful_messages', 'failed_messages', 'success_rate_display']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('session', 'date')
        }),
        ('Статистика', {
            'fields': ('total_messages', 'successful_messages', 'failed_messages', 'success_rate_display')
        }),
    )
    
    def has_add_permission(self, request):
        """Запрет на создание статистики вручную"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешить удаление только для старой статистики"""
        return True
    
    def success_rate_display(self, obj):
        """Процент успешных отправок с цветом"""
        rate = obj.success_rate
        if rate >= 90:
            color = 'green'
        elif rate >= 70:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<strong style="color: {};">{:.1f}%</strong>', color, rate)
    success_rate_display.short_description = 'Успешность'
    
    def changelist_view(self, request, extra_context=None):
        """Добавление сводной информации"""
        extra_context = extra_context or {}
        
        # Статистика за последние 7 дней
        week_ago = date.today() - timedelta(days=7)
        week_stats = DailyStatistics.objects.filter(date__gte=week_ago).aggregate(
            total=Sum('total_messages'),
            successful=Sum('successful_messages'),
            failed=Sum('failed_messages')
        )
        
        extra_context['week_stats'] = week_stats
        
        return super().changelist_view(request, extra_context=extra_context)
