import importlib
from types import SimpleNamespace

from clues.ingest import _build_clue
from clues.models import SourceClue
from django.apps import apps
from django.db import connection
from django.test import TestCase

from study.enums import SessionMode
from study.models import Attempt, StudySession

clue_migration = importlib.import_module("clues.migrations.0004_normalize_escaped_single_quotes")
attempt_migration = importlib.import_module("study.migrations.0007_normalize_answer_snapshots_single_quotes")
schema_editor = SimpleNamespace(connection=connection)


class SingleQuoteMigrationTests(TestCase):
    def test_clue_migration_unescapes_text_and_matches_import_fingerprint(self):
        expected = _build_clue(
            {
                "answer": r"It\'s a clue",
                "question": r"What\'s this",
                "category": r"Don\'t",
                "comments": r"A\'s",
                "air_date": "2022-01-01",
            },
            "rev",
            1,
        )
        assert expected is not None
        clue = SourceClue.objects.create(
            source_id="old",
            content_fingerprint="stale",
            clue_text=r"It\'s a clue",
            correct_response=r"What\'s this",
            original_category=r"Don\'t",
            category_comments=r"A\'s",
        )
        untouched = SourceClue.objects.create(
            source_id="clean",
            content_fingerprint="keep",
            clue_text="Fine",
            correct_response="Fine",
            original_category="Fine",
        )

        clue_migration.normalize_escaped_single_quotes(apps, schema_editor)

        clue.refresh_from_db()
        self.assertEqual(clue.clue_text, "It's a clue")
        self.assertEqual(clue.correct_response, "What's this")
        self.assertEqual(clue.original_category, "Don't")
        self.assertEqual(clue.category_comments, "A's")
        self.assertEqual(clue.content_fingerprint, expected.content_fingerprint)
        untouched.refresh_from_db()
        self.assertEqual(untouched.content_fingerprint, "keep")

    def test_attempt_migration_unescapes_snapshot(self):
        clue = SourceClue.objects.create(
            source_id="c", content_fingerprint="f", clue_text="t", correct_response="r", original_category="c"
        )
        session = StudySession.objects.create(mode=SessionMode.GENERAL, seed=1, clue_ids=[str(clue.pk)])
        attempt = Attempt.objects.create(session=session, position=0, clue=clue, canonical_snapshot=r"What\'s \"up\"")

        attempt_migration.normalize_answer_snapshots_single_quotes(apps, schema_editor)

        attempt.refresh_from_db()
        self.assertEqual(attempt.canonical_snapshot, 'What\'s \\"up\\"')
