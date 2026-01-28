from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sessions', views.MaxSessionViewSet)
router.register(r'chats', views.ChatConfigViewSet)
router.register(r'schedules', views.MessageScheduleViewSet)
router.register(r'logs', views.MessageLogViewSet)
router.register(r'statistics', views.StatisticsViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
