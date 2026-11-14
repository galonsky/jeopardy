import csv
import hashlib
import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

from django.db import transaction

from clues.enums import Round
from clues.models import SourceClue

IMPORT_BATCH_SIZE = 1000
UPDATE_FIELDS = [
    "source_url",
    "content_fingerprint",
    "clue_text",
    "correct_response",
    "original_category",
    "category_comments",
    "show_number",
    "air_date",
    "round",
    "original_value",
    "is_daily_double",
    "original_payload",
]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()) if value.strip() else None
    except ValueError:
        return None


def _normalize_text(value: str) -> str:
    return value.replace(r"\"", '"')


def _round(value: str) -> str:
    try:
        return {1: Round.JEOPARDY, 2: Round.DOUBLE_JEOPARDY, 3: Round.FINAL_JEOPARDY}[int(value)]
    except ValueError, KeyError:
        return Round.OTHER


def _source_url(data: dict[str, str]) -> str:
    return data.get("source_url", "").strip()


def _build_clue(data: dict[str, str], source_revision: str, number: int) -> SourceClue | None:
    clue_text = _normalize_text(data.get("answer", data.get("clue", data.get("clue_text", ""))).strip())
    response = _normalize_text(data.get("question", data.get("response", data.get("correct_response", ""))).strip())
    category = _normalize_text(data.get("category", data.get("original_category", "")).strip())
    if not clue_text or not response or not category:
        return None
    air_date = _parse_date(data.get("air_date", ""))
    source_id = (
        data.get("id", "").strip() or f"{source_revision}:{data.get('show_number', '')}:{air_date or ''}:{number}"
    )
    payload = json.dumps([clue_text, response, category], ensure_ascii=False, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    try:
        value = int(data.get("clue_value") or 0) or None
        wager = int(data.get("daily_double_value") or 0)
    except ValueError:
        value, wager = None, 0
    return SourceClue(
        source_id=source_id,
        source_url=_source_url(data),
        content_fingerprint=fingerprint,
        clue_text=clue_text,
        correct_response=response,
        original_category=category,
        category_comments=_normalize_text(data.get("comments", "")),
        show_number=data.get("show_number", ""),
        air_date=air_date,
        round=_round(data.get("round", "")),
        original_value=value,
        is_daily_double=wager > 0,
        original_payload=data,
    )


def _flush_batch(batch: list[SourceClue]) -> tuple[int, int]:
    unique = {clue.source_id: clue for clue in batch}
    source_ids = list(unique)
    existing = set(SourceClue.objects.filter(source_id__in=source_ids).values_list("source_id", flat=True))
    with transaction.atomic():
        SourceClue.objects.bulk_create(
            list(unique.values()),
            batch_size=IMPORT_BATCH_SIZE,
            update_conflicts=True,
            update_fields=UPDATE_FIELDS,
            unique_fields=["source_id"],
        )
    return len(unique) - len(existing), len(existing)


def _import_rows(
    rows: Iterable[dict[str, Any]], source_revision: str, min_air_date: date | None
) -> tuple[int, int]:
    created = updated = 0
    batch = []
    for number, row in enumerate(rows, start=1):
        data = {str(key).strip().lower(): (value or "") for key, value in row.items() if key is not None}
        if min_air_date and (_parse_date(data.get("air_date", "")) or date.min) < min_air_date:
            continue
        clue = _build_clue(data, source_revision, number)
        if clue is None:
            continue
        batch.append(clue)
        if len(batch) == IMPORT_BATCH_SIZE:
            new, refreshed = _flush_batch(batch)
            created += new
            updated += refreshed
            batch.clear()
    if batch:
        new, refreshed = _flush_batch(batch)
        created += new
        updated += refreshed
    return created, updated


def import_file(path: str | Path, source_revision: str = "local", min_air_date: date | None = None) -> tuple[int, int]:
    """Import a TSV/CSV/JSON source in idempotent batches, preserving each original row."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        return _import_rows(json.loads(path.read_text(encoding="utf-8")), source_revision, min_air_date)
    delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    with path.open(encoding="utf-8-sig", newline="") as source:
        return _import_rows(csv.DictReader(source, delimiter=delimiter), source_revision, min_air_date)
