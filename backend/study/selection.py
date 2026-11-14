import random
from datetime import date

from classification.enums import TaxonomyVersion
from classification.models import Classification
from clues.difficulty import difficulty_for
from clues.enums import Round
from clues.models import SourceClue
from django.db.models import Count, Q
from django.utils import timezone

from study.enums import AttemptGrade, SessionMode
from study.models import Attempt, ReviewState


def select_clues(config: dict, mode: str, seed: int, count: int) -> list[SourceClue]:
    queryset = SourceClue.objects.all().order_by("source_id")
    if not config.get("include_media_required", False):
        queryset = queryset.filter(media_required=False)
    if config.get("min_date"):
        queryset = queryset.filter(air_date__gte=date.fromisoformat(config["min_date"]))
    if config.get("max_date"):
        queryset = queryset.filter(air_date__lte=date.fromisoformat(config["max_date"]))
    if not config.get("include_double", True):
        queryset = queryset.exclude(round=Round.DOUBLE_JEOPARDY)
    if not config.get("include_final", False):
        queryset = queryset.exclude(round=Round.FINAL_JEOPARDY)
    if not config.get("include_daily_doubles", False):
        queryset = queryset.filter(is_daily_double=False)
    subject_ids = config.get("subject_ids", [])
    subtopic_ids = config.get("subtopic_ids", [])
    if subject_ids:
        matching = Classification.objects.filter(
            version=TaxonomyVersion.V1,
            primary_subject_id__in=subject_ids,
        ).values_list("clue_id", flat=True)
        queryset = queryset.filter(id__in=matching)
    if subtopic_ids:
        matching = Classification.objects.filter(
            version=TaxonomyVersion.V1,
            primary_subtopic_id__in=subtopic_ids,
        ).values_list("clue_id", flat=True)
        queryset = queryset.filter(id__in=matching)
    queryset = queryset.only(
        "id",
        "source_id",
        "content_fingerprint",
        "round",
        "board_row",
        "original_value",
        "air_date",
        "original_category",
        "is_daily_double",
    )
    min_level = int(config.get("min_difficulty", 1))
    max_level = int(config.get("max_difficulty", 5))
    clues = []
    for clue in queryset:
        level = difficulty_for(clue)
        if (
            (clue.round == Round.FINAL_JEOPARDY and config.get("include_final", False))
            or (level is None and config.get("include_unknown", False))
            or min_level <= (level or 0) <= max_level
        ):
            clues.append(clue)
    rng = random.Random(seed)
    seen_fingerprints = set(Attempt.objects.values_list("clue__content_fingerprint", flat=True).distinct())
    unique_clues: dict[str, SourceClue] = {}
    for clue in clues:
        unique_clues.setdefault(clue.content_fingerprint, clue)
    clues = list(unique_clues.values())
    weak_weights = {}
    if mode == SessionMode.REVIEW:
        due_ids = set(ReviewState.objects.filter(due_at__lte=timezone.now()).values_list("clue_id", flat=True))
        clues = [clue for clue in clues if clue.id in due_ids]
    elif mode == SessionMode.WEAK_AREAS:
        # Reweight subjects by low success and uncertainty, then retain seeded variety.
        counts = {
            row["clue__classifications__primary_subject_id"]: [
                row["attempts"],
                row["correct"] + row["partial"] * 0.5,
            ]
            for row in Attempt.objects.filter(
                is_first_seen=True,
                correctness__in=(AttemptGrade.CORRECT, AttemptGrade.PARTIAL, AttemptGrade.INCORRECT),
                clue__classifications__version=TaxonomyVersion.V1,
            )
            .values("clue__classifications__primary_subject_id")
            .annotate(
                attempts=Count("id"),
                correct=Count("id", filter=Q(correctness=AttemptGrade.CORRECT)),
                partial=Count("id", filter=Q(correctness=AttemptGrade.PARTIAL)),
            )
        }
        primary_by_clue = dict(
            Classification.objects.filter(version=TaxonomyVersion.V1).values_list("clue_id", "primary_subject_id")
        )
        for clue in clues:
            subject_id = primary_by_clue.get(clue.id)
            attempts_count, credited = counts.get(subject_id, [0, 0]) if subject_id is not None else [0, 0]
            alpha = credited + 2
            beta = attempts_count - credited + 2
            mean = alpha / (alpha + beta)
            error = (alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1))) ** 0.5
            lower_bound = max(0, mean - 1.28 * error)
            weak_weights[clue.id] = 0.5 + 1 - lower_bound
    unseen = [clue for clue in clues if clue.content_fingerprint not in seen_fingerprints]
    seen = [clue for clue in clues if clue.content_fingerprint in seen_fingerprints]
    if mode == SessionMode.WEAK_AREAS:
        pool = unseen if len(unseen) >= count else unseen + seen
        candidate = sorted(
            pool,
            key=lambda clue: rng.random() ** (1 / weak_weights.get(clue.id, 1)),
            reverse=True,
        )
    else:
        rng.shuffle(unseen)
        rng.shuffle(seen)
        candidate = unseen + ([] if mode == SessionMode.ANYTIME else seen)
    if mode == SessionMode.ANYTIME:
        distinct_categories = []
        used_categories = set()
        for clue in candidate:
            category = " ".join(clue.original_category.casefold().split())
            if category not in used_categories:
                distinct_categories.append(clue)
                used_categories.add(category)
        if len(distinct_categories) >= count:
            candidate = distinct_categories
    weights = config.get("difficulty_weights") or {}
    if not weights:
        return candidate[:count]
    buckets: dict[int, list[SourceClue]] = {level: [] for level in range(min_level, max_level + 1)}
    for clue in candidate:
        level = difficulty_for(clue)
        if level in buckets:
            buckets[level].append(clue)
    selected: list[SourceClue] = []
    positive_levels = [level for level in buckets if float(weights.get(str(level), 0)) > 0]
    total_weight = sum(float(weights.get(str(level), 0)) for level in positive_levels)
    if total_weight == 0:
        return []
    for level in positive_levels:
        bucket = buckets[level]
        quota = round(count * float(weights.get(str(level), 0)) / total_weight)
        selected.extend(bucket[: min(quota, len(bucket))])
    selected_ids = {clue.id for clue in selected}
    fallback = [clue for level in positive_levels for clue in buckets[level] if clue.id not in selected_ids]
    fallback.extend(clue for clue in candidate if clue.round == Round.FINAL_JEOPARDY and clue.id not in selected_ids)
    selected.extend(fallback[: max(0, count - len(selected))])
    rng.shuffle(selected)
    return selected[:count]
