import random
from datetime import timedelta
from uuid import UUID

from asgiref.sync import sync_to_async
from classification.enums import TaxonomyVersion
from classification.models import Classification, Subject
from clues.difficulty import difficulty_for
from clues.models import SourceClue
from core.enums import JobKind
from core.models import BackgroundJob
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone
from ninja import Schema
from ninja_extra import NinjaExtraAPI
from pydantic import Field, field_validator, model_validator
from study.analytics import dashboard_data, rebuild_review_state
from study.enums import AttemptGrade, RecallRating, SessionMode, SessionStatus, TimerDuration
from study.grading import grade_answer
from study.models import Attempt, PracticePreset, StudySession
from study.selection import select_clues

from config.serialization import OrjsonParser, OrjsonRenderer

api = NinjaExtraAPI(title="Jeopardy Study API", version="1.0.0", parser=OrjsonParser(), renderer=OrjsonRenderer())


class StartSession(Schema):
    mode: SessionMode = SessionMode.GENERAL
    count: int = Field(default=20, ge=1, le=100)
    seed: int | None = None
    min_difficulty: int = Field(default=1, ge=1, le=5)
    max_difficulty: int = Field(default=5, ge=1, le=5)
    difficulty_weights: dict[str, float] = Field(default_factory=dict)
    subject_ids: list[int] = Field(default_factory=list)
    subtopic_ids: list[int] = Field(default_factory=list)
    include_double: bool = True
    include_daily_doubles: bool = False
    include_final: bool = False
    include_media_required: bool = False
    min_date: str | None = None
    max_date: str | None = None
    timer_seconds: TimerDuration | None = None

    @model_validator(mode="after")
    def validate_difficulty_range(self):
        if self.min_difficulty > self.max_difficulty:
            raise ValueError("Minimum difficulty must not exceed maximum difficulty.")
        return self


class AnswerInput(Schema):
    answer: str = ""
    response_ms: int | None = Field(default=None, ge=0)
    position: int | None = Field(default=None, ge=0)


class GradeInput(Schema):
    correctness: AttemptGrade

    @field_validator("correctness")
    @classmethod
    def validate_grade(cls, value: AttemptGrade) -> AttemptGrade:
        if value not in (AttemptGrade.CORRECT, AttemptGrade.PARTIAL, AttemptGrade.INCORRECT):
            raise ValueError("Choose correct, partially correct, or incorrect.")
        return value


class RecallRatingInput(Schema):
    rating: RecallRating


class ClassificationJobInput(Schema):
    version: TaxonomyVersion = TaxonomyVersion.V1
    limit: int = Field(default=0, ge=0)
    concurrency: int = Field(default=2, ge=1, le=16)
    clue_ids: list[str] = Field(default_factory=list)
    reprocess: bool = False


class PracticePresetInput(Schema):
    name: str = Field(min_length=1, max_length=100)
    mode: SessionMode = SessionMode.GENERAL
    config: dict = Field(default_factory=dict)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Preset name cannot be blank.")
        return value


def _subject_payload() -> list[dict]:
    return [
        {
            "id": subject.id,
            "name": subject.name,
            "slug": subject.slug,
            "subtopics": [
                {"id": topic.id, "name": topic.name, "slug": topic.slug} for topic in subject.subtopics.all()
            ],
        }
        for subject in Subject.objects.prefetch_related("subtopics").order_by("sort_order", "name")
    ]


