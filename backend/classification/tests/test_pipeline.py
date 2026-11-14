import json
import os
from datetime import date
from unittest.mock import ANY, Mock, patch

from clues.enums import Round
from clues.models import SourceClue
from django.test import TestCase

from classification.enums import PromptVersion, TaxonomyVersion
from classification.models import Classification, Subject, Subtopic
from classification.pipeline import classify_one, classify_pending


class ClassificationBatchTests(TestCase):
    def test_prompt_uses_response_for_subject_when_category_is_wordplay(self):
        subject = Subject.objects.create(name="Geography", slug="geography")
        topic = Subtopic.objects.create(subject=subject, name="World capitals", slug="world-capitals")
        clue = self._clue("jakarta")
        clue.original_category = "Words Starting with J"
        clue.category_comments = "Every response starts with J."
        clue.clue_text = "This Indonesian capital sits on the northwest coast of Java."
        clue.correct_response = "Jakarta"
        clue.save()
        completion = {
            "subject": "Geography",
            "subtopic": "World capitals",
            "secondary": [],
            "mechanics": ["wordplay"],
            "entities": ["Jakarta"],
            "confidence": 0.98,
        }
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": json.dumps(completion)}}]}

        with (
            patch.dict(os.environ, {"CLASSIFICATION_MODEL": "test-model", "OPENAI_API_KEY": "test-key"}),
            patch("classification.pipeline.httpx.post", return_value=response) as post,
        ):
            self.assertTrue(classify_one(clue.pk, TaxonomyVersion.V1))

        prompt = post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("Words Starting with J", prompt)
        self.assertIn("This Indonesian capital", prompt)
        self.assertIn("Correct response: Jakarta", prompt)
        self.assertIn("on-air category and comments are context only", prompt)
        classification = Classification.objects.get(clue=clue)
        self.assertEqual((classification.primary_subject, classification.primary_subtopic), (subject, topic))
        self.assertEqual(classification.mechanics, ["wordplay"])

    def test_pending_is_resumable_and_selected_clues_can_be_reprocessed(self):
        subject = Subject.objects.create(name="Geography", slug="geography")
        topic = Subtopic.objects.create(subject=subject, name="World capitals", slug="world-capitals")
        classified = self._clue("classified")
        selected = self._clue("selected")
        Classification.objects.create(
            clue=classified,
            version=TaxonomyVersion.V1,
            primary_subject=subject,
            primary_subtopic=topic,
            model_name="fixture",
            prompt_version=PromptVersion.V2,
        )

        progress = []
        with patch("classification.pipeline.classify_one", return_value=True) as classify_one:
            self.assertEqual(
                classify_pending(
                    version=TaxonomyVersion.V1,
                    concurrency=1,
                    progress_callback=lambda *values: progress.append(values),
                ),
                (1, 0),
            )
            classify_one.assert_called_once_with(selected.pk, TaxonomyVersion.V1, taxonomy_snapshot=ANY)
            self.assertEqual(progress, [(0, 0, 1), (1, 0, 1)])
            classify_one.reset_mock()
            self.assertEqual(
                classify_pending(
                    version=TaxonomyVersion.V1,
                    concurrency=1,
                    clue_ids=[str(classified.pk)],
                    reprocess=True,
                ),
                (1, 0),
            )
            classify_one.assert_called_once_with(classified.pk, TaxonomyVersion.V1, taxonomy_snapshot=ANY)

    def _clue(self, name):
        return SourceClue.objects.create(
            source_id=f"classification:{name}",
            content_fingerprint=f"classification-fingerprint-{name}",
            clue_text="This clue tests a knowledge area.",
            correct_response="An answer",
            original_category="Wordplay",
            air_date=date(2022, 1, 1),
            round=Round.JEOPARDY,
            original_value=200,
        )
