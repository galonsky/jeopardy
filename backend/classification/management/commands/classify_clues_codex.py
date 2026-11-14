from math import ceil

from django.core.management.base import BaseCommand, CommandError

from classification.codex_runner import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    classify_pending_with_codex,
)
from classification.enums import TaxonomyVersion
from classification.pipeline import _taxonomy_snapshot
from clues.models import SourceClue


class Command(BaseCommand):
    help = "Classify local database clues in resumable batches using the Codex CLI."

    def add_arguments(self, parser):
        parser.add_argument("--taxonomy-version", dest="version", default=TaxonomyVersion.V1)
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help="Clues per Codex call; lower this to reduce usage-budget overshoot.",
        )
        parser.add_argument("--limit", type=int, default=0, help="Maximum clues to process; 0 means all pending clues.")
        parser.add_argument("--clue-id", action="append", default=[])
        parser.add_argument("--reprocess", action="store_true")
        parser.add_argument("--model", default=DEFAULT_CODEX_MODEL)
        parser.add_argument(
            "--reasoning-effort",
            choices=["low", "medium", "high", "xhigh"],
            default=DEFAULT_REASONING_EFFORT,
        )
        parser.add_argument("--timeout", type=int, default=1800, help="Timeout for each Codex batch, in seconds.")
        parser.add_argument(
            "--max-usage-tokens",
            type=int,
            default=0,
            help="Local stop after this many reported input+output tokens; 0 means no token cap.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show the pending count and estimated Codex calls.")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")
        if options["limit"] < 0:
            raise CommandError("--limit cannot be negative.")
        if options["max_usage_tokens"] < 0:
            raise CommandError("--max-usage-tokens cannot be negative.")

        taxonomy, _ = _taxonomy_snapshot(options["version"])
        if not taxonomy:
            raise CommandError(f"No taxonomy exists for classification version {options['version']}.")

        pending = SourceClue.objects.all()
        if options["clue_id"]:
            pending = pending.filter(pk__in=options["clue_id"])
        if not options["reprocess"]:
            pending = pending.exclude(classifications__version=options["version"])
        if options["limit"]:
            pending = pending.order_by("pk")[: options["limit"]]
        count = pending.count()

        self.stdout.write(
            f"Pending clues: {count:,}; estimated batches: {ceil(count / batch_size) if count else 0}; "
            f"model: {options['model']} ({options['reasoning_effort']} reasoning)."
        )
        if options["max_usage_tokens"]:
            self.stdout.write(f"Local token budget: {options['max_usage_tokens']:,} input+output tokens.")
        if options["dry_run"] or not count:
            return

        def report(batches: int, processed: int, failed: int, total: int, usage_tokens: int) -> None:
            self.stdout.write(
                f"Batches: {batches}; classified: {processed:,}/{total:,}; failed: {failed:,}; "
                f"reported input+output tokens: {usage_tokens:,}.",
                ending="\r",
            )
            self.stdout.flush()

        try:
            summary = classify_pending_with_codex(
                version=options["version"],
                batch_size=batch_size,
                limit=options["limit"],
                clue_ids=options["clue_id"] or None,
                reprocess=options["reprocess"],
                model=options["model"],
                reasoning_effort=options["reasoning_effort"],
                timeout=options["timeout"],
                max_usage_tokens=options["max_usage_tokens"],
                progress_callback=report,
            )
        except ValueError as error:
            raise CommandError(str(error)) from error

        self.stdout.write("")
        usage = f"{summary.usage_tokens:,}" if summary.usage_known else f">={summary.usage_tokens:,} (some usage unavailable)"
        self.stdout.write(
            f"Classified {summary.processed:,}; failed {summary.failed:,}; batches {summary.batches:,}; "
            f"reported input+output tokens {usage}."
        )
        if summary.stopped_for_budget:
            if summary.usage_known:
                self.stdout.write("Stopped at the local token budget; remaining clues stay pending for the next run.")
            else:
                self.stdout.write(
                    "Stopped because Codex usage could not be measured under the local budget; "
                    "remaining clues stay pending for the next run."
                )
        if summary.last_error:
            self.stderr.write(f"Last Codex error: {summary.last_error}")
        if summary.failed_ids:
            shown_ids = ", ".join(summary.failed_ids[:10])
            suffix = f" (+{len(summary.failed_ids) - 10} more)" if len(summary.failed_ids) > 10 else ""
            self.stderr.write(f"Failed clue IDs: {shown_ids}{suffix}")
        if summary.failed:
            raise CommandError(f"{summary.failed:,} clues failed and remain available to retry.")
