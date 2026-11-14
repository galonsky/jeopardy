from django.urls import path

from ws.consumers import JobEventsConsumer

websocket_urlpatterns = [path("ws/jobs/", JobEventsConsumer.as_asgi())]
