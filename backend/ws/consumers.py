from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings


class JobEventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if settings.TSIDP_ISSUER and not self.scope["user"].is_authenticated:
            await self.close(code=4003)
            return
        self.group_name = "jeopardy.jobs"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def job_event(self, event):
        await self.send_json(event["payload"])
