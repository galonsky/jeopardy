import json
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Write the Django Ninja schema to a file for offline client generation."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="frontend/openapi.json")

    def handle(self, *args, **options):
        from config.api import api

        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(api.get_openapi_schema(), indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {output}"))
