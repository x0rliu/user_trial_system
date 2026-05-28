# app/utils/upload_security.py

from pathlib import Path
import re


CSV_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
CSV_UPLOAD_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/x-csv",
    "text/x-csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}


def _normalize_content_type(content_type):
    return str(content_type or "").split(";", 1)[0].strip().lower()


def sanitize_upload_filename(filename, *, fallback="upload.csv", max_length=120):
    """
    Return a safe display/storage filename.

    This strips path components, removes dangerous characters, and keeps only
    a conservative filename character set.
    """

    raw = str(filename or fallback).strip()
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = Path(raw).name.strip()

    if not raw:
        raw = fallback

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
    safe = safe.strip("._")

    if not safe:
        safe = fallback

    return safe[:max_length]


def require_csv_upload(
    *,
    filename,
    file_bytes,
    content_type=None,
    max_bytes=CSV_UPLOAD_MAX_BYTES,
):
    """
    Validate a CSV upload and return the sanitized filename.

    Raises ValueError with a safe user-facing message.
    """

    safe_filename = sanitize_upload_filename(filename)

    if not safe_filename.lower().endswith(".csv"):
        raise ValueError("Only CSV uploads are allowed.")

    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    if len(file_bytes) > max_bytes:
        raise ValueError("Uploaded file is too large.")

    normalized_content_type = _normalize_content_type(content_type)
    if (
        normalized_content_type
        and normalized_content_type not in CSV_UPLOAD_ALLOWED_CONTENT_TYPES
    ):
        raise ValueError("Uploaded file type is not allowed.")

    return safe_filename