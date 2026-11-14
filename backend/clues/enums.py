from django.db import models


class Round(models.TextChoices):
    JEOPARDY = "jeopardy", "Jeopardy!"
    DOUBLE_JEOPARDY = "double", "Double Jeopardy!"
    FINAL_JEOPARDY = "final", "Final Jeopardy!"
    OTHER = "other", "Other"


class MediaStatus(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    UNNECESSARY = "unnecessary", "Not required"
    REQUIRED = "required", "Required"
