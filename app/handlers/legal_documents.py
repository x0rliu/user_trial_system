# app/handlers/legal_documents.py

from pathlib import Path
from app.db.legal_documents import (
    get_latest_published_document,
    get_active_documents,
    get_draft_documents,
    get_archived_documents,
    get_document_by_id,
    get_active_document_review_statuses,
    record_legal_document_review,
)
from datetime import datetime
from html.parser import HTMLParser
from app.utils.html_escape import escape_html as e
from app.utils.csrf import generate_csrf_token

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


def _review_state_label(review_state: str | None) -> str:
    labels = {
        "current": "Review current",
        "due_soon": "Review due soon",
        "overdue": "Review overdue",
        "never_reviewed": "Never reviewed",
    }

    return labels.get(review_state or "", "Review unknown")


def _review_state_class(review_state: str | None) -> str:
    allowed = {"current", "due_soon", "overdue", "never_reviewed"}
    state = review_state if review_state in allowed else "unknown"
    return f"review-{state}"


def _build_review_panel(selected_doc: dict | None, selected_review: dict | None) -> str:
    if not selected_doc or selected_doc.get("status") != "active":
        return ""

    review_state = selected_review.get("review_state") if selected_review else "never_reviewed"
    last_reviewed_at = selected_review.get("last_reviewed_at") if selected_review else None
    review_due_at = selected_review.get("review_due_at") if selected_review else None

    last_reviewed = _format_date(last_reviewed_at)
    review_due = _format_date(review_due_at)

    return f"""
    <section class="legal-review-panel {_review_state_class(review_state)}">
        <div>
            <div class="legal-review-label">Annual legal review</div>
            <div class="legal-review-status">{e(_review_state_label(review_state))}</div>
        </div>

        <div class="legal-review-meta">
            <span>Last reviewed: {e(last_reviewed)}</span>
            <span>Next due: {e(review_due)}</span>
        </div>
    </section>
    """


def _build_review_action(selected_doc: dict | None) -> str:
    if not selected_doc or selected_doc.get("status") != "active":
        return ""

    return """
    <form class="legal-review-action" method="post" action="/legal/documents/review">
        <input type="hidden" name="csrf_token" value="__CSRF_TOKEN__">
        <input type="hidden" name="document_id" value="__DOC_ID__">
        <button class="legal-button review" type="submit">
            Mark Reviewed
        </button>
        <span class="legal-review-action-note">
            Use only when Legal has reviewed this active version and no content change is needed.
        </span>
    </form>
    """


class _LegalHtmlSanitizer(HTMLParser):
    """
    Conservative allowlist sanitizer for legal-document rich HTML.

    Legal documents are edited by privileged users, but the stored HTML is still
    treated as untrusted before browser rendering.
    """

    ALLOWED_TAGS = {
        "a", "b", "blockquote", "br", "div", "em", "h1", "h2", "h3", "h4",
        "i", "li", "ol", "p", "span", "strong", "table", "tbody", "td",
        "th", "thead", "tr", "u", "ul",
    }

    ALLOWED_ATTRS = {
        "a": {"href", "title", "target", "rel"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def _safe_href(self, value: str) -> str:
        href = str(value or "").strip()
        lowered = href.lower()

        if not href:
            return ""
        if lowered.startswith(("javascript:", "data:", "vbscript:")):
            return ""
        if href.startswith(("/", "#")):
            return href
        if lowered.startswith(("http://", "https://", "mailto:", "tel:")):
            return href

        return ""

    def _safe_attrs(self, tag: str, attrs) -> str:
        allowed = self.ALLOWED_ATTRS.get(tag, set())
        safe_attrs = []

        for raw_name, raw_value in attrs:
            name = str(raw_name or "").strip().lower()
            value = str(raw_value or "").strip()

            if name.startswith("on"):
                continue
            if name not in allowed:
                continue

            if tag == "a" and name == "href":
                value = self._safe_href(value)
                if not value:
                    continue

            if tag == "a" and name == "target":
                if value not in {"_blank", "_self"}:
                    continue
                safe_attrs.append('rel="noopener noreferrer"')

            safe_attrs.append(f'{name}="{e(value)}"')

        return (" " + " ".join(safe_attrs)) if safe_attrs else ""

    def handle_starttag(self, tag, attrs):
        tag = str(tag or "").lower()
        if tag not in self.ALLOWED_TAGS:
            return

        self.parts.append(f"<{tag}{self._safe_attrs(tag, attrs)}>")

    def handle_endtag(self, tag):
        tag = str(tag or "").lower()
        if tag not in self.ALLOWED_TAGS or tag == "br":
            return

        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(e(data))

    def handle_entityref(self, name):
        self.parts.append(e(f"&{name};"))

    def handle_charref(self, name):
        self.parts.append(e(f"&#{name};"))


def _sanitize_legal_html(content: str | None) -> str:
    sanitizer = _LegalHtmlSanitizer()
    sanitizer.feed(str(content or ""))
    sanitizer.close()
    return "".join(sanitizer.parts)

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
        "html": _sanitize_legal_html(doc["content"])
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
    review_statuses = get_active_document_review_statuses()

    selected_doc = None

    if doc_id is not None:
        try:
            doc_id = int(doc_id)
        except (TypeError, ValueError):
            return {"redirect": "/legal/documents"}

        selected_doc = get_document_by_id(doc_id)
        if not selected_doc:
            return {"redirect": "/legal/documents"}

    if not selected_doc:
        if draft_docs:
            selected_doc = draft_docs[0]
        elif active_docs:
            selected_doc = active_docs[0]

    selected_review = None
    if selected_doc:
        selected_doc_id = int(selected_doc["id"])
        for review_status in review_statuses:
            if int(review_status.get("id") or 0) == selected_doc_id:
                selected_review = review_status
                break

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

    csrf_token = generate_csrf_token(user_id)

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
        e(_sanitize_legal_html(selected_doc["content"])) if selected_doc else "",
    )

    html = html.replace(
        "__LEGAL_REVIEW_PANEL__",
        _build_review_panel(selected_doc, selected_review),
    )

    html = html.replace(
        "__LEGAL_ACTIONS__",
        legal_actions,
    )

    html = html.replace(
        "__LEGAL_REVIEW_ACTION__",
        _build_review_action(selected_doc),
    )

    html = html.replace(
        "__CSRF_TOKEN__",
        e(csrf_token),
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

    document_id = _scalar(data.get("document_id"))
    content = _scalar(data.get("content"))

    if not document_id or not content:
        return {"ok": False, "error": "Missing document_id or content"}

    try:
        document_id = int(document_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Invalid document_id"}

    content = _sanitize_legal_html(content.strip())

    if not document_id or not content:
        return {"ok": False, "error": "Missing document_id or content"}

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

    try:
        document_id = int(document_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Invalid document_id"}

    content = _sanitize_legal_html(content.strip())

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


# ==============================
# Review Legal Document (Legal)
# ==============================

def handle_review_legal_document(user_id: str, data: dict) -> dict:
    document_id = _scalar(data.get("document_id"))

    try:
        document_id = int(document_id)
    except (TypeError, ValueError):
        return {"redirect": "/legal/documents?error=invalid_document"}

    try:
        record_legal_document_review(
            document_id=document_id,
            reviewed_by_user_id=user_id,
        )
    except RuntimeError:
        return {"redirect": f"/legal/documents/{document_id}?error=review_failed"}

    return {"redirect": f"/legal/documents/{document_id}?review=marked"}