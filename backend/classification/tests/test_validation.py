from unittest import TestCase

from pydantic import ValidationError

from classification.pipeline import Classified


class ClassificationValidationTests(TestCase):
    def test_structured_result_requires_valid_confidence_and_fields(self):
        result = Classified.model_validate(
            {
                "subject": "Geography",
                "subtopic": "World capitals",
                "secondary": [],
                "mechanics": ["wordplay"],
                "entities": ["Jakarta"],
                "confidence": 0.94,
            }
        )
        self.assertEqual(result.subject, "Geography")
        self.assertEqual(result.mechanics[0], "wordplay")
        with self.assertRaises(ValidationError):
            Classified.model_validate({"subject": "Geography", "subtopic": "World capitals", "confidence": 1.2})

    def test_mechanics_and_secondary_assignments_are_structured(self):
        result = Classified.model_validate(
            {
                "subject": "Geography",
                "subtopic": "World capitals",
                "secondary": [{"subject": "History", "subtopic": "World history"}],
                "mechanics": ["wordplay"],
                "entities": ["Jakarta"],
                "confidence": 0.9,
            }
        )
        self.assertEqual(result.secondary[0].subject, "History")
        with self.assertRaises(ValidationError):
            Classified.model_validate(
                {
                    "subject": "Geography",
                    "subtopic": "World capitals",
                    "mechanics": ["random"],
                    "confidence": 0.9,
                }
            )