def _session_payload(session: StudySession) -> dict:
    attempt, clue = None, None
    ids = session.clue_ids
    if session.current_index < len(ids):
        clue = SourceClue.objects.get(pk=ids[session.current_index])
        attempt, _ = Attempt.objects.get_or_create(
            session=session,
            position=session.current_index,
            clue=clue,
            defaults={"canonical_snapshot": clue.correct_response},
        )
        assert attempt is not None
    seconds = 15 if session.mode == SessionMode.ANYTIME else session.config.get("timer_seconds")
    timed = seconds is not None
    done = session.status != "active" or session.current_index >= len(ids)
    result = {
        "id": str(session.id),
        "mode": session.mode,
        "status": session.status,
        "current_index": session.current_index,
        "total": len(ids),
        "requested_total": session.config.get("count", len(ids)),
        "shortfall": max(0, session.config.get("count", len(ids)) - len(ids)),
        "seed": session.seed,
        "config": session.config,
        "is_complete": done,
    }
    if clue is not None and not done:
        assert attempt is not None
        classification = (
            Classification.objects.filter(clue=clue, version=TaxonomyVersion.V1)
            .select_related("primary_subject", "primary_subtopic")
            .first()
        )
        result["question"] = {
            "clue_id": str(clue.id),
            "category": clue.original_category,
            "clue": clue.clue_text,
            "round": clue.round,
            "difficulty": difficulty_for(clue),
            "subject": classification.primary_subject.name if classification else None,
            "answered": attempt.answered_at is not None,
            "revealed": attempt.revealed_at is not None or attempt.answered_at is not None,
            "answer": attempt.typed_response,
            "correct_response": (
                clue.correct_response
                if session.mode != SessionMode.ANYTIME and (attempt.revealed_at is not None or attempt.answered_at)
                else None
            ),
            "deadline_at": (attempt.started_at + timedelta(seconds=seconds)).isoformat() if timed else None,
            "grading": None if session.mode == SessionMode.ANYTIME else attempt.correctness,
            "recall_rating": attempt.recall_rating,
        }
        if timed:
            result["seconds_per_question"] = seconds
    return result


def _session_get(session_id: str) -> dict:
    try:
        return _session_payload(StudySession.objects.get(pk=session_id))
    except StudySession.DoesNotExist, ValueError:
        raise Http404


@api.get("/health", operation_id="health", tags=["System"])
def health(request):
    return {"status": "ok"}


@api.get("/taxonomy", operation_id="getTaxonomy", tags=["Subjects"])
def taxonomy(request):
    return _subject_payload()


@api.get("/dashboard", operation_id="getDashboard", tags=["Analytics"])
def dashboard(request):
    return dashboard_data()


@api.get("/history", operation_id="getHistory", tags=["Sessions"])
def history(request):
    sessions = StudySession.objects.annotate(
        answered_count=Count("attempts", filter=~Q(attempts__correctness="unanswered"))
    ).order_by("-started_at")[:50]
    return [
        {
            "id": str(item.id),
            "mode": item.mode,
            "started_at": item.started_at,
            "status": item.status,
            "count": len(item.clue_ids),
            "answered": item.answered_count,
        }
        for item in sessions
    ]


@api.get("/presets", operation_id="getPresets", tags=["Settings"])
def presets(request):
    return [
        {"id": item.id, "name": item.name, "mode": item.mode, "config": item.config, "is_default": item.is_default}
        for item in PracticePreset.objects.order_by("mode", "name")
    ]


@api.post("/presets", operation_id="savePracticePreset", tags=["Settings"])
def save_preset(request, payload: PracticePresetInput):
    with transaction.atomic():
        if payload.is_default:
            PracticePreset.objects.filter(mode=payload.mode).update(is_default=False)
        preset, _ = PracticePreset.objects.update_or_create(
            name=payload.name.strip(),
            mode=payload.mode,
            defaults={"config": payload.config, "is_default": payload.is_default},
        )
    return {
        "id": preset.id,
        "name": preset.name,
        "mode": preset.mode,
        "config": preset.config,
        "is_default": preset.is_default,
    }


