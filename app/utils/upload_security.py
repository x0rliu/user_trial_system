# app/utils/upload_security.py

from pathlib import Path
import re


CSV_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


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

    return safe_filename