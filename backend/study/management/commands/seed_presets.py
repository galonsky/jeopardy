from django.core.management.base import BaseCommand

from study.enums import SessionMode
from study.models import PracticePreset

DEFAULT_ANYTIME_NAME = "Anytime Test Prep approximation"
DEFAULT_ANYTIME_CONFIG = {
    "count": 50,
    "min_difficulty": 1,
    "max_difficulty": 5,
    "difficulty_weights": {"1": 10, "2": 25, "3": 35, "4": 25, "5": 5},
    "include_double": True,
    "include_daily_doubles": False,
    "include_final": False,
    "include_media_required": False,
    "min_date": None,
    "max_date": None,
    "subject_ids": [],
    "subtopic_ids": [],
}


class Command(BaseCommand):
    help = "Create the default, approximate Anytime Test Prep preset if it is missing."

    def handle(self, *args, **options):
        _, created = PracticePreset.objects.get_or_create(
            name=DEFAULT_ANYTIME_NAME,
            mode=SessionMode.ANYTIME,
            defaults={"config": DEFAULT_ANYTIME_CONFIG, "is_default": True},
        )
        self.stdout.write(
            self.style.SUCCESS("Created default Anytime preset." if created else "Default preset exists.")
        )
