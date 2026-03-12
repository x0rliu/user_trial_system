# app/cache/product_cache.py

import uuid
from datetime import datetime
from app.cache.simple_cache import cache
import json
from pathlib import Path


# existing product-related cache helpers

# In-memory cache (swap later if needed)
_PRODUCT_DRAFT_CACHE: dict[str, dict[str, dict]] = {}

# NOTE: legacy draft cache (not used by Request Trial wizard)

def create_product_draft(*, user_id: str) -> str:
    draft_id = uuid.uuid4().hex

    _PRODUCT_DRAFT_CACHE.setdefault(user_id, {})
    _PRODUCT_DRAFT_CACHE[user_id][draft_id] = {
        "status": "draft",
        "created_at": datetime.utcnow().isoformat(),
        "basics": {},
        "timing": {},
        "stakeholders": {},
    }

    return draft_id


def get_product_draft(*, user_id: str, draft_id: str) -> dict | None:
    return _PRODUCT_DRAFT_CACHE.get(user_id, {}).get(draft_id)


def list_product_drafts_for_user(*, user_id: str) -> list[str]:
    return list(_PRODUCT_DRAFT_CACHE.get(user_id, {}).keys())

TRIAL_PROJECT_PREFIX = "trial_project"


def create_empty_trial_project(*, created_by: str) -> str:
    project_id = str(uuid.uuid4())
    cache_key = f"{TRIAL_PROJECT_PREFIX}:{project_id}"

    project = {
        "project_id": project_id,
        "created_by": created_by,
        "status": "draft",

        # wizard steps
        "basics": {},
        "timing_scope": {},
        "stakeholders": {},

        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # PRIMARY: cache
    cache.set(cache_key, project)

    # SECONDARY: JSON (dev only)
    from app.config.config import USE_TRIAL_FILE_FALLBACK
    if USE_TRIAL_FILE_FALLBACK:
        _save_trial_project_to_file(project_id, project)

    return project_id


def get_trial_project(project_id: str) -> dict | None:
    from app.cache.simple_cache import cache
    from app.config.config import USE_TRIAL_FILE_FALLBACK

    cache_key = f"{TRIAL_PROJECT_PREFIX}:{project_id}"
    project = cache.get(cache_key)
    if project:
        # Allow returning the mirror even if DB is authoritative.
        # (Authoritativeness is tracked in _authority; caller can decide behavior.)
        return project

    if not USE_TRIAL_FILE_FALLBACK:
        return None

    project = _load_trial_project_from_file(project_id)
    if not project:
        return None

    # Allow returning the mirror even if DB is authoritative.
    return project


def save_trial_project(project_id: str, project: dict) -> None:
    from app.cache.simple_cache import cache
    from app.config.config import USE_TRIAL_FILE_FALLBACK

    cache_key = f"{TRIAL_PROJECT_PREFIX}:{project_id}"

    authority = project.get("_authority", {})
    sot = authority.get("sot")

    # --------------------------------------------------
    # If DB is now authoritative, purge in-memory cache
    # --------------------------------------------------
    if sot == "database":
        cache.delete(cache_key)
    else:
        cache.set(cache_key, project)

    # --------------------------------------------------
    # JSON file is retained for audit only
    # --------------------------------------------------
    if USE_TRIAL_FILE_FALLBACK:
        _save_trial_project_to_file(project_id, project)


def _project_file_path(project_id: str) -> Path:
    return Path("app/dev_data/trial_projects") / f"project_{project_id}.json"

def _load_trial_project_from_file(project_id: str) -> dict | None:
    path = _project_file_path(project_id)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_trial_project_to_file(project_id: str, project: dict) -> None:
    path = _project_file_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(project, f, indent=2)

# app/cache/product_cache.py

from pathlib import Path
import json
from app.config.config import USE_TRIAL_FILE_FALLBACK

TRIAL_PROJECT_PREFIX = "trial_project"


def list_trial_projects_for_user(*, user_id: str) -> list[dict]:
    """
    Returns all trial projects created by this user.
    Source of truth:
    - JSON files (dev)
    - cache-only in prod later
    """

    projects = []

    if not USE_TRIAL_FILE_FALLBACK:
        # cache is write-through only, not enumerable
        return projects

    base_path = Path("app/dev_data/trial_projects")
    if not base_path.exists():
        return projects

    for path in base_path.glob("project_*.json"):
        with path.open("r", encoding="utf-8") as f:
            project = json.load(f)

        if project.get("created_by") == user_id:
            projects.append(project)

    return projects

def delete_trial_project(project_id: str) -> None:
    """
    Permanently remove a trial project draft from cache and dev JSON.
    Used after authoritative DB submission.
    """
    cache_key = f"{TRIAL_PROJECT_PREFIX}:{project_id}"

    # Remove from in-memory cache
    cache.delete(cache_key)

    # Remove dev JSON mirror if present
    if USE_TRIAL_FILE_FALLBACK:
        path = _project_file_path(project_id)
        if path.exists():
            path.unlink()
