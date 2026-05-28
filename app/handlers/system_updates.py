# app/handlers/system_updates.py

from pathlib import Path
import re

from app.utils.html_escape import escape_html as e

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_UPDATES_PERMISSION_LEVELS = {60, 70, 80, 100}  # Management, UT Lead, IT Admin, Admin
CHANGELOG_PATH = PROJECT_ROOT / "docs" / "changelog.md"
_ENTRY_RE = re.compile(r"^###\s+(?P<date>\d{4}-\d{2}-\d{2})\s+—\s+(?P<title>.+?)\s*$")
_SECTION_RE = re.compile(r"^>\s+\*\*(?P<label>.+?)\*\*")


def _require_system_updates_access(user_id: str):
    from app.db.user_roles import get_effective_permission_level

    permission_level = get_effective_permission_level(user_id)
    if permission_level not in SYSTEM_UPDATES_PERMISSION_LEVELS:
        return {"redirect": "/dashboard"}
    return None


def _clean_blockquote_line(line: str) -> str:
    raw = line.rstrip("\n")
    if raw.startswith(">"):
        raw = raw[1:]
    return raw.strip()


def _parse_changelog_entries(raw_markdown: str) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    current_section: str | None = None

    for line in raw_markdown.splitlines():
        entry_match = _ENTRY_RE.match(line)
        if entry_match:
            if current:
                entries.append(current)

            current = {
                "heading": line.strip(),
                "date": entry_match.group("date"),
                "title": entry_match.group("title"),
                "sections": {},
            }
            current_section = None
            continue

        if current is None:
            continue

        section_match = _SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group("label").strip()
            current["sections"].setdefault(current_section, [])
            continue

        if current_section:
            current["sections"].setdefault(current_section, []).append(
                _clean_blockquote_line(line)
            )

    if current:
        entries.append(current)

    return entries


def _count_bullets(entry: dict, label: str) -> int:
    lines = entry.get("sections", {}).get(label, [])
    return sum(1 for line in lines if line.strip().startswith("- "))


def _render_section_html(entry: dict, label: str, *, empty_text: str = "None listed.") -> str:
    lines = entry.get("sections", {}).get(label, [])
    html: list[str] = []
    bullets: list[str] = []

    def flush_bullets():
        nonlocal bullets
        if not bullets:
            return
        html.append("<ul>")
        for bullet in bullets:
            html.append(f"<li>{e(bullet)}</li>")
        html.append("</ul>")
        bullets = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_bullets()
            continue

        if line.startswith("- "):
            bullets.append(line[2:].strip())
            continue

        flush_bullets()
        html.append(f"<p>{e(line)}</p>")

    flush_bullets()

    if not html:
        return f"<p class='system-updates-muted'>{e(empty_text)}</p>"

    return "\n".join(html)


def _render_audience_cards() -> str:
    cards = [
        ("Leadership", "Audit what changed, what was verified, and what still needs follow-up."),
        ("UT Lead", "Preview workflow improvements that may affect trial setup, selection, reporting, or participant handling."),
        ("Admin", "Track configuration, approvals, user controls, debug settings, and system-level changes."),
        ("IT", "Review security posture, known exceptions, deferred cleanup, and operational risk areas."),
    ]

    return "".join(
        f"""
        <article class="system-updates-audience-card">
            <h3>{e(title)}</h3>
            <p>{e(description)}</p>
        </article>
        """
        for title, description in cards
    )


def _render_metric_cards(entries: list[dict]) -> str:
    latest = entries[0] if entries else {}
    latest_date = latest.get("date") or "—"
    latest_title = latest.get("title") or "No changelog entries found"
    recent_entries = entries[:5]
    confirmed_count = sum(_count_bullets(entry, "Confirmed Working") for entry in recent_entries)
    follow_up_count = sum(
        _count_bullets(entry, "Untested / Needs Follow-up")
        + _count_bullets(entry, "Known Exceptions / Deferred Cleanup")
        for entry in recent_entries
    )

    cards = [
        ("Latest update", latest_date, latest_title),
        ("Entries shown", str(len(recent_entries)), "Newest changelog entries in this view"),
        ("Verified items", str(confirmed_count), "Confirmed working bullets across recent entries"),
        ("Follow-up items", str(follow_up_count), "Untested and deferred bullets across recent entries"),
    ]

    return "".join(
        f"""
        <article class="system-updates-metric-card">
            <div class="system-updates-metric-label">{e(label)}</div>
            <div class="system-updates-metric-value">{e(value)}</div>
            <p>{e(note)}</p>
        </article>
        """
        for label, value, note in cards
    )


