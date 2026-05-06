# app/services/gender_values.py

CANONICAL_GENDER_VALUES = {
    "female",
    "male",
    "non_binary",
    "prefer_not_to_say",
}

GENDER_VALUE_ALIASES = {
    "female": "female",
    "male": "male",

    "non_binary": "non_binary",
    "nonbinary": "non_binary",
    "non-binary": "non_binary",
    "non binary": "non_binary",

    "prefer_not_to_say": "prefer_not_to_say",
    "prefer not to say": "prefer_not_to_say",
    "unspecified": "prefer_not_to_say",
}


def canonicalize_gender_value(value) -> str | None:
    """
    Converts known gender aliases into the canonical app value.

    Returns None for blank or unknown values.
    """
    raw = str(value or "").strip().lower()

    if not raw:
        return None

    return GENDER_VALUE_ALIASES.get(raw)


def canonicalize_gender_values(values) -> list[str]:
    """
    Converts a list/string of gender values into canonical values.

    Preserves order.
    Removes blanks, unknowns, and duplicates.
    """
    if values is None:
        return []

    if isinstance(values, str):
        values = [values]

    normalized = []

    for value in values:
        canonical = canonicalize_gender_value(value)

        if canonical and canonical not in normalized:
            normalized.append(canonical)

    return normalized


def gender_display_label(value) -> str:
    canonical = canonicalize_gender_value(value)

    labels = {
        "female": "Female",
        "male": "Male",
        "non_binary": "Non-binary",
        "prefer_not_to_say": "Prefer not to say",
    }

    return labels.get(canonical, "")