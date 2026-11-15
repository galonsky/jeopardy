#!/usr/bin/env python3
"""Classify local pending clues, splitting failed batches so one clue cannot block later rows."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"

import django  # noqa: E402

django.setup()

from classification.codex_runner import (  # noqa: E402
    DEFAULT_CODEX_MODEL,
    DEFAULT_REASONING_EFFORT,
    classify_pending_with_codex,
)
from classification.models import Classification  # noqa: E402
from clues.models import SourceClue  # noqa: E402

BATCH_SIZE = 500
TIMEOUT_SECONDS = 3600
MAX_SINGLETON_ATTEMPTS = 2
MAX_CONSECUTIVE_SINGLETON_FAILURES = 20

classified_this_run = 0
reported_tokens = 0
usage_known = True
codex_calls = 0
failed_singletons: list[str] = []
consecutive_singleton_failures = 0
stop_for_repeated_failure = False


def classify_ids(ids: list[str], singleton_attempt: int = 1) -> None:
    global classified_this_run, reported_tokens, usage_known, codex_calls
    global consecutive_singleton_failures, stop_for_repeated_failure

    if not ids or stop_for_repeated_failure:
        return

    codex_calls += 1
    summary = classify_pending_with_codex(
        version="v1",
        batch_size=len(ids),
        clue_ids=ids,
        model=DEFAULT_CODEX_MODEL,
        reasoning_effort=DEFAULT_REASONING_EFFORT,
        timeout=TIMEOUT_SECONDS,
    )
    classified_this_run += summary.processed
    reported_tokens += summary.usage_tokens
    usage_known = usage_known and summary.usage_known
    failed = list(dict.fromkeys(str(clue_id) for clue_id in summary.failed_ids))

    if not failed:
        if summary.processed:
            consecutive_singleton_failures = 0
        return

    if len(ids) == 1:
        if singleton_attempt < MAX_SINGLETON_ATTEMPTS:
            classify_ids(ids, singleton_attempt + 1)
            return

        failed_singletons.append(ids[0])
        consecutive_singleton_failures += 1
        if consecutive_singleton_failures >= MAX_CONSECUTIVE_SINGLETON_FAILURES:
            stop_for_repeated_failure = True
        return

    if summary.processed or len(failed) < len(ids):
        classify_ids(failed)
        return

    midpoint = len(ids) // 2
    classify_ids(ids[:midpoint])
    classify_ids(ids[midpoint:])


def main() -> int:
    pending_ids = [
        str(clue_id)
        for clue_id in SourceClue.objects.exclude(classifications__version="v1")
        .order_by("pk")
        .values_list("pk", flat=True)
    ]
    before = Classification.objects.filter(version="v1", model_name="codex-cli:gpt-6-luna").count()
    print(json.dumps({"event": "start", "pending": len(pending_ids), "model": DEFAULT_CODEX_MODEL}))

    chunks = [pending_ids[index : index + BATCH_SIZE] for index in range(0, len(pending_ids), BATCH_SIZE)]
    for index, chunk in enumerate(chunks, start=1):
        classify_ids(chunk)
        current = Classification.objects.filter(version="v1", model_name="codex-cli:gpt-6-luna").count()
        pending = SourceClue.objects.exclude(classifications__version="v1").count()
        print(
            json.dumps(
                {
                    "event": "progress",
                    "batch": index,
                    "batches": len(chunks),
                    "classified_this_run": classified_this_run,
                    "local_codex_total": current,
                    "pending": pending,
                    "failed_singletons": len(failed_singletons),
                    "codex_calls": codex_calls,
                    "reported_tokens": reported_tokens,
                }
            ),
            flush=True,
        )
        if stop_for_repeated_failure:
            break

    after = Classification.objects.filter(version="v1", model_name="codex-cli:gpt-6-luna").count()
    pending_after = SourceClue.objects.exclude(classifications__version="v1").count()
    print(
        json.dumps(
            {
                "event": "finish",
                "classified_this_run": classified_this_run,
                "local_codex_total_before": before,
                "local_codex_total_after": after,
                "pending_after": pending_after,
                "failed_singletons": failed_singletons[:20],
                "failed_singleton_count": len(failed_singletons),
                "stopped_for_repeated_failure": stop_for_repeated_failure,
                "codex_calls": codex_calls,
                "reported_tokens": reported_tokens,
                "usage_known": usage_known,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 1 if stop_for_repeated_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
