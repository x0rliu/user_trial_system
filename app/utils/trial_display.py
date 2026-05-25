# app/utils/trial_display.py

import re


_ROUND_SUFFIX_RE = re.compile(
    r"\s*(?:[-–—]|\()\s*round\s+\d+\)?\s*$",
    re.IGNORECASE,
)

_ROUND_NUMBER_RE = re.compile(
    r"\bround\s+(\d+)\b",
    re.IGNORECASE,
)


def strip_round_suffix(value):
    """
    Remove a trailing "Round N" suffix from display names.

    Examples:
    - "Remo – Round 1" -> "Remo"
    - "Remo - Round 1" -> "Remo"
    - "Remo (Round 1)" -> "Remo"

    Display-only. Does not mutate stored DB values.
    """

    text = str(value or "").strip()

    if not text:
        return ""

    return _ROUND_SUFFIX_RE.sub("", text).strip()


def get_project_display_name(row, default="Untitled trial"):
    """
    Return the project/trial display name without any duplicated Round N suffix.
    """

    project_name = strip_round_suffix((row or {}).get("ProjectName"))

    if project_name:
        return project_name

    round_name = strip_round_suffix((row or {}).get("RoundName"))

    if round_name:
        return round_name

    return default


def get_round_number(row):
    """
    Return the human round number within a project.

    RoundNumber is preferred because it is the DB source for project-relative
    round sequence. RoundID is intentionally not used because it is a global DB id.
    """

    if not row:
        return None

    round_number = row.get("RoundNumber")

    if round_number not in (None, ""):
        try:
            return int(round_number)
        except (TypeError, ValueError):
            return str(round_number).strip()

    round_name = row.get("RoundName") or ""
    match = _ROUND_NUMBER_RE.search(str(round_name))

    if match:
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return match.group(1)

    return None


def get_round_display_label(row, default="—"):
    """
    Return "Round N" for display using the project-relative RoundNumber.
    """

    round_number = get_round_number(row)

    if round_number in (None, ""):
        return default

    return f"Round {round_number}"