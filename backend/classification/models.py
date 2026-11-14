from clues.models import SourceClue
from django.db import models

from classification.enums import PromptVersion, TaxonomyVersion


class Subject(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100, unique=True)
    taxonomy_version = models.CharField(max_length=40, default=TaxonomyVersion.V1)
    sort_order = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return self.name


class Subtopic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="subtopics")
    slug = models.SlugField()
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["subject", "slug"], name="unique_subtopic_per_subject")]

    def __str__(self) -> str:
        return f"{self.subject}: {self.name}"


class Classification(models.Model):
    clue = models.ForeignKey(SourceClue, on_delete=models.CASCADE, related_name="classifications")
    version = models.CharField(max_length=64, default=TaxonomyVersion.V1)
    primary_subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="primary_classifications")
    primary_subtopic = models.ForeignKey(Subtopic, on_delete=models.PROTECT, related_name="primary_classifications")
    secondary = models.JSONField(default=list)
    mechanics = models.JSONField(default=list)
    entities = models.JSONField(default=list)
    confidence = models.FloatField(default=0.5)
    model_name = models.CharField(max_length=120, blank=True)
    prompt_version = models.CharField(max_length=40, choices=PromptVersion.choices, default=PromptVersion.V2)
    input_hash = models.CharField(max_length=64, blank=True)
    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clue", "version"], name="unique_clue_classification_version"),
            models.CheckConstraint(
                condition=models.Q(confidence__gte=0, confidence__lte=1), name="classification_confidence_0_to_1"
            ),
            models.CheckConstraint(
                condition=models.Q(prompt_version__in=PromptVersion.values),
                name="classification_prompt_version_supported",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.primary_subtopic_id and self.primary_subject_id:
            if self.primary_subtopic.subject_id != self.primary_subject_id:
                raise ValidationError({"primary_subtopic": "The subtopic must belong to the selected primary subject."})
