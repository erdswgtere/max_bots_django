from django.apps import AppConfig


class MaxSessionsConfig(AppConfig):
    name = "max_sessions"
    verbose_name = "Сессии и сообщения"

    def ready(self):
        import max_sessions.signals
