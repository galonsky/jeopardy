from datetime import date

from classification.enums import PromptVersion, TaxonomyVersion
from classification.models import Classification, Subject, Subtopic
from clues.difficulty import difficulty_for
from clues.enums import Round
from clues.models import SourceClue
from django.test import TestCase
from django.utils import timezone

from study.analytics import rebuild_review_state
from study.enums import AttemptGrade, SessionMode
from study.grading import grade_answer, normalize
from study.models import Attempt, ReviewState, StudySession
from study.selection import select_clues


class GradingSelectionTests(TestCase):
    def setUp(self):
        self.clues = [
            SourceClue.objects.create(
                source_id=f"fixture:{i}",
                content_fingerprint=f"fingerprint-{i}",
                clue_text=f"Capital clue {i}",
                correct_response=f"City {i}",
                original_category=f"Category {i}",
                air_date=date(2022, 1, 1),
                round=Round.JEOPARDY,
                original_value=200 * (i % 5 + 1),
            )
            for i in range(8)
        ]

    def test_normalization_and_conservative_grading(self):
        self.assertEqual(normalize("  THE Café! "), "cafe")
        self.assertEqual(grade_answer("City 0", self.clues[0])[0], "correct")
        self.assertEqual(grade_answer("City 00", self.clues[0])[0], "uncertain")
        self.assertEqual(grade_answer("a different city", self.clues[0])[0], "incorrect")

    def test_seeded_selection_is_repeatable_without_duplicates(self):
        a = select_clues({"min_difficulty": 1, "max_difficulty": 5}, SessionMode.GENERAL, 15, 5)
        b = select_clues({"min_difficulty": 1, "max_difficulty": 5}, SessionMode.GENERAL, 15, 5)
        self.assertEqual([x.pk for x in a], [x.pk for x in b])
        self.assertEqual(len({x.pk for x in a}), len(a))

    def test_exposed_unanswered_clue_is_not_selected_as_new_when_unseen_clues_are_available(self):
        clue = self.clues[0]
        session = StudySession.objects.create(mode=SessionMode.GENERAL, seed=1, clue_ids=[str(clue.pk)])
        Attempt.objects.create(session=session, position=0, clue=clue, canonical_snapshot=clue.correct_response)

        selected = select_clues({"min_difficulty": 1, "max_difficulty": 5}, SessionMode.GENERAL, 15, 7)

        self.assertEqual(len(selected), 7)
        self.assertNotIn(clue.pk, {selected_clue.pk for selected_clue in selected})

    def test_weighted_selection_excludes_zero_weight_rows_when_a_bucket_is_short(self):
        selected = select_clues(
            {"min_difficulty": 1, "max_difficulty": 5, "difficulty_weights": {"3": 100}},
            SessionMode.GENERAL,
            15,
            8,
        )
        self.assertTrue(selected)
        self.assertTrue(all(difficulty_for(clue) == 3 for clue in selected))

    def test_final_jeopardy_is_selectable_without_a_board_row_difficulty(self):
        final = SourceClue.objects.create(
            source_id="fixture:final",
            content_fingerprint="fingerprint-final",
            clue_text="This river flows through Vienna.",
            correct_response="The Danube",
            original_category="Rivers",
            air_date=date(2023, 1, 1),
            round=Round.FINAL_JEOPARDY,
        )
        selected = select_clues(
            {
                "min_difficulty": 1,
                "max_difficulty": 5,
                "min_date": "2023-01-01",
                "max_date": "2023-01-01",
                "include_final": True,
            },
            SessionMode.GENERAL,
            15,
            1,
        )
        self.assertEqual([clue.pk for clue in selected], [final.pk])

    def test_tricky_on_air_category_classification_is_semantically_independent(self):
        subject = Subject.objects.create(name="Geography", slug="geography")
        topic = Subtopic.objects.create(subject=subject, slug="world-capitals", name="World capitals")
        clue = self.clues[0]
        clue.original_category = "Words Starting with J"
        clue.clue_text = "This Indonesian capital sits on the northwest coast of Java."
        clue.correct_response = "Jakarta"
        clue.save()
        Classification.objects.create(
            clue=clue,
            version=TaxonomyVersion.V1,
            primary_subject=subject,
            primary_subtopic=topic,
            confidence=0.96,
            model_name="fixture",
            prompt_version=PromptVersion.V2,
        )
        self.assertEqual(clue.classifications.get().primary_subtopic.name, "World capitals")
        self.assertEqual(clue.original_category, "Words Starting with J")

    def test_attempt_correctness_has_explicit_primary_attribution(self):
        session = StudySession.objects.create(mode=SessionMode.GENERAL, seed=1, clue_ids=[str(self.clues[0].pk)])
        Attempt.objects.create(
            session=session,
            position=0,
            clue=self.clues[0],
            canonical_snapshot=self.clues[0].correct_response,
            correctness=AttemptGrade.CORRECT,
            automatic_correctness=AttemptGrade.CORRECT,
        )
        self.assertEqual(session.attempts.count(), 1)

    def test_review_schedule_rebuilds_from_attempts_and_corrections(self):
        clue = self.clues[0]
        first = StudySession.objects.create(mode=SessionMode.GENERAL, seed=1)
        Attempt.objects.create(
            session=first,
            position=0,
            clue=clue,
            canonical_snapshot=clue.correct_response,
            correctness="incorrect",
            automatic_correctness="incorrect",
            answered_at=timezone.now(),
        )
        rebuild_review_state(clue.pk)
        self.assertEqual(ReviewState.objects.get(clue=clue).interval_days, 1)
        review = StudySession.objects.create(mode=SessionMode.REVIEW, seed=2)
        Attempt.objects.create(
            session=review,
            position=0,
            clue=clue,
            canonical_snapshot=clue.correct_response,
            correctness="correct",
            automatic_correctness="correct",
            answered_at=timezone.now(),
        )
        rebuild_review_state(clue.pk)
        state = ReviewState.objects.get(clue=clue)
        self.assertEqual((state.interval_days, state.repetitions), (1, 1))
        missed = first.attempts.get()
        missed.correctness = "correct"
        missed.save(update_fields=["correctness"])
        rebuild_review_state(clue.pk)
        self.assertFalse(ReviewState.objects.filter(clue=clue).exists())
