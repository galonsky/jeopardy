#!/usr/bin/env python3
"""Import JSON Lines from stdin into this pod's Django database, preserving existing rows."""

from __future__ import annotations

import json
import sys

import django

django.setup()

from classification.models import Classification, Subject, Subtopic  # noqa: E402
from clues.models import SourceClue  # noqa: E402
from django.db import transaction  # noqa: E402


def main() -> None:
    rows = [json.loads(line) for line in sys.stdin if line.strip()]
    if len({row["source_id"] for row in rows}) != len(rows):
        raise SystemExit("Export contains duplicate source_id values; refusing import.")

    clue_map = {
        source_id: (clue_id, fingerprint)
        for source_id, clue_id, fingerprint in SourceClue.objects.values_list(
            "source_id", "id", "content_fingerprint"
        ).iterator(chunk_size=2000)
    }
    subject_map = {
        slug: subject_id
        for slug, subject_id in Subject.objects.filter(taxonomy_version="v1").values_list("slug", "id")
    }
    subtopic_map = {
        (subject_slug, topic_slug): (topic_id, subject_id)
        for subject_slug, topic_slug, topic_id, subject_id in Subtopic.objects.values_list(
            "subject__slug", "slug", "id", "subject_id"
        )
    }
    existing_ids = set(Classification.objects.filter(version="v1").values_list("clue_id", flat=True))

    objects = []
    missing_clues = 0
    existing = 0
    mismatches = []
    for row in rows:
        if row.get("version") != "v1":
            mismatches.append(f"unsupported taxonomy version for {row['source_id']}")
            continue
        clue = clue_map.get(row["source_id"])
        if clue is None:
            missing_clues += 1
            continue
        clue_id, fingerprint = clue
        if fingerprint != row["fingerprint"]:
            mismatches.append(f"fingerprint mismatch for {row['source_id']}")
            continue
        subject_id = subject_map.get(row["subject_slug"])
        topic = subtopic_map.get((row["subject_slug"], row["subtopic_slug"]))
        if subject_id is None or topic is None or topic[1] != subject_id:
            mismatches.append(f"taxonomy mismatch for {row['source_id']}")
            continue
        if clue_id in existing_ids:
            existing += 1
            continue
        objects.append(
            Classification(
                clue_id=clue_id,
                version=row["version"],
                primary_subject_id=subject_id,
                primary_subtopic_id=topic[0],
                secondary=row["secondary"],
                mechanics=row["mechanics"],
                entities=row["entities"],
                confidence=row["confidence"],
                model_name=row["model_name"],
                prompt_version=row["prompt_version"],
                input_hash=row["input_hash"],
                is_manual=row["is_manual"],
            )
        )

    if mismatches:
        raise SystemExit("Import validation failed: " + "; ".join(mismatches[:10]))

    before = Classification.objects.filter(version="v1", model_name="codex-cli:gpt-6-luna").count()
    with transaction.atomic():
        Classification.objects.bulk_create(objects, batch_size=500, ignore_conflicts=True)
    after = Classification.objects.filter(version="v1", model_name="codex-cli:gpt-6-luna").count()
    print(
        json.dumps(
            {
                "export_rows": len(rows),
                "imported": after - before,
                "already_classified": existing,
                "missing_hosted_clues": missing_clues,
                "hosted_codex_total": after,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
