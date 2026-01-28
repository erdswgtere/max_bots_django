from rest_framework import serializers
from .models import MaxSession, ChatConfig, MessageSchedule, MessageLog, DailyStatistics

class MaxSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaxSession
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class ChatConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatConfig
        fields = '__all__'
        read_only_fields = ('created_at',)

class MessageScheduleSerializer(serializers.ModelSerializer):
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    
    class Meta:
        model = MessageSchedule
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'celery_task_id')

class MessageLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = MessageLog
        fields = '__all__'
        read_only_fields = ('sent_at',)

class DailyStatisticsSerializer(serializers.ModelSerializer):
    success_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        model = DailyStatistics
        fields = '__all__'
        read_only_fields = ('date',)
