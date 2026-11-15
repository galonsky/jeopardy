#!/usr/bin/env python3
"""Write local Codex classifications as JSON Lines for transfer to the cluster."""

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

from classification.models import Classification  # noqa: E402


def main() -> None:
    rows = (
        Classification.objects.filter(version="v1", model_name="codex-cli:gpt-6-luna")
        .select_related("clue", "primary_subject", "primary_subtopic")
        .order_by("clue__source_id")
        .iterator(chunk_size=1000)
    )
    for item in rows:
        print(
            json.dumps(
                {
                    "source_id": item.clue.source_id,
                    "fingerprint": item.clue.content_fingerprint,
                    "version": item.version,
                    "subject_slug": item.primary_subject.slug,
                    "subtopic_slug": item.primary_subtopic.slug,
                    "secondary": item.secondary,
                    "mechanics": item.mechanics,
                    "entities": item.entities,
                    "confidence": item.confidence,
                    "model_name": item.model_name,
                    "prompt_version": item.prompt_version,
                    "input_hash": item.input_hash,
                    "is_manual": item.is_manual,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
