import json
from pathlib import Path
from uuid import UUID

from clues.models import SourceClue
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from study.analytics import rebuild_review_state
from study.enums import AttemptGrade, RecallRating, SessionMode, SessionStatus
from study.models import Attempt, PracticePreset, StudySession


def _datetime(value: str | None):
    if value is None:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError("Invalid datetime.")
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


class Command(BaseCommand):
    help = "Restore a study export into a database that has the matching clue dataset."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        try:
            payload = json.loads(Path(options["path"]).read_text(encoding="utf-8"))
        except OSError as error:
            raise CommandError(str(error)) from error
        except json.JSONDecodeError as error:
            raise CommandError(str(error)) from error
        if not isinstance(payload, dict) or payload.get("format_version") != 1:
            raise CommandError("Unsupported progress export version.")
        if not isinstance(payload.get("sessions"), list) or not isinstance(payload.get("presets"), list):
            raise CommandError("Progress export must contain session and preset lists.")

        fingerprints = {
            value
            for item in payload["sessions"]
            if isinstance(item, dict) and isinstance(item.get("fingerprints"), list)
            for value in item["fingerprints"]
            if isinstance(value, str)
        }
        clues = {
            clue.content_fingerprint: clue for clue in SourceClue.objects.filter(content_fingerprint__in=fingerprints)
        }
        restored = skipped = 0
        updated_clues = set()
        with transaction.atomic():
            for preset in payload["presets"]:
                if not isinstance(preset, dict) or preset.get("mode") not in SessionMode.values:
                    continue
                name = preset.get("name")
                config = preset.get("config")
                if not isinstance(name, str) or not isinstance(config, dict):
                    continue
                PracticePreset.objects.update_or_create(
                    name=name,
                    mode=preset["mode"],
                    defaults={"config": config, "is_default": bool(preset.get("is_default", False))},
                )

            for item in payload["sessions"]:
                try:
                    session_data, attempts_data, session_clues = self._validate_session(item, clues)
                except KeyError, TypeError, ValueError:
                    skipped += 1
                    continue
                session_id = session_data.pop("id")
                old_clue_ids = set(Attempt.objects.filter(session_id=session_id).values_list("clue_id", flat=True))
                session, _ = StudySession.objects.update_or_create(id=session_id, defaults=session_data)
                session.attempts.all().delete()
                Attempt.objects.bulk_create(
                    [
                        Attempt(
                            session=session,
                            position=attempt["position"],
                            clue=session_clues[attempt["position"]],
                            typed_response=attempt["typed_response"],
                            canonical_snapshot=attempt["canonical_snapshot"],
                            correctness=attempt["correctness"],
                            automatic_correctness=attempt["automatic_correctness"],
                            recall_rating=attempt["recall_rating"],
                            response_ms=attempt["response_ms"],
                            is_first_seen=attempt["is_first_seen"],
                            revealed_at=attempt["revealed_at"],
                            answered_at=attempt["answered_at"],
                            started_at=attempt["started_at"],
                        )
                        for attempt in attempts_data
                    ]
                )
                updated_clues.update(old_clue_ids)
                updated_clues.update(clue.pk for clue in session_clues)
                restored += 1

            for clue_id in updated_clues:
                rebuild_review_state(clue_id)

        self.stdout.write(
            self.style.SUCCESS(f"Restored {restored} sessions; skipped {skipped} missing or invalid sessions.")
        )

    def _validate_session(self, item, clues):
        if not isinstance(item, dict):
            raise ValueError("Session must be an object.")
        if item.get("mode") not in SessionMode.values or item.get("status") not in SessionStatus.values:
            raise ValueError("Unsupported session mode or status.")
        fingerprints = item.get("fingerprints")
        attempts = item.get("attempts", [])
        config = item.get("config", {})
        if not isinstance(fingerprints, list) or not fingerprints or not isinstance(config, dict):
            raise ValueError("Session clues and configuration are required.")
        if not isinstance(attempts, list):
            raise ValueError("Session attempts must be a list.")
        session_clues = [clues.get(fingerprint) for fingerprint in fingerprints]
        if any(clue is None for clue in session_clues):
            raise ValueError("The matching clue dataset is incomplete.")
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("Session contains duplicate clues.")

        attempt_rows = []
        seen_positions = set()
        for attempt in attempts:
            position = attempt["position"]
            if not isinstance(position, int) or position < 0 or position >= len(fingerprints):
                raise ValueError("Attempt position is outside this session.")
            if position in seen_positions:
                raise ValueError("Duplicate attempt position.")
            if attempt.get("fingerprint") != fingerprints[position]:
                raise ValueError("Attempt clue does not match its session position.")
            correctness = attempt.get("correctness")
            automatic = attempt.get("automatic_correctness", AttemptGrade.UNANSWERED)
            if correctness not in AttemptGrade.values or automatic not in AttemptGrade.values:
                raise ValueError("Unsupported attempt grade.")
            recall_rating = attempt.get("recall_rating")
            if recall_rating is not None and recall_rating not in RecallRating.values:
                raise ValueError("Unsupported recall rating.")
            response_ms = attempt.get("response_ms")
            if response_ms is not None and (not isinstance(response_ms, int) or response_ms < 0):
                raise ValueError("Response time must be a non-negative integer.")
            typed_response = attempt.get("typed_response", "")
            snapshot = attempt.get("canonical_snapshot", session_clues[position].correct_response)
            if not isinstance(typed_response, str) or not isinstance(snapshot, str):
                raise ValueError("Responses must be text.")
            answered_at = _datetime(attempt.get("answered_at"))
            revealed_at = _datetime(attempt.get("revealed_at")) or answered_at
            attempt_rows.append(
                {
                    "position": position,
                    "typed_response": typed_response,
                    "canonical_snapshot": snapshot,
                    "correctness": correctness,
                    "automatic_correctness": automatic,
                    "recall_rating": recall_rating,
                    "response_ms": response_ms,
                    "is_first_seen": bool(attempt.get("is_first_seen", True)),
                    "revealed_at": revealed_at,
                    "answered_at": answered_at,
                    "started_at": _datetime(attempt["started_at"]),
                }
            )
            seen_positions.add(position)

        current_index = item.get("current_index", 0)
        seed = item.get("seed", 0)
        if not isinstance(current_index, int) or not 0 <= current_index <= len(fingerprints):
            raise ValueError("Invalid current question index.")
        if not isinstance(seed, int) or seed < 0:
            raise ValueError("Invalid random seed.")
        session_data = {
            "id": UUID(item["id"]),
            "mode": item["mode"],
            "seed": seed,
            "config": config,
            "clue_ids": [str(clue.pk) for clue in session_clues],
            "status": item["status"],
            "current_index": current_index,
            "started_at": _datetime(item["started_at"]),
            "completed_at": _datetime(item.get("completed_at")),
        }
        if session_data["started_at"] is None:
            raise ValueError("Session start time is required.")
        return session_data, attempt_rows, session_clues
