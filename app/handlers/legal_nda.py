from app.utils.templates import render_template
from app.db.user_legal_acceptance import get_user_signed_document


def render_legal_nda(user_id):

    nda = get_user_signed_document(user_id, "nda")

    if nda:
        signed_date = nda["signed_at"]
        document_id = nda["document_id"]

        return render_template(
            "legal/nda_signed.html",
            signed_date=signed_date,
            document_id=document_id
        )

    return render_template(
        "legal/nda_unsigned.html"
    )