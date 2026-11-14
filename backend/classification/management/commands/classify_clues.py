from django.core.management.base import BaseCommand, CommandError

from classification.enums import TaxonomyVersion
from classification.pipeline import classify_pending


class Command(BaseCommand):
    help = "Classify unclassified clues using a configured OpenAI-compatible API."

    def add_arguments(self, parser):
        parser.add_argument("--version", default=TaxonomyVersion.V1)
        parser.add_argument("--concurrency", type=int, default=2)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--clue-id", action="append", default=[])
        parser.add_argument("--reprocess", action="store_true")

    def handle(self, *args, **options):
        import os

        if not os.getenv("CLASSIFICATION_MODEL") or not os.getenv("OPENAI_API_KEY"):
            raise CommandError("Set CLASSIFICATION_MODEL and OPENAI_API_KEY first.")
        success, failed = classify_pending(
            version=options["version"],
            concurrency=options["concurrency"],
            limit=options["limit"],
            clue_ids=options["clue_id"] or None,
            reprocess=options["reprocess"],
        )
        self.stdout.write(f"Classified {success}; failed {failed}.")