@api.post("/classification-jobs", operation_id="startClassificationJob", tags=["Classification"])
async def start_classification_job(request, payload: ClassificationJobInput):
    if not settings.CLASSIFICATION_MODEL or not settings.OPENAI_API_KEY:
        return api.create_response(
            request,
            {"error": "Set CLASSIFICATION_MODEL and OPENAI_API_KEY to enable optional classification."},
            status=422,
        )
    if not await Subject.objects.filter(taxonomy_version=payload.version).aexists():
        return api.create_response(
            request,
            {"error": "Load the matching subject taxonomy before classifying clues."},
            status=422,
        )
    job = await sync_to_async(BackgroundJob.objects.create, thread_sensitive=True)(
        kind=JobKind.CLASSIFICATION,
        version=payload.version,
        config={
            "limit": max(0, payload.limit),
            "concurrency": max(1, min(payload.concurrency, 16)),
            "clue_ids": payload.clue_ids,
            "reprocess": payload.reprocess,
        },
    )
    from core.tasks import run_classification_job

    await run_classification_job.kiq(str(job.pk))
    return {"id": str(job.pk), "status": job.status}


@api.get("/classification-jobs", operation_id="getClassificationJobs", tags=["Classification"])
def classification_jobs(request):
    return [
        {
            "id": str(job.pk),
            "status": job.status,
            "total": job.total,
            "processed": job.processed,
            "failed": job.failed,
            "error": job.error,
            "created_at": job.created_at,
        }
        for job in BackgroundJob.objects.filter(kind=JobKind.CLASSIFICATION).order_by("-created_at")[:25]
    ]


@api.post("/sessions", operation_id="startSession", tags=["Practice"])
def start_session(request, payload: StartSession):
    mode = payload.mode
    count = 50 if mode == SessionMode.ANYTIME else max(1, min(payload.count, 100))
    seed = payload.seed if payload.seed is not None else random.SystemRandom().randrange(2**32)
    config = payload.model_dump(mode="json")
    config["count"] = count
    if mode == SessionMode.ANYTIME and not config.get("difficulty_weights"):
        config["difficulty_weights"] = {"1": 0.10, "2": 0.25, "3": 0.35, "4": 0.25, "5": 0.05}
    chosen = select_clues(config, mode, seed, count)
    if mode == SessionMode.ANYTIME and len(chosen) < 50:
        return api.create_response(
            request, {"error": f"Only {len(chosen)} eligible clues are available; 50 are required."}, status=422
        )
    if not chosen:
        return api.create_response(
            request,
            {"error": "No clues match these filters. Try widening your difficulty, date, or subject filters."},
            status=422,
        )
    session = StudySession.objects.create(
        mode=mode, seed=seed, config=config, clue_ids=[str(item.id) for item in chosen]
    )
    return _session_get(str(session.id))


@api.get("/sessions/{session_id}", operation_id="getSession", tags=["Practice"])
def get_session(request, session_id: str):
    return _session_get(session_id)


@api.post("/sessions/{session_id}/reveal", operation_id="revealCurrentAnswer", tags=["Practice"])
def reveal_current_answer(request, session_id: str):
    with transaction.atomic():
        session = StudySession.objects.select_for_update().get(pk=session_id)
        if session.status != SessionStatus.ACTIVE or session.current_index >= len(session.clue_ids):
            return api.create_response(request, {"error": "This session is complete."}, status=409)
        if session.mode == SessionMode.ANYTIME:
            return api.create_response(request, {"error": "Answers stay hidden until the test ends."}, status=409)
        clue = SourceClue.objects.get(pk=session.clue_ids[session.current_index])
        attempt, _ = Attempt.objects.get_or_create(
            session=session,
            position=session.current_index,
            clue=clue,
            defaults={"canonical_snapshot": clue.correct_response},
        )
        if attempt.answered_at or attempt.revealed_at:
            return _session_payload(session)
        attempt.revealed_at = timezone.now()
        attempt.save(update_fields=["revealed_at"])
    return _session_get(str(session.id))


