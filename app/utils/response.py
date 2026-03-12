import json


def json_response(payload, status=200):
    """
    Minimal JSON response helper.

    Returns a (status, headers, body) tuple.
    No state.
    No side effects.
    No assumptions.
    """
    return (
        status,
        {"Content-Type": "application/json"},
        json.dumps(payload)
    )
