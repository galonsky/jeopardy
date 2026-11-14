import os
from datetime import UTC, datetime

import django
from asgiref.sync import sync_to_async

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from classification.pipeline import classify_pending  # noqa: E402
from realtime.events import broadcast_job_event  # noqa: E402

from core.models import BackgroundJob  # noqa: E402
from core.taskiq import broker  # noqa: E402


@broker.task(retry_on_error=True, max_retries=3, delay=3)
async def run_classification_job(job_id: str) -> dict[str, int]:
    job = await sync_to_async(BackgroundJob.objects.get, thread_sensitive=True)(pk=job_id)
    job.status = BackgroundJob.Status.RUNNING
    job.started_at = datetime.now(UTC)
    job.completed_at = None
    job.error = ""
    await sync_to_async(job.save, thread_sensitive=True)()
    await broadcast_job_event({"type": "classification.started", "job_id": str(job.pk)})

    def save_progress(processed: int, failed: int, total: int) -> None:
        BackgroundJob.objects.filter(pk=job_id).update(
            processed=job.processed + processed,
            failed=job.failed + failed,
            total=job.total or total,
        )

    try:
        processed, failed = await sync_to_async(classify_pending, thread_sensitive=False)(
            version=job.version,
            concurrency=int(job.config.get("concurrency", 2)),
            limit=int(job.config.get("limit", 0)),
            clue_ids=job.config.get("clue_ids") or None,
            reprocess=bool(job.config.get("reprocess", False)),
            progress_callback=save_progress,
        )
    except Exception as error:
        await sync_to_async(BackgroundJob.objects.filter(pk=job_id).update, thread_sensitive=True)(
            status=BackgroundJob.Status.FAILED,
            error=str(error)[:4000],
            completed_at=datetime.now(UTC),
        )
        await broadcast_job_event({"type": "classification.failed", "job_id": str(job.pk)})
        raise
    job.processed += processed
    job.failed += failed
    job.total = job.total or job.processed + job.failed
    job.status = BackgroundJob.Status.FAILED if failed else BackgroundJob.Status.SUCCEEDED
    job.completed_at = datetime.now(UTC)
    await sync_to_async(job.save, thread_sensitive=True)()
    await broadcast_job_event(
        {
            "type": "classification.completed" if not failed else "classification.failed",
            "job_id": str(job.pk),
            "processed": processed,
            "failed": failed,
        }
    )
    return {"processed": processed, "failed": failed}
