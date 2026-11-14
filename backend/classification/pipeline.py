import hashlib
import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import httpx
from clues.models import SourceClue
from django.db import close_old_connections
from django.db.models import Prefetch
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from classification.enums import Mechanic, PromptVersion, TaxonomyVersion
from classification.models import Classification, Subject, Subtopic


class SecondaryClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    subtopic: str


class Classified(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    subtopic: str
    secondary: list[SecondaryClassification] = Field(default_factory=list)
    mechanics: list[Mechanic] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


type TaxonomySnapshot = tuple[list[dict[str, str | list[str]]], dict[tuple[str, str], tuple[int, int]]]


def _taxonomy_snapshot(version: str) -> TaxonomySnapshot:
    taxonomy: list[dict[str, str | list[str]]] = []
    lookup: dict[tuple[str, str], tuple[int, int]] = {}
    subjects = (
        Subject.objects.filter(taxonomy_version=version)
        .prefetch_related(Prefetch("subtopics", queryset=Subtopic.objects.order_by("name")))
        .order_by("sort_order", "name")
    )
    for subject in subjects:
        topics = list(subject.subtopics.all())
        subtopic_names: list[str] = [topic.name for topic in topics]
        taxonomy.append({"subject": subject.name, "subtopics": subtopic_names})
        for topic in topics:
            lookup[(subject.name, topic.name)] = (int(subject.pk), int(topic.pk))
    return taxonomy, lookup


def build_classification_prompt(clue: SourceClue, taxonomy: list[dict[str, str | list[str]]]) -> str:
    return (
        "Classify the knowledge needed to produce the correct Jeopardy response. Use clue and response primarily; "
        "on-air category and comments are context only. Return one taxonomy subject and subtopic, optional secondary "
        "subject/subtopic objects, and mechanic tags from: "
        f"{', '.join(Mechanic.values)}. "
        f"Taxonomy: {json.dumps(taxonomy)}\nCategory: {clue.original_category}\nComments: {clue.category_comments}"
        f"\nClue: {clue.clue_text}\nCorrect response: {clue.correct_response}"
    )


def classify_one(
    clue_id: UUID | str,
    version: str,
    prompt_version: str = PromptVersion.V2,
    taxonomy_snapshot: TaxonomySnapshot | None = None,
) -> bool:
    clue = SourceClue.objects.get(pk=clue_id)
    model = os.environ["CLASSIFICATION_MODEL"]
    key = os.environ["OPENAI_API_KEY"]
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    taxonomy, lookup = taxonomy_snapshot or _taxonomy_snapshot(version)
    prompt = build_classification_prompt(clue, taxonomy)
    input_hash = hashlib.sha256(prompt.encode()).hexdigest()
    for attempt in range(3):
        try:
            response = httpx.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            response.raise_for_status()
            data = Classified.model_validate_json(response.json()["choices"][0]["message"]["content"])
            subject_id, topic_id = lookup[(data.subject, data.subtopic)]
            secondary = []
            for assignment in data.secondary:
                _ = lookup[(assignment.subject, assignment.subtopic)]
                secondary.append({"subject": assignment.subject, "subtopic": assignment.subtopic})
            Classification.objects.update_or_create(
                clue=clue,
                version=version,
                defaults={
                    "primary_subject_id": subject_id,
                    "primary_subtopic_id": topic_id,
                    "secondary": secondary,
                    "mechanics": [mechanic.value for mechanic in data.mechanics],
                    "entities": data.entities,
                    "confidence": data.confidence,
                    "model_name": model,
                    "prompt_version": prompt_version,
                    "input_hash": input_hash,
                },
            )
            return True
        except httpx.HTTPError, KeyError, ValueError, ValidationError:
            if attempt == 2:
                return False
            time.sleep(2**attempt)
    return False


def classify_pending(
    version: str = TaxonomyVersion.V1,
    concurrency: int = 2,
    limit: int = 0,
    clue_ids: list[str] | None = None,
    reprocess: bool = False,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> tuple[int, int]:
    pending_query = SourceClue.objects.all()
    if clue_ids:
        pending_query = pending_query.filter(pk__in=clue_ids)
    if not reprocess:
        pending_query = pending_query.exclude(classifications__version=version)
    pending = pending_query.values_list("pk", flat=True)
    if limit:
        pending = pending[:limit]
    ids = list(pending)
    total = len(ids)
    taxonomy_snapshot = _taxonomy_snapshot(version)
    if not taxonomy_snapshot[0]:
        raise ValueError(f"No taxonomy exists for classification version {version}.")
    if progress_callback:
        progress_callback(0, 0, total)
    processed = failed = 0
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:

        def classify_safely(clue_id):
            close_old_connections()
            try:
                return classify_one(clue_id, version, taxonomy_snapshot=taxonomy_snapshot)
            finally:
                close_old_connections()

        for index, success in enumerate(pool.map(classify_safely, ids), start=1):
            processed += int(success)
            failed += int(not success)
            if progress_callback and (index % 10 == 0 or index == total):
                progress_callback(processed, failed, total)
    return processed, failed
