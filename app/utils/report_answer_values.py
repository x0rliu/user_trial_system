# app/utils/report_answer_values.py

from __future__ import annotations

import re


_LEADING_FRAGMENT_RE = re.compile(
    r"^(i\b|i['’]|it\b|they\b|we\b|but\b|and\b|or\b|however\b|though\b|because\b|didn['’]t\b|don['’]t\b|couldn['’]t\b|wouldn['’]t\b)",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def split_countable_answer_value(value: object) -> list[str]:
    """
    Split countable report answer values only when the comma is likely acting as
    a multi-select delimiter.

    Google Forms exports checkbox answers as comma-separated text, but normal
    single-choice labels also frequently contain commas, such as:
    - "No, I didn't need to"
    - "No, but I knew I could"
    - "Yes, but I did not use it"

    Those labels must remain intact because each option maps to a different
    product action. This helper is intentionally conservative: when in doubt,
    preserve the original value.
    """

    raw = _clean(value)
    if not raw:
        return []

    if "," not in raw:
        return [raw]

    candidates = [_clean(part) for part in raw.split(",") if _clean(part)]
    if len(candidates) <= 1:
        return [raw]

    lower_candidates = [candidate.lower() for candidate in candidates]

    # "No, I didn't..." and "Yes, but..." are single option labels, not
    # multi-select answers.
    if lower_candidates[0] in {"yes", "no"}:
        return [raw]

    for candidate in candidates[1:]:
        if _LEADING_FRAGMENT_RE.search(candidate):
            return [raw]

    # Long comma-separated prose is more likely to be a written answer or a
    # labeled option with punctuation than a compact checkbox list.
    for candidate in candidates:
        if len(candidate.split()) > 5:
            return [raw]

    return candidates