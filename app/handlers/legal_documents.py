# app/handlers/legal_documents.py

from pathlib import Path
from app.db.legal_documents import (
    get_latest_published_document,
    get_active_documents,
    get_draft_documents,
    get_archived_documents,
    get_document_by_id,
)
from datetime import datetime
from app.utils.html_escape import escape_html as e

# ==============================
# Templates
# ==============================

DOCUMENTS_INDEX_TEMPLATE = Path(
    "app/templates/legal/documents.html"
).read_text(encoding="utf-8")


# ==============================
# Helpers
# ==============================

def _scalar(value):
    if isinstance(value, list):
        return value[0]
    return value

def _render_docs_list(docs: list[dict]) -> str:
    items = []

    for doc in docs:
        raw_title = _display_title(doc["title"])
        title = e(raw_title)

        version = f"v{doc['version']}"
        date = _format_date(doc["effective_date"])

        if doc["status"] == "draft":
            meta = f"{version} · Draft"
        elif doc["status"] == "active":
            meta = f"{version} · Effective {date}"
        elif doc["status"] == "archived":
            meta = f"{version} · Archived {date}"
        else:
            meta = version

        safe_meta = e(meta)
        doc_id = e(doc["id"])

        items.append(
            f"""
            <a class="rail-item" href="/legal/documents/{doc_id}">
                <div class="rail-title">{title}</div>
                <div class="rail-meta">{safe_meta}</div>
            </a>
            """
        )

    return "".join(items)

def _display_title(title: str) -> str:
    PREFIXES = (
        "Logitech User Trials – ",
        "Logitech User Trials ",
    )

    for prefix in PREFIXES:
        if title.startswith(prefix):
            return title[len(prefix):]

    return title

def _format_date(value) -> str:
    """
    Accepts date/datetime/string from MySQL and formats consistently.
    """
    if not value:
        return "—"

    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y")

    # MySQL may return date or string depending on connector
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return str(value)

# ==============================
# Public legal document view
# ==============================

def render_legal_document_view(document_type: str, user_id: str | None) -> dict:
    """
    Public-facing legal document view.
    Always renders the latest *published* document for a document_type.
    """

    doc = get_latest_published_document(document_type)

    if not doc:
        return {
            "html": "<p>No published document found.</p>"
        }

    return {
        "html": doc["content"]
    }


# ==============================
# Legal editor index (admin)
# ==============================

def render_legal_documents_index(user_id: str, doc_id: int | None = None) -> dict:
    """
    Editor view: left rail + editor.
    """

    active_docs = get_active_documents()
    draft_docs = get_draft_documents()
    archived_docs = get_archived_documents()

    selected_doc = None

    if doc_id:
        selected_doc = get_document_by_id(doc_id)

    if not selected_doc:
        if draft_docs:
            selected_doc = draft_docs[0]
        elif active_docs:
            selected_doc = active_docs[0]

    # ------------------------------
    # Determine legal actions block
    # ------------------------------
    if selected_doc and selected_doc["status"] != "archived":
        legal_actions = """
        <div class="legal-actions">
            <button class="legal-button secondary" type="submit">
                Save Draft
            </button>

            <button class="legal-button primary" id="publish-doc" type="button">
                Publish
            </button>
        </div>
        """
    else:
        # Archived = read-only
        legal_actions = """
        <div class="legal-readonly-note">
            Archived documents are read-only.
        </div>
        """

    doc_status = selected_doc["status"] if selected_doc else ""
    doc_status_class = f"status-{doc_status}" if doc_status else "status-unknown"

    html = DOCUMENTS_INDEX_TEMPLATE

    html = html.replace("__ACTIVE_DOCS__", _render_docs_list(active_docs))
    html = html.replace("__DRAFT_DOCS__", _render_docs_list(draft_docs))
    html = html.replace("__ARCHIVED_DOCS__", _render_docs_list(archived_docs))

    html = html.replace(
        "__DOC_TITLE__",
        e(selected_doc["title"]) if selected_doc else "No document selected",
    )

    html = html.replace(
        "__DOC_ID__",
        e(str(selected_doc["id"])) if selected_doc else "",
    )

    html = html.replace(
        "__DOC_TYPE__",
        e(selected_doc["document_type"]) if selected_doc else "",
    )

    html = html.replace(
        "__VERSION__",
        e(str(selected_doc["version"])) if selected_doc else "",
    )

    html = html.replace(
        "__DOC_STATUS__",
        e(doc_status.title()) if doc_status else "Unknown",
    )

    html = html.replace(
        "__DOC_STATUS_CLASS__",
        e(doc_status_class),
    )

    html = html.replace(
        "__EDITOR_CONTENT__",
        selected_doc["content"] if selected_doc else "",
    )

    html = html.replace(
        "__LEGAL_ACTIONS__",
        legal_actions,
    )

    return {"html": html}


# ==============================
# Save Legal Draft (Legal)
# ==============================

def handle_save_legal_draft(user_id: str, data: dict) -> dict:
    from app.db.legal_documents import (
        get_document_by_id,
        save_draft_document,
        update_existing_draft,
    )

    print("SAVE PAYLOAD:", data)

    document_id = _scalar(data.get("document_id"))
    content = _scalar(data.get("content"))

    if not document_id or not content:
        print("SAVE REJECTED:", document_id, repr(content))
        return {"ok": False, "error": "Missing document_id or content"}

    document_id = int(document_id)
    content = content.strip()

    if not document_id or not content:
        return {"ok": False, "error": "Missing document_id or content"}

    document_id = int(document_id)
    content = content.strip()

    doc = get_document_by_id(document_id)

    if not doc:
        return {"ok": False, "error": "Document not found"}

    if doc["status"] == "active":
        # Editing published → create/update draft
        new_id = save_draft_document(
            document_id=document_id,
            content=content,
            user_id=user_id,
        )

        return {
            "ok": True,
            "document_id": new_id,
        }


    elif doc["status"] == "draft":
        # Editing draft → update draft directly
        update_existing_draft(
            draft_id=document_id,
            content=content,
            user_id=user_id,
        )

    else:
        return {
            "ok": False,
            "error": f"Cannot save document in status {doc['status']}",
        }

    return {"ok": True}

def handle_publish_legal_document(user_id: str, data: dict) -> dict:
    from app.db.legal_documents import (
        get_document_by_id,
        save_draft_document,
        update_existing_draft,
        publish_draft,
    )

    document_id = data.get("document_id")
    content = data.get("content")

    if not document_id or not content:
        return {"ok": False, "error": "Missing document_id or content"}

    document_id = int(document_id)
    content = content.strip()

    doc = get_document_by_id(document_id)
    if not doc:
        return {"ok": False, "error": "Document not found"}

    # -------------------------
    # Ensure draft exists
    # -------------------------
    if doc["status"] == "active":
        draft_id = save_draft_document(
            document_id=document_id,
            content=content,
            user_id=user_id,
        )

    elif doc["status"] == "draft":
        update_existing_draft(
            draft_id=document_id,
            content=content,
            user_id=user_id,
        )
        draft_id = document_id

    else:
        return {"ok": False, "error": f"Cannot publish status {doc['status']}"}

    # -------------------------
    # Publish draft
    # -------------------------
    new_active_id = publish_draft(
        draft_id=draft_id,
        user_id=user_id,
    )

    return {"ok": True, "active_id": new_active_id}
