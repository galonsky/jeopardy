import uuid

from django.db import models

from clues.enums import MediaStatus, Round


class SourceClue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_id = models.CharField(max_length=300, unique=True)
    source_url = models.URLField(blank=True)
    content_fingerprint = models.CharField(max_length=64, db_index=True)
    clue_text = models.TextField()
    correct_response = models.TextField()
    original_category = models.CharField(max_length=300, db_index=True)
    category_comments = models.TextField(blank=True)
    show_number = models.CharField(max_length=50, blank=True)
    air_date = models.DateField(null=True, blank=True, db_index=True)
    round = models.CharField(max_length=12, choices=Round.choices, default=Round.OTHER)
    original_value = models.PositiveIntegerField(null=True, blank=True)
    board_row = models.PositiveSmallIntegerField(null=True, blank=True)
    is_daily_double = models.BooleanField(default=False)
    media_status = models.CharField(max_length=20, choices=MediaStatus.choices, default=MediaStatus.UNKNOWN)
    media_required = models.BooleanField(default=False)
    original_payload = models.JSONField(default=dict)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(board_row__isnull=True) | models.Q(board_row__gte=1, board_row__lte=5),
                name="clue_board_row_1_to_5",
            ),
            models.CheckConstraint(condition=models.Q(round__in=Round.values), name="clue_round_is_supported"),
            models.CheckConstraint(
                condition=models.Q(media_status__in=MediaStatus.values), name="clue_media_status_is_supported"
            ),
        ]
        indexes = [models.Index(fields=["round", "board_row"]), models.Index(fields=["air_date", "round"])]

    def __str__(self) -> str:
        return f"{self.original_category}: {self.clue_text[:70]}"
