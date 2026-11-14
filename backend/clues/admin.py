from django.contrib import admin

from clues.models import SourceClue


@admin.register(SourceClue)
class SourceClueAdmin(admin.ModelAdmin):
    list_display = ["original_category", "round", "original_value", "air_date", "is_daily_double"]
    search_fields = ["clue_text", "correct_response", "original_category", "show_number"]
    list_filter = ["round", "is_daily_double", "air_date"]
