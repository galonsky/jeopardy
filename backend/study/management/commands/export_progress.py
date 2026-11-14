import json
from pathlib import Path
from typing import Any
from uuid import UUID

from clues.models import SourceClue
from django.core.management.base import BaseCommand, CommandError

from study.models import Attempt, PracticePreset, StudySession


class Command(BaseCommand):
    help = "Export study history and presets without copying the clue dataset."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        records = list(StudySession.objects.order_by("started_at"))
        clue_ids = {UUID(clue_id) for session in records for clue_id in session.clue_ids}
        clues = {str(clue.pk): clue for clue in SourceClue.objects.in_bulk(clue_ids).values()}
        attempts_by_session: dict[str, list[dict[str, Any]]] = {}
        attempts = Attempt.objects.filter(session__in=records).select_related("clue").order_by("session_id", "position")
        for attempt in attempts:
            attempts_by_session.setdefault(str(attempt.session_id), []).append(
                {
                    "position": attempt.position,
                    "fingerprint": attempt.clue.content_fingerprint,
                    "typed_response": attempt.typed_response,
                    "canonical_snapshot": attempt.canonical_snapshot,
                    "correctness": attempt.correctness,
                    "automatic_correctness": attempt.automatic_correctness,
                    "recall_rating": attempt.recall_rating,
                    "response_ms": attempt.response_ms,
                    "is_first_seen": attempt.is_first_seen,
                    "revealed_at": attempt.revealed_at.isoformat() if attempt.revealed_at else None,
                    "answered_at": attempt.answered_at.isoformat() if attempt.answered_at else None,
                    "started_at": attempt.started_at.isoformat(),
                }
            )
        sessions = []
        for session in records:
            missing = [clue_id for clue_id in session.clue_ids if clue_id not in clues]
            if missing:
                raise CommandError(f"Session {session.pk} references missing clues; progress export was not written.")
            sessions.append(
                {
                    "id": str(session.pk),
                    "mode": session.mode,
                    "seed": session.seed,
                    "config": session.config,
                    "fingerprints": [clues[clue_id].content_fingerprint for clue_id in session.clue_ids],
                    "status": session.status,
                    "current_index": session.current_index,
                    "started_at": session.started_at.isoformat(),
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                    "attempts": attempts_by_session.get(str(session.pk), []),
                }
            )
        payload = {
            "format_version": 1,
            "presets": list(PracticePreset.objects.values("name", "mode", "config", "is_default")),
            "sessions": sessions,
        }
        Path(options["path"]).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Exported {len(sessions)} sessions."))
