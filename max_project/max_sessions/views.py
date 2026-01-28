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
    def authenticate_phone(self, request, pk=None):
        """Начало процесса авторизации (отправка SMS)"""
        session = self.get_object()
        phone = request.data.get('phone_number')
        if not phone:
            return Response({'error': 'phone_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        service = MaxClientService(session)
        try:
            token = run_async(service.authenticate(phone))
            return Response({'token': token, 'message': 'SMS code sent'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'])
    def verify_code(self, request, pk=None):
        """Верификация кода из SMS"""
        session = self.get_object()
        token = request.data.get('token')
        code = request.data.get('code')
        
        if not token or not code:
            return Response({'error': 'token and code are required'}, status=status.HTTP_400_BAD_REQUEST)
            
        service = MaxClientService(session)
        try:
            auth_token = run_async(service.verify_code(token, code))
            return Response({'auth_token': auth_token, 'message': 'Authenticated successfully'})
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
