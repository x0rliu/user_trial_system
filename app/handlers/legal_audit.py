# app/handlers/legal_audit.py

from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

from app.db.legal_documents import (
    get_legal_document_audit_event_rows,
    get_legal_document_audit_rows,
)
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



def _event_type_label(event_type: str | None) -> str:
    clean_event_type = str(event_type or "").strip()
    if not clean_event_type:
        return "Unknown Event"
    return clean_event_type.replace("_", " ").title()


def _actor_display(event: dict) -> str:
    display_name = (event.get("actor_name") or "").strip()
    email = (event.get("actor_email") or "").strip()
    user_id = (event.get("actor_user_id") or "").strip()

    if display_name and email:
        return f"{display_name} ({email})"
    if display_name:
        return display_name
    if email:
        return email
    return user_id or "—"


def _source_document_display(event: dict) -> str:
    source_document_id = event.get("source_document_id")
    if not source_document_id:
        return "—"

    title = _display_title(event.get("source_document_title") or "")
    version = event.get("source_document_version") or "?"

    if title:
        return f"#{source_document_id} · {title} v{version}"

    return f"#{source_document_id} · v{version}"


def _group_events_by_document_id(events: list[dict]) -> dict[int, list[dict]]:
    grouped = {}

    for event in events:
        try:
            document_id = int(event.get("document_id"))
        except (TypeError, ValueError):
            continue

        if document_id not in grouped:
            grouped[document_id] = []
        grouped[document_id].append(event)

    return grouped


def _render_event_log(document_id: int, events_by_document_id: dict[int, list[dict]]) -> str:
    events = events_by_document_id.get(int(document_id), [])

    if not events:
        return """
        <div class="legal-audit-event-empty">
            No detailed audit events have been recorded for this version yet.
        </div>
        """

    event_items = []
    for event in events:
        main_change = str(event.get("main_change") or "").strip() or "—"
        event_notes = str(event.get("event_notes") or "").strip()

        notes_html = ""
        if event_notes:
            notes_html = f"""
            <div class="legal-audit-event-notes">
                {e(event_notes)}
            </div>
            """

        event_items.append(
            f"""
            <li class="legal-audit-event-item">
                <div class="legal-audit-event-main">
                    <span class="legal-audit-event-type">{e(_event_type_label(event.get("event_type")))}</span>
                    <span class="legal-audit-event-time">{e(_format_datetime(event.get("event_at")))}</span>
                </div>
                <dl class="legal-audit-event-meta">
                    <div>
                        <dt>Actor</dt>
                        <dd>{e(_actor_display(event))}</dd>
                    </div>
                    <div>
                        <dt>Source</dt>
                        <dd>{e(_source_document_display(event))}</dd>
                    </div>
                    <div>
                        <dt>Main Change</dt>
                        <dd>{e(main_change)}</dd>
                    </div>
                </dl>
                {notes_html}
            </li>
            """
        )

    return f"""
    <ol class="legal-audit-event-list">
        {''.join(event_items)}
    </ol>
    """


def _group_rows_by_document_type(rows: list[dict]) -> OrderedDict:
    grouped = OrderedDict()

    for row in rows:
        document_type = row.get("document_type") or "unknown"
        if document_type not in grouped:
            grouped[document_type] = []
        grouped[document_type].append(row)

    return grouped


def _render_audit_row(row: dict, events_by_document_id: dict[int, list[dict]]) -> str:
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
    <tr class="legal-audit-events-row">
        <td colspan="9">
            <details class="legal-audit-events-detail">
                <summary>Audit event log</summary>
                {_render_event_log(int(document_id), events_by_document_id)}
            </details>
        </td>
    </tr>
    """


def _render_audit_groups(rows: list[dict], events_by_document_id: dict[int, list[dict]]) -> str:
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
        table_rows = "".join(_render_audit_row(row, events_by_document_id) for row in document_rows)

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
    document_ids = [int(row["id"]) for row in rows if row.get("id")]
    event_rows = get_legal_document_audit_event_rows(document_ids)
    events_by_document_id = _group_events_by_document_id(event_rows)

    html = LEGAL_AUDIT_TEMPLATE
    html = html.replace("__AUDIT_GROUPS__", _render_audit_groups(rows, events_by_document_id))
    html = html.replace("__AUDIT_DOCUMENT_COUNT__", e(len(_group_rows_by_document_type(rows))))
    html = html.replace("__AUDIT_REVISION_COUNT__", e(len(rows)))
    html = html.replace("__AUDIT_EVENT_COUNT__", e(len(event_rows)))

    return {"html": html}