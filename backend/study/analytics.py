from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from classification.enums import TaxonomyVersion
from classification.models import Subject
from clues.difficulty import normalize_difficulty
from django.db.models import Avg, Count, Q

from study.enums import AttemptGrade, SessionMode
from study.models import Attempt, ReviewState

PRIOR_ALPHA = 2
PRIOR_BETA = 2
SCORED_GRADES = (AttemptGrade.CORRECT, AttemptGrade.PARTIAL, AttemptGrade.INCORRECT)


def _estimate(attempts: int, correct: int, partial: int = 0) -> dict:
    credited = correct + partial * 0.5
    alpha = credited + PRIOR_ALPHA
    beta = attempts - credited + PRIOR_BETA
    denominator = alpha + beta
    mean = alpha / denominator
    standard_error = (alpha * beta / (denominator**2 * (denominator + 1))) ** 0.5
    confidence = "high" if attempts >= 30 else "medium" if attempts >= 10 else "low"
    return {
        "attempts": attempts,
        "correct": correct,
        "partial": partial,
        "proficiency": round(mean, 3),
        "lower_bound": round(max(0, mean - 1.96 * standard_error), 3),
        "upper_bound": round(min(1, mean + 1.96 * standard_error), 3),
        "confidence": confidence,
    }


def _credit(accuracy_rows: Sequence[Mapping[str, Any]]) -> float:
    count = len(accuracy_rows)
    if not count:
        return 0
    correct = sum(row["correctness"] == AttemptGrade.CORRECT for row in accuracy_rows)
    partial = sum(row["correctness"] == AttemptGrade.PARTIAL for row in accuracy_rows)
    return (correct + partial * 0.5) / count


def _difficulty_groups(rows: Sequence[Mapping[str, Any]], key: str | None = None) -> dict[Any, dict[str, int]]:
    groups: dict[Any, dict[str, int]] = defaultdict(lambda: {"attempts": 0, "correct": 0, "partial": 0})
    for row in rows:
        level = normalize_difficulty(
            row["clue__round"],
            row["clue__original_value"],
            row["clue__board_row"],
            row["clue__air_date"],
        )
        if level is None:
            continue
        group_key = (row[key], level) if key else level
        group = groups[group_key]
        group["attempts"] += row["attempts"]
        group["correct"] += row["correct"]
        group["partial"] += row["partial"]
    return groups


