import csv
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from clues.difficulty import normalize_difficulty
from clues.enums import Round
from clues.ingest import import_file
from clues.models import SourceClue
from django.test import TestCase


class IngestionDifficultyTests(TestCase):
    def test_import_is_idempotent_and_preserves_raw_source(self):
        fixture = Path(__file__).resolve().parents[3] / "data" / "sample.tsv"
        created, updated = import_file(fixture, "sample-v1")
        self.assertGreater(created, 0)
        again, refreshed = import_file(fixture, "sample-v1")
        self.assertEqual((again, refreshed), (0, created))
        clue = SourceClue.objects.first()
        assert clue is not None
        self.assertTrue(clue.source_id.startswith("sample-v1:"))
        self.assertEqual(clue.source_url, "")
        self.assertIn("answer", clue.original_payload)
        self.assertEqual(SourceClue.objects.count(), created)

    def test_import_can_limit_rows_to_a_date_range(self):
        fixture = Path(__file__).resolve().parents[3] / "data" / "sample.tsv"
        created, updated = import_file(fixture, "recent-sample", date(2024, 1, 11))
        self.assertEqual(updated, 0)
        self.assertGreater(created, 0)
        self.assertEqual(SourceClue.objects.filter(air_date__lt=date(2024, 1, 11)).count(), 0)

    def test_import_unescapes_quotes_but_preserves_the_raw_payload(self):
        fields = [
            "round",
            "clue_value",
            "daily_double_value",
            "category",
            "comments",
            "answer",
            "question",
            "air_date",
            "source_url",
        ]
        raw_category = r"\"TITLES\""
        raw_comments = r"Use the escaped \"quote\""
        raw_clue = r"Name the song \"Pomp\""
        raw_response = r"\"Pomp And Circumstance\""

        with TemporaryDirectory() as directory:
            path = Path(directory) / "quoted.tsv"
            with path.open("w", encoding="utf-8", newline="") as source:
                writer = csv.DictWriter(source, fieldnames=fields, delimiter="\t")
                writer.writeheader()
                writer.writerow(
                    {
                        "round": "1",
                        "clue_value": "200",
                        "daily_double_value": "0",
                        "category": raw_category,
                        "comments": raw_comments,
                        "answer": raw_clue,
                        "question": raw_response,
                        "air_date": "2022-09-12",
                        "source_url": "https://source.example.test/clues/quoted-1",
                    }
                )

            created, _ = import_file(path, "quoted-v1")

        self.assertEqual(created, 1)
        clue = SourceClue.objects.get()
        self.assertEqual(clue.original_category, '"TITLES"')
        self.assertEqual(clue.category_comments, 'Use the escaped "quote"')
        self.assertEqual(clue.clue_text, 'Name the song "Pomp"')
        self.assertEqual(clue.correct_response, '"Pomp And Circumstance"')
        self.assertEqual(clue.source_url, "https://source.example.test/clues/quoted-1")
        self.assertEqual(clue.original_payload["question"], raw_response)

    def test_difficulty_uses_round_and_era(self):
        self.assertEqual(normalize_difficulty(Round.JEOPARDY, 600, None, date(2022, 1, 1)), 3)
        self.assertEqual(normalize_difficulty(Round.DOUBLE_JEOPARDY, 1200, None, date(2022, 1, 1)), 3)
        self.assertEqual(normalize_difficulty(Round.JEOPARDY, 300, None, date(1984, 9, 10)), 3)
        self.assertIsNone(normalize_difficulty(Round.FINAL_JEOPARDY, 0, None, None))
        self.assertEqual(normalize_difficulty(Round.JEOPARDY, 100, 5, None), 5)
