# app/handlers/legal_audit.py

from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

from app.db.legal_documents import get_legal_document_audit_rows
from app.utils.html_escape import escape_html as e


LEGAL_AUDIT_TEMPLATE = Path(
    "app/templates/legal/audit.html"
).read_text(encoding="utf-8")


def _display_title(title: str) -> str:
    prefixes = (
        "Logitech User Trials – ",
        "Logitech User Trials ",
    )

    clean_title = str(title or "").strip()
    for prefix in prefixes:
        if clean_title.startswith(prefix):
            return clean_title[len(prefix):]

    return clean_title or "Untitled document"


def _format_datetime(value) -> str:
    if not value:
        return "—"

    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y %H:%M")

    if isinstance(value, date):
        return value.strftime("%b %d, %Y")

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).strftime("%b %d, %Y %H:%M")
        except ValueError:
            continue

    return str(value)


def _status_class(status: str | None) -> str:
    safe_status = str(status or "unknown").strip().lower()
    if safe_status not in {"active", "draft", "archived"}:
        safe_status = "unknown"
    return f"status-{safe_status}"


def _modified_by(row: dict) -> str:
    display_name = (row.get("modified_by_name") or "").strip()
    email = (row.get("modified_by_email") or "").strip()
    user_id = (row.get("modified_by_user_id") or "").strip()

    if display_name and email:
        return f"{display_name} ({email})"
    if display_name:
        return display_name
    if email:
        return email
    return user_id or "—"


def _modified_from(row: dict) -> str:
    supersedes_id = row.get("supersedes_id")
    if not supersedes_id:
        return "—"

    supersedes_title = _display_title(row.get("supersedes_title") or "")
    supersedes_version = row.get("supersedes_version") or "?"

    if supersedes_title:
        return f"#{supersedes_id} · {supersedes_title} v{supersedes_version}"

    return f"#{supersedes_id} · v{supersedes_version}"


def _main_change(row: dict) -> str:
    main_change = str(row.get("main_change") or "").strip()
    if main_change:
        return main_change

    latest_event_type = str(row.get("latest_event_type") or "").strip()
    if latest_event_type:
        return latest_event_type.replace("_", " ").title()

    return "—"


def _group_rows_by_document_type(rows: list[dict]) -> OrderedDict:
    grouped = OrderedDict()

    for row in rows:
        document_type = row.get("document_type") or "unknown"
        if document_type not in grouped:
            grouped[document_type] = []
        grouped[document_type].append(row)

    return grouped


def _render_audit_row(row: dict) -> str:
    document_id = row.get("id")
    title = _display_title(row.get("title"))
    version = row.get("version") or "—"
    status = row.get("status") or "unknown"

    return f"""
    <tr>
        <td class="audit-uid">#{e(document_id)}</td>
        <td>{e(title)}</td>
        <td>v{e(version)}</td>
        <td>
            <span class="legal-meta-pill {_status_class(status)}">{e(str(status).title())}</span>
        </td>
        <td>{e(_modified_from(row))}</td>
        <td>{e(_main_change(row))}</td>
        <td>{e(_modified_by(row))}</td>
        <td>{e(_format_datetime(row.get("modified_at")))}</td>
        <td>
            <a class="audit-action-link" href="/legal/documents/{e(document_id)}">Open</a>
        </td>
    </tr>
    """


def _render_audit_groups(rows: list[dict]) -> str:
    if not rows:
        return """
        <section class="legal-audit-empty">
            No legal document history was found.
        </section>
        """

    cards = []
    grouped = _group_rows_by_document_type(rows)

    for document_type, document_rows in grouped.items():
        first_row = document_rows[0]
        display_title = _display_title(first_row.get("title"))
        safe_document_type = e(document_type)
        table_rows = "".join(_render_audit_row(row) for row in document_rows)

        cards.append(
            f"""
            <section class="legal-audit-card">
                <header class="legal-audit-card-header">
                    <div>
                        <h2>{e(display_title)}</h2>
                        <div class="legal-audit-card-meta">Document type: {safe_document_type}</div>
                    </div>
                    <div class="legal-audit-version-count">
                        {len(document_rows)} version{'s' if len(document_rows) != 1 else ''}
                    </div>
                </header>

                <div class="legal-audit-table-wrap">
                    <table class="legal-audit-table">
                        <thead>
                            <tr>
                                <th>UID</th>
                                <th>Document Name</th>
                                <th>Version</th>
                                <th>Status</th>
                                <th>Modified From Document</th>
                                <th>Main Change</th>
                                <th>Modified By</th>
                                <th>Modified At</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </section>
            """
        )

    return "".join(cards)


def render_legal_audit_index(user_id: str) -> dict:
    """
    Render the read-only Legal Document Audit page.
    """

    rows = get_legal_document_audit_rows()

    html = LEGAL_AUDIT_TEMPLATE
    html = html.replace("__AUDIT_GROUPS__", _render_audit_groups(rows))
    html = html.replace("__AUDIT_DOCUMENT_COUNT__", e(len(_group_rows_by_document_type(rows))))
    html = html.replace("__AUDIT_REVISION_COUNT__", e(len(rows)))

    return {"html": html}