@api.post("/sessions/{session_id}/rate/{position}", operation_id="rateCurrentRecall", tags=["Practice"])
def rate_current_recall(request, session_id: str, position: int, payload: RecallRatingInput):
    grade_for_rating = {
        RecallRating.CONFIDENT: AttemptGrade.CORRECT,
        RecallRating.GUESSED: AttemptGrade.PARTIAL,
        RecallRating.DID_NOT_KNOW: AttemptGrade.INCORRECT,
    }
    with transaction.atomic():
        session = StudySession.objects.select_for_update().get(pk=session_id)
        if session.status != SessionStatus.ACTIVE or session.current_index >= len(session.clue_ids):
            return api.create_response(request, {"error": "This session is complete."}, status=409)
        if session.mode == SessionMode.ANYTIME:
            return api.create_response(request, {"error": "Anytime responses use timed answer scoring."}, status=409)
        if position != session.current_index:
            return api.create_response(request, {"error": "This clue is no longer current."}, status=409)
        clue = SourceClue.objects.get(pk=session.clue_ids[position])
        attempt, _ = Attempt.objects.get_or_create(
            session=session,
            position=position,
            clue=clue,
            defaults={"canonical_snapshot": clue.correct_response},
        )
        if attempt.answered_at:
            return api.create_response(request, {"error": "This clue has already been rated."}, status=409)
        if attempt.revealed_at is None:
            return api.create_response(request, {"error": "Reveal the response before rating recall."}, status=409)
        now = timezone.now()
        prior = (
            Attempt.objects.filter(clue__content_fingerprint=clue.content_fingerprint).exclude(pk=attempt.pk).exists()
        )
        seconds = session.config.get("timer_seconds")
        response_ms = max(0, round((now - attempt.started_at).total_seconds() * 1000))
        if seconds:
            response_ms = min(response_ms, seconds * 1000)
        attempt.typed_response = ""
        attempt.correctness = grade_for_rating[payload.rating]
        attempt.automatic_correctness = AttemptGrade.UNANSWERED
        attempt.recall_rating = payload.rating
        attempt.response_ms = response_ms
        attempt.is_first_seen = not prior
        attempt.answered_at = now
        attempt.save()
        rebuild_review_state(clue.pk)
        session.current_index += 1
        if session.current_index >= len(session.clue_ids):
            session.status = SessionStatus.COMPLETED
            session.completed_at = now
        session.save(update_fields=["current_index", "status", "completed_at"])
    return _session_get(str(session.id))


@api.post("/sessions/{session_id}/answer", operation_id="answerCurrentQuestion", tags=["Practice"])
def answer_question(request, session_id: str, payload: AnswerInput):
    with transaction.atomic():
        session = StudySession.objects.select_for_update().get(pk=session_id)
        if session.status != "active" or session.current_index >= len(session.clue_ids):
            return api.create_response(request, {"error": "This session is complete."}, status=409)
        if payload.position is not None and payload.position != session.current_index:
            if session.mode == SessionMode.ANYTIME:
                return {"saved": True, "question": _session_get(str(session.id))}
            return api.create_response(request, {"error": "This question has already been answered."}, status=409)
        clue = SourceClue.objects.get(pk=session.clue_ids[session.current_index])
        attempt, _ = Attempt.objects.get_or_create(
            session=session,
            position=session.current_index,
            clue=clue,
            defaults={"canonical_snapshot": clue.correct_response},
        )
        if attempt.answered_at:
            if session.mode == SessionMode.ANYTIME:
                return {"saved": True, "question": _session_get(str(session.id))}
            return {
                "saved": True,
                "grading": attempt.correctness,
                "correct_response": clue.correct_response,
                "needs_review": attempt.correctness == "uncertain",
            }
        response_text = payload.answer
        response_ms = payload.response_ms
        seconds = 15 if session.mode == SessionMode.ANYTIME else session.config.get("timer_seconds")
        if seconds and timezone.now() >= attempt.started_at + timedelta(seconds=seconds):
            response_text = ""
            response_ms = seconds * 1000
        grade, _ = grade_answer(response_text, clue)
        prior = (
            Attempt.objects.filter(clue__content_fingerprint=clue.content_fingerprint).exclude(pk=attempt.pk).exists()
        )
        attempt.typed_response = response_text
        attempt.automatic_correctness = grade
        attempt.correctness = grade
        if session.mode != SessionMode.ANYTIME:
            attempt.revealed_at = timezone.now()
        attempt.response_ms = response_ms
        attempt.answered_at = timezone.now()
        attempt.is_first_seen = not prior
        attempt.save()
        rebuild_review_state(clue.pk)
        if session.mode == SessionMode.ANYTIME:
            session.current_index += 1
            if session.current_index >= len(session.clue_ids):
                session.status = SessionStatus.COMPLETED
                session.completed_at = timezone.now()
            session.save(update_fields=["current_index", "status", "completed_at"])
    if session.mode == SessionMode.ANYTIME:
        return {"saved": True, "question": _session_get(str(session.id))}
    return {
        "saved": True,
        "grading": attempt.correctness,
        "correct_response": clue.correct_response,
        "needs_review": grade == "uncertain",
    }


