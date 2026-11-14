from datetime import date

from classification.enums import PromptVersion, TaxonomyVersion
from classification.models import Classification, Subject, Subtopic
from clues.enums import Round
from clues.models import SourceClue
from django.test import TestCase

from study.analytics import dashboard_data
from study.enums import AttemptGrade, SessionMode
from study.models import Attempt, StudySession


class AnalyticsTests(TestCase):
    def test_dashboard_uses_primary_subject_and_separates_review_accuracy(self):
        geography = Subject.objects.create(name="Geography", slug="geography")
        capitals = Subtopic.objects.create(subject=geography, slug="world-capitals", name="World capitals")
        first_session = StudySession.objects.create(mode=SessionMode.GENERAL, seed=1)
        clues = []
        for index in range(10):
            clue = SourceClue.objects.create(
                source_id=f"analytics:{index}",
                content_fingerprint=f"analytics-fingerprint-{index}",
                clue_text=f"Capital clue {index}",
                correct_response=f"City {index}",
                original_category="Words Starting with J",
                air_date=date(2022, 1, 1),
                round=Round.JEOPARDY,
                original_value=400 if index < 5 else 800,
            )
            clues.append(clue)
            Classification.objects.create(
                clue=clue,
                version=TaxonomyVersion.V1,
                primary_subject=geography,
                primary_subtopic=capitals,
                confidence=0.9,
                model_name="fixture",
                prompt_version=PromptVersion.V2,
            )
            Attempt.objects.create(
                session=first_session,
                position=index,
                clue=clue,
                canonical_snapshot=clue.correct_response,
                correctness=AttemptGrade.CORRECT if index < 8 else AttemptGrade.INCORRECT,
                automatic_correctness=AttemptGrade.CORRECT,
                response_ms=1000 + index,
                answered_at=first_session.started_at,
                is_first_seen=True,
            )

        review_session = StudySession.objects.create(mode=SessionMode.REVIEW, seed=2)
        Attempt.objects.create(
            session=review_session,
            position=0,
            clue=clues[0],
            canonical_snapshot=clues[0].correct_response,
            correctness=AttemptGrade.CORRECT,
            automatic_correctness=AttemptGrade.CORRECT,
            response_ms=800,
            answered_at=review_session.started_at,
            is_first_seen=False,
        )

        result = dashboard_data()
        self.assertEqual((result["total_attempts"], result["new_attempts"]), (11, 10))
        self.assertEqual(result["review_accuracy"], 1)
        self.assertEqual(result["review_attempts"], 1)
        geography_row = result["subjects"][0]
        self.assertEqual(geography_row["attempts"], 10)
        self.assertGreater(geography_row["upper_bound"], geography_row["proficiency"])
        capitals_row = geography_row["subtopics"][0]
        levels = {item["level"]: item["attempts"] for item in capitals_row["by_difficulty"]}
        self.assertEqual((levels[2], levels[4]), (5, 5))
        self.assertEqual(result["average_response_ms"], 986)