def dashboard_data() -> dict:
    answered = Attempt.objects.filter(answered_at__isnull=False)
    scored = answered.filter(correctness__in=SCORED_GRADES)
    novel = scored.filter(is_first_seen=True)
    total = answered.count()
    graded_total = scored.count()
    correct = scored.filter(correctness=AttemptGrade.CORRECT).count()
    novel_total = novel.count()
    novel_correct = novel.filter(correctness=AttemptGrade.CORRECT).count()
    novel_partial = novel.filter(correctness=AttemptGrade.PARTIAL).count()
    review = scored.filter(session__mode=SessionMode.REVIEW)
    review_total = review.count()
    review_correct = review.filter(correctness=AttemptGrade.CORRECT).count()
    overall = _estimate(novel_total, novel_correct, novel_partial)
    novel_rows = list(novel.order_by("-answered_at", "-pk").values("correctness")[:100])
    recent, previous = novel_rows[:50], novel_rows[50:100]
    recent_trend = {
        "recent_attempts": len(recent),
        "recent_accuracy": round(_credit(recent), 3) if recent else None,
        "previous_attempts": len(previous),
        "previous_accuracy": round(_credit(previous), 3) if previous else None,
        "delta": round(_credit(recent) - _credit(previous), 3) if recent and previous else None,
    }
    response_time = answered.aggregate(value=Avg("response_ms"))["value"]

    subject_query = novel.filter(clue__classifications__version=TaxonomyVersion.V1)
    subject_groups = {
        row["clue__classifications__primary_subject_id"]: row
        for row in subject_query.values("clue__classifications__primary_subject_id").annotate(
            attempts=Count("id"),
            correct=Count("id", filter=Q(correctness=AttemptGrade.CORRECT)),
            partial=Count("id", filter=Q(correctness=AttemptGrade.PARTIAL)),
        )
    }
    subtopic_groups = {
        row["clue__classifications__primary_subtopic_id"]: row
        for row in subject_query.values("clue__classifications__primary_subtopic_id").annotate(
            attempts=Count("id"),
            correct=Count("id", filter=Q(correctness=AttemptGrade.CORRECT)),
            partial=Count("id", filter=Q(correctness=AttemptGrade.PARTIAL)),
        )
    }
    difficulty_rows = list(
        novel.values("clue__board_row", "clue__round", "clue__original_value", "clue__air_date").annotate(
            attempts=Count("id"),
            correct=Count("id", filter=Q(correctness=AttemptGrade.CORRECT)),
            partial=Count("id", filter=Q(correctness=AttemptGrade.PARTIAL)),
        )
    )
    difficulty_groups = _difficulty_groups(difficulty_rows)
    subject_difficulty_rows = list(
        subject_query.values(
            "clue__classifications__primary_subtopic_id",
            "clue__board_row",
            "clue__round",
            "clue__original_value",
            "clue__air_date",
        ).annotate(
            attempts=Count("id"),
            correct=Count("id", filter=Q(correctness=AttemptGrade.CORRECT)),
            partial=Count("id", filter=Q(correctness=AttemptGrade.PARTIAL)),
        )
    )
    subtopic_difficulties = _difficulty_groups(
        subject_difficulty_rows, key="clue__classifications__primary_subtopic_id"
    )

    subject_rows = []
    for subject in Subject.objects.prefetch_related("subtopics").order_by("sort_order", "name"):
        row = subject_groups.get(subject.id)
        if row is None:
            continue
        subtopics = []
        for topic in subject.subtopics.all():
            topic_row = subtopic_groups.get(topic.id, {"attempts": 0, "correct": 0, "partial": 0})
            levels = [
                {
                    "level": level,
                    **_estimate(
                        **subtopic_difficulties.get((topic.id, level), {"attempts": 0, "correct": 0, "partial": 0})
                    ),
                }
                for level in range(1, 6)
            ]
            subtopics.append(
                {
                    "id": topic.id,
                    "name": topic.name,
                    **_estimate(topic_row["attempts"], topic_row["correct"], topic_row["partial"]),
                    "by_difficulty": levels,
                }
            )
        subject_rows.append(
            {
                "id": subject.id,
                "name": subject.name,
                **_estimate(row["attempts"], row["correct"], row["partial"]),
                "subtopics": subtopics,
            }
        )
    weak = sorted((item for item in subject_rows if item["attempts"] >= 10), key=lambda item: item["proficiency"])
    mode_groups = [
        {
            "mode": row["session__mode"],
            **_estimate(row["attempts"], row["correct"], row["partial"]),
        }
        for row in scored.values("session__mode")
        .annotate(
            attempts=Count("id"),
            correct=Count("id", filter=Q(correctness=AttemptGrade.CORRECT)),
            partial=Count("id", filter=Q(correctness=AttemptGrade.PARTIAL)),
        )
        .order_by("session__mode")
    ]
    difficulty_levels = [
        {"level": level, **_estimate(**difficulty_groups.get(level, {"attempts": 0, "correct": 0, "partial": 0}))}
        for level in range(1, 6)
    ]
    recommendations = []
    if weak:
        recommendations.append(f"Your weakest well-sampled subject is {weak[0]['name']}.")
    if recent_trend["delta"] is not None and len(recent) >= 20 and len(previous) >= 20:
        change = recent_trend["delta"]
        if abs(change) >= 0.05:
            direction = "improved" if change > 0 else "declined"
            recommendations.append(f"Your accuracy has {direction} over your last 50 new clues.")
    for subject_data in subject_rows:
        for topic in subject_data["subtopics"]:
            level_rows = [level for level in topic["by_difficulty"] if level["attempts"] >= 10]
            if level_rows:
                best = max(level_rows, key=lambda level: level["proficiency"])
                weakest = min(level_rows, key=lambda level: level["proficiency"])
            else:
                continue
            if best["level"] != weakest["level"] and best["proficiency"] - weakest["proficiency"] >= 0.2:
                recommendations.append(
                    f"In {topic['name']}, difficulty {best['level']} is stronger than difficulty {weakest['level']}."
                )
                break
        else:
            continue
        break

    return {
        "total_attempts": total,
        "graded_attempts": graded_total,
        "novel_graded_attempts": novel_total,
        "uncertain_attempts": answered.filter(correctness=AttemptGrade.UNCERTAIN).count(),
        "new_attempts": answered.filter(is_first_seen=True).count(),
        "correct": correct,
        "accuracy": round(correct / graded_total, 3) if graded_total else 0,
        "novel_accuracy": round(novel_correct / novel_total, 3) if novel_total else 0,
        "proficiency": overall["proficiency"],
        "lower_bound": overall["lower_bound"],
        "upper_bound": overall["upper_bound"],
        "average_response_ms": round(response_time) if response_time is not None else None,
        "review_attempts": review_total,
        "review_accuracy": round(review_correct / review_total, 3) if review_total else 0,
        "subjects": subject_rows,
        "weak_areas": weak[:3],
        "difficulty_levels": difficulty_levels,
        "mode_performance": mode_groups,
        "recent_trend": recent_trend,
        "recommendations": recommendations,
    }


def rebuild_review_state(clue_id) -> None:
    """Recompute due state from attempts so a grading correction cannot leave stale scheduling."""
    rows = list(
        Attempt.objects.filter(clue_id=clue_id, answered_at__isnull=False)
        .select_related("session")
        .order_by("answered_at", "pk")
        .values_list("session__mode", "correctness", "answered_at")
    )
    misses = [
        index
        for index, (_, grade, _) in enumerate(rows)
        if grade in {AttemptGrade.INCORRECT, AttemptGrade.PARTIAL, AttemptGrade.UNCERTAIN}
    ]
    if not misses:
        ReviewState.objects.filter(clue_id=clue_id).delete()
        return
    last_miss = misses[-1]
    review_correct = [
        answered_at
        for mode, grade, answered_at in rows[last_miss + 1 :]
        if mode == SessionMode.REVIEW and grade == AttemptGrade.CORRECT
    ]
    intervals = [1, 3, 7, 14, 30]
    repetitions = len(review_correct)
    if repetitions:
        interval = intervals[min(repetitions - 1, len(intervals) - 1)]
        base = review_correct[-1]
    else:
        interval = 1
        base = rows[last_miss][2]
    assert base is not None
    ReviewState.objects.update_or_create(
        clue_id=clue_id,
        defaults={"due_at": base + timedelta(days=interval), "interval_days": interval, "repetitions": repetitions},
    )
