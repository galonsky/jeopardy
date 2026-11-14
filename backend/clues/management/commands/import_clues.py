from datetime import date

from django.core.management.base import BaseCommand, CommandError

from clues.ingest import import_file


class Command(BaseCommand):
    help = "Import a Jeopardy clue TSV, CSV, or JSON file."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--revision", default="local")
        parser.add_argument("--since", type=date.fromisoformat, help="Import clues aired on or after this date.")

    def handle(self, *args, **options):
        try:
            created, updated = import_file(options["path"], options["revision"], options["since"])
        except OSError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Imported {created} new clues; refreshed {updated} existing clues."))
