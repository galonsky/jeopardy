from datetime import date

from clues.enums import Round
from clues.models import SourceClue

DOUBLE_VALUES = {
    (200, 400, 600, 800, 1000): (1, 2, 3, 4, 5),
    (200, 400, 600, 800, 1000, 1200, 1600, 2000): (1, 2, 3, 4, 5),
}


def normalize_difficulty(
    round_name: str, original_value: int | None, board_row: int | None, air_date: date | None
) -> int | None:
    """Map known board rows or historical values to a five-row proxy."""
    if board_row is not None and 1 <= board_row <= 5:
        return board_row
    if original_value is None or round_name == Round.FINAL_JEOPARDY or original_value <= 0:
        return None
    if round_name not in (Round.JEOPARDY, Round.DOUBLE_JEOPARDY):
        return None
    # Values doubled at the start of the 2001 season; row position is invariant.
    modern = air_date is not None and air_date >= date(2001, 11, 26)
    base = 200 if modern else 100
    if round_name == Round.DOUBLE_JEOPARDY:
        base *= 2
    delta = original_value / base
    if delta.is_integer() and 1 <= int(delta) <= 5:
        return int(delta)
    return None


def difficulty_for(clue: SourceClue) -> int | None:
    return normalize_difficulty(clue.round, clue.original_value, clue.board_row, clue.air_date)