def _render_latest_entry(entries: list[dict]) -> str:
    if not entries:
        return """
        <section class="system-updates-panel">
            <h2>Latest Update</h2>
            <p class="system-updates-muted">No changelog entries were found.</p>
        </section>
        """

    latest = entries[0]
    summary = _render_section_html(latest, "Summary", empty_text="No summary listed.")
    next_step = _render_section_html(
        latest,
        "Next Recommended Step",
        empty_text="No next recommended step listed.",
    )

    return f"""
    <section class="system-updates-panel system-updates-latest">
        <div class="system-updates-section-heading-row">
            <div>
                <h2>Latest Update</h2>
                <p class="system-updates-entry-kicker">{e(latest.get("date") or "")}</p>
            </div>
            <span class="system-updates-status-pill">Newest first</span>
        </div>
        <h3>{e(latest.get("title") or "Untitled update")}</h3>
        <div class="system-updates-section-block">
            <h4>Summary</h4>
            {summary}
        </div>
        <div class="system-updates-section-block">
            <h4>Next Recommended Step</h4>
            {next_step}
        </div>
    </section>
    """


def _render_entry_details(entries: list[dict]) -> str:
    if not entries:
        return """
        <section class="system-updates-panel">
            <h2>Recent Changelog Entries</h2>
            <p class="system-updates-muted">No recent entries are available.</p>
        </section>
        """

    blocks: list[str] = []

    for index, entry in enumerate(entries[:5]):
        open_attr = " open" if index == 0 else ""
        blocks.append(f"""
        <details class="system-updates-entry"{open_attr}>
            <summary>
                <span>
                    <strong>{e(entry.get("date") or "")}</strong>
                    {e(entry.get("title") or "Untitled update")}
                </span>
            </summary>

            <div class="system-updates-entry-body">
                <div class="system-updates-entry-grid">
                    <section>
                        <h4>Changes Made</h4>
                        {_render_section_html(entry, "Changes Made")}
                    </section>
                    <section>
                        <h4>Confirmed Working</h4>
                        {_render_section_html(entry, "Confirmed Working")}
                    </section>
                    <section>
                        <h4>Needs Follow-up</h4>
                        {_render_section_html(entry, "Untested / Needs Follow-up")}
                    </section>
                    <section>
                        <h4>Deferred Cleanup</h4>
                        {_render_section_html(entry, "Known Exceptions / Deferred Cleanup")}
                    </section>
                </div>
            </div>
        </details>
        """)

    return f"""
    <section class="system-updates-panel">
        <h2>Recent Changelog Entries</h2>
        <p class="system-updates-panel-intro">
            This view keeps the engineering changelog readable for audit, planning, and role-specific review.
        </p>
        {''.join(blocks)}
    </section>
    """


def _render_full_changelog(raw_markdown: str) -> str:
    return f"""
    <section class="system-updates-panel">
        <details class="system-updates-full-log">
            <summary>View full changelog source</summary>
            <pre>{e(raw_markdown or "")}</pre>
        </details>
    </section>
    """


def render_system_updates_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
) -> dict:
    denied = _require_system_updates_access(user_id)
    if denied:
        return denied

    if CHANGELOG_PATH.exists():
        raw_markdown = CHANGELOG_PATH.read_text(encoding="utf-8")
        entries = _parse_changelog_entries(raw_markdown)
        source_note = "Source: docs/changelog.md"
    else:
        raw_markdown = ""
        entries = []
        source_note = "Missing source: docs/changelog.md"

    body_html = f"""
    <section class="admin-page-shell system-updates-page">
        <div class="page-header admin-page-header">
            <div class="admin-page-title-row">
                <div>
                    <h1 class="page-title">System Updates</h1>
                    <p class="page-description">
                        Internal change visibility for leadership audit, UT Lead planning, Admin review, and IT review.
                    </p>
                </div>
                <div class="admin-page-toolbar">
                    <span class="admin-summary-pill">{e(source_note)}</span>
                    <span class="admin-summary-note">Read-only</span>
                </div>
            </div>
        </div>

        <div class="system-updates-audience-grid">
            {_render_audience_cards()}
        </div>

        <div class="system-updates-metric-grid">
            {_render_metric_cards(entries)}
        </div>

        {_render_latest_entry(entries)}
        {_render_entry_details(entries)}
        {_render_full_changelog(raw_markdown)}
    </section>
    """

    html = inject_nav(base_template)
    html = html.replace("__BODY_CLASS__", "admin-page system-updates-body")
    html = html.replace("{{ title }}", "System Updates")
    html = html.replace("__BODY__", body_html)
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/admin.css">\n</head>',
    )

    return {"html": html}