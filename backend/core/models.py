from classification.enums import TaxonomyVersion
from django.db import models

from core.enums import JobKind, JobStatus


class FailedTask(models.Model):
    task_name = models.CharField(max_length=200)
    payload = models.JSONField(default=dict)
    error = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class BackgroundJob(models.Model):
    Status = JobStatus

    kind = models.CharField(max_length=40, choices=JobKind.choices, default=JobKind.CLASSIFICATION)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    version = models.CharField(max_length=64, default=TaxonomyVersion.V1)
    config = models.JSONField(default=dict)
    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=JobStatus.values), name="background_job_status_is_supported"
            ),
            models.CheckConstraint(condition=models.Q(kind__in=JobKind.values), name="background_job_kind_supported"),
        ]
