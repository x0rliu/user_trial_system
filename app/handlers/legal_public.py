from html import escape
from app.db.legal_documents import get_latest_published_document


def render_signed_legal_document(*, document_type: str, user_id=None):
    """
    Render the latest published legal document.
    """

    document = get_latest_published_document(document_type)

    if not document:
        return {
            "html": _render_missing_document(document_type)
        }

    return {
        "html": _render_document(document)
    }


def _render_document(doc: dict) -> str:

    title = escape(doc.get("title", "Legal Document"))
    version = escape(str(doc.get("version", "")))
    effective_date = escape(str(doc.get("effective_date", "")))
    content = doc.get("content", "")

    return f"""
<div class="legal-document">

<h1>{title}</h1>

<div class="legal-meta">
<strong>Version:</strong> {version}<br>
<strong>Effective:</strong> {effective_date}
</div>

<hr>

<div class="legal-content">
{content}
</div>

</div>
"""


def _render_missing_document(document_type: str) -> str:

    return f"""
<div class="legal-document">

<h1>Document Not Found</h1>

<p>No published document exists for:</p>

<code>{escape(document_type)}</code>

</div>
"""