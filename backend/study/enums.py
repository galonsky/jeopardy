from django.db import models


class SessionMode(models.TextChoices):
    ANYTIME = "anytime", "Anytime Test Prep"
    GENERAL = "general", "General Practice"
    WEAK_AREAS = "weak_areas", "Weak Areas"
    REVIEW = "review", "Review Mistakes"


class SessionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    ABANDONED = "abandoned", "Abandoned"


class TimerDuration(models.IntegerChoices):
    FIFTEEN = 15, "15 seconds"
    THIRTY = 30, "30 seconds"
    SIXTY = 60, "60 seconds"


class AttemptGrade(models.TextChoices):
    CORRECT = "correct", "Correct"
    PARTIAL = "partial", "Partially correct"
    INCORRECT = "incorrect", "Incorrect"
    UNCERTAIN = "uncertain", "Needs review"
    UNANSWERED = "unanswered", "Unanswered"


class RecallRating(models.TextChoices):
    CONFIDENT = "confident", "Confident"
    GUESSED = "guessed", "Guessed"
    DID_NOT_KNOW = "did_not_know", "Didn't know"
