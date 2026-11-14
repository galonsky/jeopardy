from asgiref.sync import async_to_sync
from core.enums import JobKind
from core.models import BackgroundJob
from django.contrib import admin, messages

from classification.models import Classification, Subject, Subtopic


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = ["clue", "primary_subject", "primary_subtopic", "confidence", "version", "is_manual"]
    list_filter = ["version", "is_manual", "primary_subject"]
    search_fields = ["clue__clue_text", "clue__original_category", "clue__correct_response"]
    actions = ["reclassify_selected"]

    @admin.action(description="Reclassify selected clues with their current taxonomy version")
    def reclassify_selected(self, request, queryset):
        from core.tasks import run_classification_job

        versions = queryset.values_list("version", flat=True).distinct()
        queued = 0
        for version in versions:
            clue_ids = [str(clue_id) for clue_id in queryset.filter(version=version).values_list("clue_id", flat=True)]
            job = BackgroundJob.objects.create(
                kind=JobKind.CLASSIFICATION,
                version=version,
                config={"clue_ids": clue_ids, "reprocess": True, "concurrency": 2, "limit": 0},
            )
            async_to_sync(run_classification_job.kiq)(str(job.pk))
            queued += len(clue_ids)
        self.message_user(request, f"Queued {queued} selected clue(s) for reclassification.", messages.SUCCESS)


admin.site.register(Subject)
admin.site.register(Subtopic)
