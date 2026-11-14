import json
import tempfile
from datetime import date
from pathlib import Path

from clues.enums import Round
from clues.models import SourceClue
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from study.enums import AttemptGrade, RecallRating, SessionMode, SessionStatus
from study.models import Attempt, PracticePreset, StudySession


class ProgressExportTests(TestCase):
    def test_export_import_round_trip_restores_answers_and_presets(self):
        clue = SourceClue.objects.create(
            source_id="progress-fixture:1",
            content_fingerprint="progress-fixture-fingerprint",
            clue_text="This capital is on the Java Sea.",
            correct_response="Jakarta",
            original_category="Words Starting with J",
            air_date=date(2022, 1, 1),
            round=Round.JEOPARDY,
            original_value=200,
        )
        session = StudySession.objects.create(
            mode=SessionMode.GENERAL,
            seed=17,
            config={"count": 1},
            clue_ids=[str(clue.pk)],
            status=SessionStatus.COMPLETED,
            current_index=1,
        )
        Attempt.objects.create(
            session=session,
            position=0,
            clue=clue,
            typed_response="Jakarta",
            canonical_snapshot="Jakarta (DKI Jakarta)",
            correctness=AttemptGrade.CORRECT,
            automatic_correctness=AttemptGrade.UNCERTAIN,
            recall_rating=RecallRating.CONFIDENT,
            response_ms=2400,
            is_first_seen=True,
            revealed_at=timezone.now(),
            answered_at=timezone.now(),
        )
        PracticePreset.objects.create(
            name="Anytime warmup",
            mode=SessionMode.ANYTIME,
            config={"min_difficulty": 2, "max_difficulty": 4},
            is_default=True,
        )

        with tempfile.TemporaryDirectory() as directory:
            export_path = Path(directory) / "progress.json"
            call_command("export_progress", str(export_path))
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["sessions"][0]["attempts"][0]["canonical_snapshot"], "Jakarta (DKI Jakarta)")

            session_id = session.pk
            session.delete()
            PracticePreset.objects.all().delete()
            call_command("import_progress", str(export_path))

        restored = StudySession.objects.get(pk=session_id)
        attempt = restored.attempts.get()
        self.assertEqual(attempt.typed_response, "Jakarta")
        self.assertEqual(attempt.canonical_snapshot, "Jakarta (DKI Jakarta)")
        self.assertEqual(attempt.correctness, AttemptGrade.CORRECT)
        self.assertEqual(attempt.automatic_correctness, AttemptGrade.UNCERTAIN)
        self.assertEqual(attempt.recall_rating, RecallRating.CONFIDENT)
        self.assertIsNotNone(attempt.revealed_at)
        self.assertTrue(PracticePreset.objects.get(name="Anytime warmup").is_default)
