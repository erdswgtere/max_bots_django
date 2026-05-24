from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from asgiref.sync import async_to_sync

from .models import MaxSession, ChatConfig, MessageSchedule, MessageLog, DailyStatistics
from .serializers import (
    MaxSessionSerializer, 
    ChatConfigSerializer, 
    MessageScheduleSerializer, 
    MessageLogSerializer, 
    DailyStatisticsSerializer
)
from .tasks import send_scheduled_messages, test_session_connection
from .services import MaxClientService

class MaxSessionViewSet(viewsets.ModelViewSet):
    queryset = MaxSession.objects.all()
    serializer_class = MaxSessionSerializer

    @decorators.action(detail=True, methods=['post'])
    def start_qr_auth(self, request, pk=None):
        """
        Начало авторизации по QR коду.
        Запускает фоновую задачу Celery и ожидает появления QR-ссылки.
        """
        import time
        from django.core.cache import cache
        from .tasks import run_qr_auth_flow
        
        session = self.get_object()
        
        try:
            # Запускаем Celery задачу
            run_qr_auth_flow.apply_async(args=[session.id], queue='default')
            
            # Ждем появления данных QR кода в кэше (до 5 секунд)
            cache_key = f"qr_auth_data_{session.id}"
            payload = None
            for _ in range(50):
                payload = cache.get(cache_key)
                if payload:
                    break
                time.sleep(0.1)
                
            if payload:
                return Response({
                    'qrLink': payload.get('qrLink'),
                    'trackId': payload.get('trackId'),
                    'expiresAt': payload.get('expiresAt'),
                    'pollingInterval': payload.get('pollingInterval', 5000)
                })
            else:
                return Response({'error': 'Timeout waiting for QR code from Celery worker'}, status=status.HTTP_408_REQUEST_TIMEOUT)
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'])
    def check_qr(self, request, pk=None):
        """
        Проверка статуса QR авторизации.
        Читает статус напрямую из кэша, обновляемого фоновой задачей.
        """
        from django.core.cache import cache
        session = self.get_object()
        track_id = request.data.get('trackId')
        
        if not track_id:
            return Response({'error': 'trackId is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            status_data = cache.get(f"qr_auth_status_{session.id}")
            if status_data:
                return Response(status_data)
            else:
                return Response({'status': 'error', 'message': 'Session expired or not found'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['get'])
    def test_connection(self, request, pk=None):
        """Проверка соединения"""
        test_session_connection.delay(pk)
        return Response({'message': 'Connection test started in background'})

class ChatConfigViewSet(viewsets.ModelViewSet):
    queryset = ChatConfig.objects.all()
    serializer_class = ChatConfigSerializer

class MessageScheduleViewSet(viewsets.ModelViewSet):
    queryset = MessageSchedule.objects.all()
    serializer_class = MessageScheduleSerializer

    @decorators.action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Ручной запуск расписания"""
        send_scheduled_messages.delay(pk)
        return Response({'message': 'Schedule started manually'})

class MessageLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MessageLog.objects.all()
    serializer_class = MessageLogSerializer
    filterset_fields = ['session', 'status', 'chat_config']

class StatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyStatistics.objects.all()
    serializer_class = DailyStatisticsSerializer

    @decorators.action(detail=False, methods=['get'])
    def weekly(self, request):
        """Статистика за последнюю неделю"""
        week_ago = timezone.now().date() - timedelta(days=7)
        stats = DailyStatistics.objects.filter(date__gte=week_ago).values('date').annotate(
            total=Sum('total_messages'),
            successful=Sum('successful_messages'),
            failed=Sum('failed_messages')
        ).order_by('date')
        return Response(stats)
