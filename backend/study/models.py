import uuid

from clues.models import SourceClue
from django.db import models
from django.utils import timezone

from study.enums import AttemptGrade, RecallRating, SessionMode, SessionStatus


class StudySession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.CharField(max_length=20, choices=SessionMode.choices)
    seed = models.PositiveBigIntegerField()
    config = models.JSONField(default=dict)
    clue_ids = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=SessionStatus.choices, default=SessionStatus.ACTIVE)
    current_index = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(mode__in=SessionMode.values), name="session_mode_is_supported"),
            models.CheckConstraint(
                condition=models.Q(status__in=SessionStatus.values), name="session_status_is_supported"
            ),
        ]


class Attempt(models.Model):
    session = models.ForeignKey(StudySession, on_delete=models.CASCADE, related_name="attempts")
    position = models.PositiveSmallIntegerField()
    clue = models.ForeignKey(SourceClue, on_delete=models.PROTECT)
    typed_response = models.TextField(blank=True)
    correctness = models.CharField(max_length=12, choices=AttemptGrade.choices, default=AttemptGrade.UNANSWERED)
    automatic_correctness = models.CharField(
        max_length=12, choices=AttemptGrade.choices, default=AttemptGrade.UNANSWERED
    )
    recall_rating = models.CharField(max_length=20, choices=RecallRating.choices, null=True, blank=True)
    canonical_snapshot = models.TextField()
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    is_first_seen = models.BooleanField(default=True)
    revealed_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "position"], name="unique_attempt_position"),
            models.CheckConstraint(
                condition=models.Q(correctness__in=AttemptGrade.values), name="attempt_grade_is_supported"
            ),
            models.CheckConstraint(
                condition=models.Q(automatic_correctness__in=AttemptGrade.values),
                name="attempt_auto_grade_is_supported",
            ),
            models.CheckConstraint(
                condition=models.Q(recall_rating__isnull=True) | models.Q(recall_rating__in=RecallRating.values),
                name="attempt_recall_rating_is_supported",
            ),
        ]


class ReviewState(models.Model):
    clue = models.OneToOneField(SourceClue, on_delete=models.CASCADE, related_name="review_state")
    due_at = models.DateTimeField(db_index=True)
    interval_days = models.PositiveSmallIntegerField(default=1)
    repetitions = models.PositiveSmallIntegerField(default=0)


class PracticePreset(models.Model):
    name = models.CharField(max_length=100)
    mode = models.CharField(max_length=20, choices=SessionMode.choices)
    config = models.JSONField(default=dict)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name", "mode"], name="unique_preset_name_per_mode"),
            models.CheckConstraint(condition=models.Q(mode__in=SessionMode.values), name="preset_mode_is_supported"),
        ]
