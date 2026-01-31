from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum

from .models import MaxSession, ChatConfig, MessageSchedule, MessageLog, DailyStatistics
from .serializers import (
    MaxSessionSerializer, 
    ChatConfigSerializer, 
    MessageScheduleSerializer, 
    MessageLogSerializer, 
    DailyStatisticsSerializer
)
from .tasks import send_scheduled_messages, test_session_connection
from .services import MaxClientService, run_async

class MaxSessionViewSet(viewsets.ModelViewSet):
    queryset = MaxSession.objects.all()
    serializer_class = MaxSessionSerializer

    @decorators.action(detail=True, methods=['post'])
    def start_qr_auth(self, request, pk=None):
        """
        Начало авторизации по QR коду.
        Возвращает ссылку на QR код и trackId для проверки.
        """
        session = self.get_object()
        service = MaxClientService(session)
        try:
            payload = run_async(service.start_qr_auth())
            return Response({
                'qrLink': payload['qrLink'],
                'trackId': payload['trackId'],
                'expiresAt': payload['expiresAt'],
                'pollingInterval': payload['pollingInterval']
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'])
    def check_qr(self, request, pk=None):
        """
        Проверка статуса QR авторизации.
        Принимает trackId. Если авторизация успешна, сохраняет токен.
        """
        session = self.get_object()
        track_id = request.data.get('trackId')
        
        if not track_id:
            return Response({'error': 'trackId is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        service = MaxClientService(session)
        try:
            result = run_async(service.check_qr_auth_status(track_id))
            return Response(result)
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
