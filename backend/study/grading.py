import re
import unicodedata

from clues.models import SourceClue

ALIASES = {
    "nyc": "new york city",
    "the big apple": "new york city",
    "usa": "united states",
    "u s a": "united states",
    "uk": "united kingdom",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    value = re.sub(r"^(the|a|an)\s+", "", value)
    return ALIASES.get(value, value)


def grade_answer(response: str, clue: SourceClue) -> tuple[str, float]:
    """Return conservative correctness and a similarity score for manual review."""
    from difflib import SequenceMatcher

    answer = normalize(response)
    accepted = [clue.correct_response, *clue.original_payload.get("aliases", [])]
    normalized = [normalize(str(item)) for item in accepted if item]
    if not answer:
        return "incorrect", 0.0
    if answer in normalized:
        return "correct", 1.0
    similarity = max((SequenceMatcher(None, answer, expected).ratio() for expected in normalized), default=0)
    if similarity >= 0.86 and abs(len(answer) - len(normalized[0])) <= 2:
        return "uncertain", similarity
    return "incorrect", similarity
