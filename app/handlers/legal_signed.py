# app/handlers/legal_signed.py

from app.db.legal_documents import get_document_by_id, get_latest_published_document
from app.db.user_legal_acceptance import get_user_signed_document
from app.db.user_pool import get_user_by_userid
from app.utils.html_escape import escape_html as e
from bs4 import BeautifulSoup


def render_signed_legal_document(*, document_type: str, user_id: str):

    acceptance = get_user_signed_document(
        user_id=user_id,
        document_type=document_type,
    )

    if acceptance:
        document = get_document_by_id(acceptance["document_id"])
    elif document_type == "nda":
        legacy_result = _get_legacy_global_nda_record(user_id)

        if not legacy_result:
            return {
                "html": _render_missing_acceptance(document_type)
            }

        document = legacy_result["document"]
        acceptance = legacy_result["acceptance"]
    else:
        return {
            "html": _render_missing_acceptance(document_type)
        }

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


def _get_legacy_global_nda_record(user_id: str) -> dict | None:
    """
    Supports older global NDA records that predate user_legal_acceptance.

    DB source of truth for the legacy state is user_pool.GlobalNDA_Status and
    user_pool.GlobalNDA_SignedAt. When GlobalNDA_Version is missing, the current
    active NDA is used for display because no document_id was captured.
    """

    user = get_user_by_userid(user_id)
    if not user:
        return None

    if user.get("GlobalNDA_Status") != "Signed" or not user.get("GlobalNDA_SignedAt"):
        return None

    document = get_latest_published_document("nda")
    if not document:
        return None

    signed_version = (user.get("GlobalNDA_Version") or "").strip()
    document_version = str(document.get("version") or "").strip()

    if signed_version and signed_version != document_version:
        return None

    return {
        "document": document,
        "acceptance": {
            "document_id": document.get("id"),
            "document_type": "nda",
            "accepted_at": user.get("GlobalNDA_SignedAt"),
        },
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
<a href="/legal/download/{doc_id}" class="btn">
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