@api.post("/sessions/{session_id}/advance", operation_id="advanceSession", tags=["Practice"])
def advance_session(request, session_id: str):
    with transaction.atomic():
        session = StudySession.objects.select_for_update().get(pk=session_id)
        if session.mode == SessionMode.ANYTIME:
            return api.create_response(
                request, {"error": "Timed test questions advance when you answer or time out."}, status=409
            )
        if session.status != SessionStatus.ACTIVE or session.current_index >= len(session.clue_ids):
            return api.create_response(request, {"error": "This session is complete."}, status=409)
        session.current_index += 1
        if session.current_index >= len(session.clue_ids):
            session.status = SessionStatus.COMPLETED
            session.completed_at = timezone.now()
        session.save(update_fields=["current_index", "status", "completed_at"])
    return _session_get(str(session.id))


@api.post("/sessions/{session_id}/abandon", operation_id="abandonSession", tags=["Practice"])
def abandon_session(request, session_id: str):
    with transaction.atomic():
        session = StudySession.objects.select_for_update().get(pk=session_id)
        if session.status == SessionStatus.ACTIVE:
            session.status = SessionStatus.ABANDONED
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at"])
    return _session_get(str(session.id))


@api.post("/sessions/{session_id}/grade/{position}", operation_id="overrideGrade", tags=["Practice"])
def override_grade(request, session_id: UUID, position: int, payload: GradeInput):
    attempt = Attempt.objects.get(session_id=session_id, position=position)
    attempt.correctness = payload.correctness
    attempt.save(update_fields=["correctness"])
    rebuild_review_state(attempt.clue_id)
    return {"updated": True, "correctness": attempt.correctness, "dashboard": dashboard_data()}


@api.get("/sessions/{session_id}/results", operation_id="getSessionResults", tags=["Sessions"])
def results(request, session_id: UUID):
    session = StudySession.objects.get(pk=session_id)
    attempts = session.attempts.select_related("clue").order_by("position")
    if session.mode == SessionMode.ANYTIME and session.status == "active":
        return api.create_response(request, {"error": "Results are available when the test ends."}, status=409)
    rows = [
        {
            "position": item.position,
            "clue_id": str(item.clue_id),
            "category": item.clue.original_category,
            "clue": item.clue.clue_text,
            "response": item.typed_response,
            "correct_response": item.canonical_snapshot,
            "correctness": item.correctness,
            "recall_rating": item.recall_rating,
            "difficulty": difficulty_for(item.clue),
        }
        for item in attempts
    ]
    total = len(rows)
    earned = sum(
        1 if row["correctness"] == "correct" else 0.5 if row["correctness"] == "partial" else 0 for row in rows
    )
    return {
        "id": str(session.id),
        "mode": session.mode,
        "correct": sum(row["correctness"] == "correct" for row in rows),
        "total": total,
        "score": round(earned, 1),
        "accuracy": round(earned / total, 3) if total else 0,
        "attempts": rows,
    }
