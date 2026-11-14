import os

from django.db import close_old_connections
from taskiq import TaskiqMiddleware, TaskiqScheduler
from taskiq.middlewares import SmartRetryMiddleware
from taskiq.middlewares.opentelemetry_middleware import OpenTelemetryMiddleware
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")


class DjangoConnectionMiddleware(TaskiqMiddleware):
    async def pre_execute(self, message):
        from asgiref.sync import sync_to_async

        await sync_to_async(close_old_connections, thread_sensitive=True)()
        return message

    async def post_execute(self, message, result):
        from asgiref.sync import sync_to_async

        await sync_to_async(close_old_connections, thread_sensitive=True)()


class DeadLetterMiddleware(TaskiqMiddleware):
    async def on_error(self, message, result, exception):
        from asgiref.sync import sync_to_async

        from core.models import FailedTask

        await sync_to_async(FailedTask.objects.create, thread_sensitive=True)(
            task_name=message.task_name,
            payload={"task_id": message.task_id, "args": message.args, "kwargs": message.kwargs},
            error=f"{type(exception).__name__}: {exception}",
        )


redis_url = os.getenv("TASKIQ_REDIS_URL", "redis://localhost:6379")
redis_db_base = int(os.getenv("REDIS_DB_BASE", "0"))
broker = RedisStreamBroker(
    url=redis_url, db=redis_db_base + 2, queue_name="jeopardy", consumer_group_name="jeopardy-workers"
)
broker.with_middlewares(
    OpenTelemetryMiddleware(),
    DjangoConnectionMiddleware(),
    SmartRetryMiddleware(default_retry_count=3, default_delay=2, use_jitter=True, use_delay_exponent=True),
    DeadLetterMiddleware(),
)
scheduler = TaskiqScheduler(broker, [LabelScheduleSource(broker)])
