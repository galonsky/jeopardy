import json
from datetime import timedelta
from pathlib import Path

from clues.ingest import import_file
from clues.models import SourceClue
from django.test import TestCase
from django.utils import timezone

from study.enums import AttemptGrade, RecallRating, SessionMode
from study.models import Attempt, StudySession


class PracticeApiTests(TestCase):
    def setUp(self):
        sample = Path(__file__).resolve().parents[3] / "data" / "sample.tsv"
        created, _ = import_file(sample, "api-sample")
        self.assertEqual(created, 52)

    def test_general_practice_and_results_round_trip_without_classification(self):
        response = self.client.post(
            "/api/sessions",
            data=json.dumps({"mode": "general", "count": 1, "seed": 10}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        session = response.json()
        self.assertIsNone(session["question"]["subject"])
        self.assertIsNone(session["question"]["correct_response"])
        answer = self.client.post(
            f"/api/sessions/{session['id']}/answer",
            data=json.dumps({"answer": "my response"}),
            content_type="application/json",
        )
        self.assertEqual(answer.status_code, 200)
        self.assertIn("correct_response", answer.json())
        result = self.client.post(f"/api/sessions/{session['id']}/advance")
        self.assertTrue(result.json()["is_complete"])
        results = self.client.get(f"/api/sessions/{session['id']}/results").json()
        self.assertEqual(results["total"], 1)
        self.assertEqual(len(results["attempts"]), 1)

    def test_anytime_requires_fifty_and_hides_feedback_until_finish(self):
        response = self.client.post(
            "/api/sessions", data=json.dumps({"mode": "anytime", "seed": 7}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        session = response.json()
        self.assertEqual(session["total"], 50)
        self.assertIsNone(session["question"]["correct_response"])
        saved = self.client.post(
            f"/api/sessions/{session['id']}/answer", data=json.dumps({"answer": ""}), content_type="application/json"
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIsNone(saved.json()["question"]["question"]["correct_response"])

    def test_practice_presets_save_and_update_by_name_and_mode(self):
        payload = {"name": "Focused geography", "mode": "general", "config": {"subject_ids": [7]}}
        response = self.client.post("/api/presets", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        payload["config"] = {"subject_ids": [8]}
        updated = self.client.post("/api/presets", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["config"]["subject_ids"], [8])
        self.assertEqual(self.client.get("/api/presets").json()[0]["name"], "Focused geography")

    def test_timed_general_practice_enforces_deadline_on_the_server(self):
        response = self.client.post(
            "/api/sessions",
            data=json.dumps({"mode": "general", "count": 1, "seed": 9, "timer_seconds": 30}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        session = response.json()
        self.assertTrue(session["question"]["deadline_at"])
        attempt = Attempt.objects.get(session_id=session["id"], position=0)
        attempt.started_at = timezone.now() - timedelta(seconds=31)
        attempt.save(update_fields=["started_at"])
        clue = attempt.clue

        saved = self.client.post(
            f"/api/sessions/{session['id']}/answer",
            data=json.dumps({"answer": clue.correct_response, "response_ms": 1000, "position": 0}),
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200)
        attempt.refresh_from_db()
        self.assertEqual(attempt.typed_response, "")
        self.assertEqual(attempt.response_ms, 30_000)

    def test_reveal_and_self_rating_records_recall_without_typed_response(self):
        started = self.client.post(
            "/api/sessions",
            data=json.dumps({"mode": "general", "count": 1, "seed": 16}),
            content_type="application/json",
        ).json()
        clue_id = started["question"]["clue_id"]
        clue = SourceClue.objects.get(pk=clue_id)
        self.assertFalse(started["question"]["revealed"])
        self.assertIsNone(started["question"]["correct_response"])

        revealed = self.client.post(f"/api/sessions/{started['id']}/reveal").json()
        self.assertTrue(revealed["question"]["revealed"])
        self.assertFalse(revealed["question"]["answered"])
        self.assertEqual(revealed["question"]["correct_response"], clue.correct_response)

        completed = self.client.post(
            f"/api/sessions/{started['id']}/rate/0",
            data=json.dumps({"rating": RecallRating.GUESSED}),
            content_type="application/json",
        ).json()
        attempt = Attempt.objects.get(session_id=started["id"], position=0)
        self.assertTrue(completed["is_complete"])
        self.assertEqual(attempt.typed_response, "")
        self.assertEqual(attempt.recall_rating, RecallRating.GUESSED)
        self.assertEqual(attempt.correctness, AttemptGrade.PARTIAL)
        self.assertEqual(attempt.automatic_correctness, AttemptGrade.UNANSWERED)
        self.assertIsNotNone(attempt.revealed_at)
        result = self.client.get(f"/api/sessions/{started['id']}/results").json()
        self.assertEqual(result["attempts"][0]["recall_rating"], RecallRating.GUESSED)

    def test_recall_cannot_be_rated_before_revealing_response(self):
        started = self.client.post(
            "/api/sessions",
            data=json.dumps({"mode": "general", "count": 1, "seed": 17}),
            content_type="application/json",
        ).json()
        response = self.client.post(
            f"/api/sessions/{started['id']}/rate/0",
            data=json.dumps({"rating": RecallRating.CONFIDENT}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_skip_and_abandon_record_session_completion(self):
        started = self.client.post(
            "/api/sessions",
            data=json.dumps({"mode": "general", "count": 2, "seed": 4}),
            content_type="application/json",
        ).json()
        advanced = self.client.post(f"/api/sessions/{started['id']}/advance")
        self.assertEqual(advanced.json()["current_index"], 1)
        ended = self.client.post(f"/api/sessions/{started['id']}/abandon")
        self.assertTrue(ended.json()["is_complete"])
        self.assertEqual(ended.json()["status"], "abandoned")
        self.assertEqual(self.client.get(f"/api/sessions/{started['id']}/results").status_code, 200)

    def test_answer_after_prior_unanswered_exposure_is_not_a_novel_attempt(self):
        clue = SourceClue.objects.first()
        assert clue is not None
        exposed_session = StudySession.objects.create(mode=SessionMode.GENERAL, seed=1, clue_ids=[str(clue.pk)])
        Attempt.objects.create(
            session=exposed_session,
            position=0,
            clue=clue,
            canonical_snapshot=clue.correct_response,
        )
        answer_session = StudySession.objects.create(mode=SessionMode.GENERAL, seed=2, clue_ids=[str(clue.pk)])

        response = self.client.post(
            f"/api/sessions/{answer_session.pk}/answer",
            data=json.dumps({"answer": clue.correct_response}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        attempt = Attempt.objects.get(session=answer_session, position=0)
        self.assertFalse(attempt.is_first_seen)
