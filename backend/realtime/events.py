from channels.layers import get_channel_layer


async def broadcast_job_event(payload: dict) -> None:
    layer = get_channel_layer()
    await layer.group_send("jeopardy.jobs", {"type": "job.event", "payload": payload})
