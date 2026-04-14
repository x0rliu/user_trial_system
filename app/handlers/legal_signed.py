# app/handlers/legal_signed.py

from html import escape
from app.db.legal_documents import get_document_by_id
from app.db.user_legal_acceptance import get_user_signed_document
from app.utils.html_escape import escape_html as e
from bs4 import BeautifulSoup

def render_signed_legal_document(*, document_type: str, user_id: str):

    acceptance = get_user_signed_document(
        user_id=user_id,
        document_type=document_type,
    )

    if not acceptance:
        return {
            "html": _render_missing_acceptance(document_type)
        }

    document = get_document_by_id(acceptance["document_id"])

    if not document:
        return {
            "html": _render_missing_acceptance(document_type)
        }

    # Safety guard — ensure document type matches expected
    if document.get("document_type") != document_type:
        return {
            "html": _render_missing_acceptance(document_type)
        }

    return {
        "html": _render_document(document, acceptance)
    }


def _render_document(doc: dict, acceptance: dict):

    title = e(doc.get("title", "Legal Document"))
    doc_type = e(doc.get("document_type", "").replace("_", " ").title())
    version = e(str(doc.get("version", "")))
    signed_date = e(str(acceptance.get("accepted_at", "")))

    # --------------------------------
    # Sanitize content (same pattern as PDF)
    # --------------------------------
    raw_content = doc.get("content", "")
    soup = BeautifulSoup(raw_content, "html.parser")

    allowed_tags = {
        "p",
        "h1",
        "h2",
        "h3",
        "ul",
        "ol",
        "li",
        "strong",
        "em"
    }

    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
        tag.attrs = {}

    content = str(soup)

    doc_id = e(doc.get("id"))

    return f"""
<div class="legal-document">

<h1>{title}</h1>

<div class="legal-meta">
<strong>Document:</strong> {doc_type}<br>
<strong>Version Signed:</strong> {version}<br>
<strong>Signed On:</strong> {signed_date}
</div>

<div class="legal-actions">
<a href="/legal/download?document_id={doc_id}&accepted_at={signed_date}" class="btn">
Download Signed Copy
</a>
</div>

<hr>

<div class="legal-content">
{content}
</div>

</div>
"""


def _render_missing_acceptance(document_type):

    return f"""
<div class="legal-document">

<h1>No Signed Document Found</h1>

<p>You have not signed:</p>

<code>{e(document_type)}</code>

</div>
"""