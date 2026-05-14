# app/utils/external_redirects.py

from urllib.parse import urlparse


ALLOWED_EXTERNAL_SURVEY_REDIRECT_HOSTS = {
    "docs.google.com",
    "forms.gle",
}


def is_allowed_external_survey_redirect(url: str) -> bool:
    """
    Validate external survey redirects before sending a user to a DB-provided URL.

    This prevents poisoned survey links from becoming an open redirect.
    """
    parsed = urlparse(str(url or "").strip())

    if parsed.scheme != "https":
        return False

    hostname = (parsed.hostname or "").lower()

    return hostname in ALLOWED_EXTERNAL_SURVEY_REDIRECT_HOSTS