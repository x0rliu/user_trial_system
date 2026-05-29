# app/handlers/reporting_insights.py

from urllib.parse import quote_plus

from app.utils.csrf import generate_csrf_token
from app.utils.html_escape import escape_html as e


REPORTING_VIEW_CONFIG = {
    "rounds": {
        "label": "Rounds",
        "href": "/reporting/insights/rounds",
    },
    "projects": {
        "label": "Projects",
        "href": "/reporting/insights/projects",
    },
    "product_types": {
        "label": "Product Type",
        "href": "/reporting/insights/product-types",
    },
    "business_groups": {
        "label": "Business Group",
        "href": "/reporting/insights/business-groups",
    },
    "overall": {
        "label": "Logi Overall",
        "href": "/reporting/insights/overall",
    },
    "tiers": {
        "label": "Tier",
        "href": "/reporting/insights/tiers",
    },
}


def _format_count(count, singular, plural=None):
    safe_count = int(count or 0)
    if safe_count == 1:
        return f"{safe_count} {singular}"
    return f"{safe_count} {plural or singular + 's'}"

def _posted_scalar(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _comparison_status_key(product_type):
    return str(product_type or "").strip().lower()


def _comparison_report_href(product_type):
    safe_product_type = quote_plus(str(product_type or "").strip())
    return f"/reporting/insights/product-types/comparison?product_type={safe_product_type}"


def _format_project_round_label(report):
    internal_name = str(report.get("internal_name") or "").strip()
    market_name = str(report.get("market_name") or "").strip()
    round_number = report.get("round_number")

    if internal_name and market_name:
        base_label = f"{internal_name} ({market_name})"
    elif internal_name:
        base_label = internal_name
    elif market_name:
        base_label = market_name
    else:
        base_label = "Unnamed Project"

    if round_number not in (None, "", "-"):
        return f"{base_label} · Round {round_number}"

    return base_label


def _render_project_report_link(report):
    report_href = str(report.get("report_href") or "").strip()
    report_label = _format_project_round_label(report)

    if not report_href:
        return e(report_label)

    return f"""
        <a class="reporting-product-link" href="{e(report_href)}">
            {e(report_label)}
        </a>
    """


def _render_reporting_view_tabs(active_view):
    items = []

    for view_key, config in REPORTING_VIEW_CONFIG.items():
        active_class = " is-active" if view_key == active_view else ""
        items.append(f"""
            <a class="reporting-view-pill{active_class}" href="{e(config.get('href'))}">
                {e(config.get('label'))}
            </a>
        """)

    return f"""
    <div class="reporting-view-tabs" aria-label="Reporting view options">
        {''.join(items)}
    </div>
    """


def _project_identity_key(report):
    product_id = report.get("product_id")
    if product_id not in (None, ""):
        return f"product:{product_id}"

    internal_name = str(report.get("internal_name") or "").strip().lower()
    market_name = str(report.get("market_name") or "").strip().lower()
    business_group = str(report.get("business_group") or "").strip().lower()
    product_type = str(report.get("product_type_display") or "").strip().lower()

    return f"fallback:{internal_name}|{market_name}|{business_group}|{product_type}"


def _format_project_label(report):
    internal_name = str(report.get("internal_name") or "").strip()
    market_name = str(report.get("market_name") or "").strip()

    if internal_name and market_name:
        return f"{internal_name} ({market_name})"
    if internal_name:
        return internal_name
    if market_name:
        return market_name
    return "Unnamed Project"


def _render_rounds_view(published_reports):
    latest_reports = sorted(
        published_reports,
        key=lambda report: str(report.get("published_at") or report.get("updated_at") or ""),
        reverse=True,
    )[:10]

    report_rows_html = ""

    for report in latest_reports:
        business_group = e(report.get("business_group") or "-")
        product_type = e(report.get("product_type_display") or "-")
        source_label = e(report.get("report_source_label") or report.get("report_source") or "-")
        survey_count = int(report.get("survey_count") or 0)
        dataset_count = int(report.get("dataset_count") or 0)
        published_at = report.get("published_at") or ""

        report_rows_html += f"""
        <tr>
            <td>{_render_project_report_link(report)}</td>
            <td>{source_label}</td>
            <td>{business_group}</td>
            <td>{product_type}</td>
            <td>{_format_count(survey_count, "survey")} ({_format_count(dataset_count, "dataset")})</td>
            <td class="reporting-published-cell">{e(str(published_at)) if published_at else "—"}</td>
        </tr>
        """

    if not report_rows_html:
        report_rows_html = """
        <tr>
            <td colspan="6">
                <div class="empty-state">
                    <p class="empty-state-description">
                        No round reports have been published to Reporting & Insights yet.
                    </p>
                </div>
            </td>
        </tr>
        """

    overflow_note = ""
    if len(published_reports) > 10:
        overflow_note = f"""
        <div class="reporting-bounded-note">
            Showing the 10 latest round reports. Search and pagination will be added after the reporting object model is stable.
        </div>
        """

    return f"""
    <section class="reporting-table-card">
        <div class="reporting-section-header reporting-section-header-row">
            <div>
                <h3>Latest published round reports</h3>
                <p>
                    Round reports aggregate the surveys from one product trial round. This is the round-level report artifact view.
                </p>
            </div>
            <span class="reporting-scope-chip">Rounds</span>
        </div>
        <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Round Report</th>
                        <th>Source</th>
                        <th>BG</th>
                        <th>Product Type</th>
                        <th>Surveys</th>
                        <th class="reporting-published-cell">Published</th>
                    </tr>
                </thead>
                <tbody>
                    {report_rows_html}
                </tbody>
            </table>
        </div>
        {overflow_note}
    </section>
    """


def _render_projects_view(published_reports):
    reports_by_project = {}
    for report in published_reports:
        project_key = _project_identity_key(report)
        if project_key not in reports_by_project:
            reports_by_project[project_key] = []
        reports_by_project[project_key].append(report)

    project_groups = []
    for project_key, reports in reports_by_project.items():
        latest_activity = max(str(report.get("published_at") or report.get("updated_at") or "") for report in reports)
        project_groups.append((project_key, reports, latest_activity))

    project_groups = sorted(
        project_groups,
        key=lambda group: (group[2], _format_project_label(group[1][0])),
        reverse=True,
    )[:10]

    rows_html = ""
    for project_key, reports, latest_activity in project_groups:
        representative = reports[0]
        project_label = _format_project_label(representative)
        business_group = e(representative.get("business_group") or "-")
        product_type = e(representative.get("product_type_display") or "-")
        round_count = len(reports)
        survey_count = sum(int(report.get("survey_count") or 0) for report in reports)
        dataset_count = sum(int(report.get("dataset_count") or 0) for report in reports)
        project_status = "Multi-round" if round_count > 1 else "Single-round"
        project_status_class = " is-multi" if round_count > 1 else ""

        round_rows_html = ""
        for report in sorted(reports, key=lambda item: int(item.get("round_number") or 0)):
            source_label = e(report.get("report_source_label") or report.get("report_source") or "-")
            round_survey_count = int(report.get("survey_count") or 0)
            round_dataset_count = int(report.get("dataset_count") or 0)
            published_at = report.get("published_at") or ""

            round_rows_html += f"""
            <tr>
                <td>{_render_project_report_link(report)}</td>
                <td>{source_label}</td>
                <td>{_format_count(round_survey_count, "survey")} ({_format_count(round_dataset_count, "dataset")})</td>
                <td class="reporting-published-cell">{e(str(published_at)) if published_at else "—"}</td>
            </tr>
            """

        rows_html += f"""
        <details class="reporting-product-type-row-card" {'open' if round_count > 1 else ''}>
            <summary class="reporting-project-row-summary">
                <span class="historical-project-caret" aria-hidden="true">▸</span>
                <span>
                    <span class="reporting-product-type-title">{e(project_label)}</span>
                    <span class="reporting-product-type-meta">{business_group} · {product_type}</span>
                </span>
                <span>{_format_count(round_count, "round")}</span>
                <span>{_format_count(survey_count, "survey")} ({_format_count(dataset_count, "dataset")})</span>
                <span><span class="reporting-project-status{project_status_class}">{e(project_status)}</span></span>
                <span>{e(str(latest_activity)) if latest_activity else "—"}</span>
            </summary>
            <div class="reporting-product-type-row-detail">
                <p>
                    Project reports will aggregate these round reports in the next reporting-model stage. For now, this view makes the project-to-round relationship explicit.
                </p>
                <div class="table-scroll">
                    <table class="data-table reporting-product-type-project-table">
                        <thead>
                            <tr>
                                <th>Round Report</th>
                                <th>Source</th>
                                <th>Surveys</th>
                                <th class="reporting-published-cell">Published</th>
                            </tr>
                        </thead>
                        <tbody>
                            {round_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </details>
        """

    if not rows_html:
        rows_html = """
        <div class="empty-state">
            <p class="empty-state-description">
                Project groupings will appear once round reports are published to Reporting & Insights.
            </p>
        </div>
        """

    overflow_note = ""
    if len(reports_by_project) > 10:
        overflow_note = """
        <div class="reporting-bounded-note">
            Showing the 10 most recently active projects. Filtering and pagination will come later.
        </div>
        """

    return f"""
    <section class="reporting-table-card">
        <div class="reporting-section-header reporting-section-header-row">
            <div>
                <h3>Published projects</h3>
                <p>
                    Projects group published round reports by product so multi-round products do not look like separate products in cross-comparison.
                </p>
            </div>
            <span class="reporting-scope-chip">Projects</span>
        </div>
        <div class="reporting-project-row-header">
            <div></div>
            <div>Project</div>
            <div>Rounds</div>
            <div>Surveys</div>
            <div>Status</div>
            <div>Latest Activity</div>
        </div>
        <div class="reporting-product-type-row-list">
            {rows_html}
        </div>
        {overflow_note}
    </section>
    """


def _render_product_types_view(*, user_id, published_reports, comparison_reports_by_type):
    from app.services.product_type_comparison_service import product_type_comparison_support_status

    csrf_token = generate_csrf_token(user_id)

    reports_by_type = {}
    for report in published_reports:
        product_type_key = str(report.get("product_type_display") or "-")
        if product_type_key not in reports_by_type:
            reports_by_type[product_type_key] = []
        reports_by_type[product_type_key].append(report)

    product_type_groups = []
    for product_type, reports in reports_by_type.items():
        latest_activity = max(str(report.get("published_at") or report.get("updated_at") or "") for report in reports)
        product_type_groups.append((product_type, reports, latest_activity))

    product_type_groups = sorted(
        product_type_groups,
        key=lambda group: (group[2], group[0]),
        reverse=True,
    )[:10]

    rows_html = ""
    for product_type, reports, latest_activity in product_type_groups:
        report_count = len(reports)
        total_surveys = sum(int(report.get("survey_count") or 0) for report in reports)
        total_datasets = sum(int(report.get("dataset_count") or 0) for report in reports)
        business_group_values = sorted({
            str(report.get("business_group") or "-")
            for report in reports
        })

        support_status = product_type_comparison_support_status(
            product_type_display=product_type,
            report_count=report_count,
        )

        if support_status.get("is_ready"):
            readiness_badge = "<span class='reporting-readiness-badge is-ready'>Ready for comparison</span>"
            insight_note = "This product type has enough published reports and an explicit comparison function."
        elif support_status.get("is_supported"):
            readiness_badge = "<span class='reporting-readiness-badge is-limited'>Needs more reports</span>"
            insight_note = e(support_status.get("reason") or "More reports are needed before comparison generation.")
        else:
            readiness_badge = "<span class='reporting-readiness-badge is-muted'>Not configured</span>"
            insight_note = "This product type does not have an explicit comparison function yet."

        comparison_report = comparison_reports_by_type.get(_comparison_status_key(product_type)) or {}
        comparison_updated_at = comparison_report.get("updated_at")

        if comparison_report:
            comparison_summary = f"""
                <span class="reporting-comparison-state is-generated">Comparison generated</span>
                <span class="reporting-product-type-meta">Updated {e(str(comparison_updated_at) if comparison_updated_at else '-')}</span>
            """
            comparison_controls = f"""
                <div class="reporting-comparison-actions">
                    <a class="historical-action-pill" href="{e(_comparison_report_href(product_type))}">View Comparison</a>
                    <form method="POST" action="/reporting/insights/product-types/generate-comparison" class="reporting-inline-form" onsubmit="startAnalysisLoading();">
                        <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                        <input type="hidden" name="product_type" value="{e(product_type)}">
                        <button type="submit" class="historical-action-pill is-secondary">Regenerate</button>
                    </form>
                </div>
            """
        elif support_status.get("is_ready"):
            comparison_summary = "<span class='reporting-comparison-state is-ready'>Generate available</span>"
            comparison_controls = f"""
                <div class="reporting-comparison-actions">
                    <form method="POST" action="/reporting/insights/product-types/generate-comparison" class="reporting-inline-form" onsubmit="startAnalysisLoading();">
                        <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                        <input type="hidden" name="product_type" value="{e(product_type)}">
                        <button type="submit" class="historical-action-pill">Generate Comparison</button>
                    </form>
                </div>
            """
        else:
            comparison_summary = "<span class='reporting-comparison-state is-unavailable'>Unavailable</span>"
            comparison_controls = """
                <div class="reporting-comparison-note">
                    Comparison generation is unavailable for this row right now.
                </div>
            """

        project_rows_html = ""
        sorted_reports = sorted(
            reports,
            key=lambda report: str(report.get("published_at") or report.get("updated_at") or ""),
            reverse=True,
        )

        for report in sorted_reports:
            business_group = e(report.get("business_group") or "-")
            source_label = e(report.get("report_source_label") or report.get("report_source") or "-")
            survey_count = int(report.get("survey_count") or 0)
            dataset_count = int(report.get("dataset_count") or 0)
            published_at = report.get("published_at") or ""

            project_rows_html += f"""
            <tr>
                <td>{_render_project_report_link(report)}</td>
                <td>{source_label}</td>
                <td>{business_group}</td>
                <td>{_format_count(survey_count, "survey")} ({_format_count(dataset_count, "dataset")})</td>
                <td class="reporting-published-cell">{e(str(published_at)) if published_at else "—"}</td>
            </tr>
            """

        rows_html += f"""
        <details class="reporting-product-type-row-card" {'open' if report_count >= 2 else ''}>
            <summary class="reporting-product-type-row-summary">
                <span class="historical-project-caret" aria-hidden="true">▸</span>
                <span>
                    <span class="reporting-product-type-title">{e(product_type)}</span>
                    <span class="reporting-product-type-meta">{e(', '.join(business_group_values))}</span>
                </span>
                <span>{_format_count(report_count, "report")}</span>
                <span>{_format_count(total_surveys, "survey")} ({_format_count(total_datasets, "dataset")})</span>
                <span>{readiness_badge}</span>
                <span>{e(str(latest_activity)) if latest_activity else "—"}</span>
                <span>{comparison_summary}</span>
            </summary>
            <div class="reporting-product-type-row-detail">
                <div class="reporting-comparison-control-row">
                    <p>{insight_note}</p>
                    {comparison_controls}
                </div>
                <div class="table-scroll">
                    <table class="data-table reporting-product-type-project-table">
                        <thead>
                            <tr>
                                <th>Included Project Round</th>
                                <th>Source</th>
                                <th>BG</th>
                                <th>Surveys</th>
                                <th class="reporting-published-cell">Published</th>
                            </tr>
                        </thead>
                        <tbody>
                            {project_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </details>
        """

    if not rows_html:
        rows_html = """
        <div class="empty-state">
            <p class="empty-state-description">
                Product-type grouping will appear once project reports are published.
            </p>
        </div>
        """

    overflow_note = ""
    if len(reports_by_type) > 10:
        overflow_note = """
        <div class="reporting-bounded-note">
            Showing the 10 most recently active product types. Filtering and pagination will come later.
        </div>
        """

    return f"""
    <section class="reporting-table-card">
        <div class="reporting-section-header reporting-section-header-row">
            <div>
                <h3>Product type insights</h3>
                <p>
                    Product types are insight groups built from the currently published historical aggregate project-round reports.
                </p>
            </div>
            <span class="reporting-scope-chip">Product Type</span>
        </div>
        <div class="reporting-product-type-row-header">
            <div></div>
            <div>Product Type</div>
            <div>Reports</div>
            <div>Surveys</div>
            <div>Readiness</div>
            <div>Latest Activity</div>
            <div>Comparison</div>
        </div>
        <div class="reporting-product-type-row-list">
            {rows_html}
        </div>
        {overflow_note}
    </section>
    """


def _render_fpo_view(active_view):
    label = REPORTING_VIEW_CONFIG.get(active_view, {}).get("label", "Reporting view")

    return f"""
    <section class="reporting-table-card">
        <div class="reporting-section-header reporting-section-header-row">
            <div>
                <h3>{e(label)} insights</h3>
                <p>
                    This reporting scope is reserved so the hub can scale beyond project and product-type reports without becoming one oversized page.
                </p>
            </div>
            <span class="reporting-scope-chip is-fpo">FPO</span>
        </div>
        <div class="reporting-fpo-card">
            <div class="historical-kicker">For placement only</div>
            <h4>{e(label)} reporting will live here.</h4>
            <p>
                Future passes can connect this view to DB-backed rollups after the underlying reporting object model is finalized.
            </p>
        </div>
    </section>
    """


def render_reporting_insights_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    active_view: str = "rounds",
):
    """
    GET /reporting/insights/*

    Reporting hub for published reports and cross-product insights.
    """

    from app.db.historical_aggregate_reports import list_published_historical_aggregate_reports_for_reporting_insights
    from app.db.product_type_comparison_reports import list_latest_product_type_comparison_reports

    if active_view not in REPORTING_VIEW_CONFIG:
        active_view = "rounds"

    published_reports = list_published_historical_aggregate_reports_for_reporting_insights()
    comparison_reports = list_latest_product_type_comparison_reports()
    comparison_reports_by_type = {
        _comparison_status_key(row.get("product_type_display")): row
        for row in comparison_reports
    }

    total_reports = len(published_reports)
    product_types = sorted({
        str(report.get("product_type_display") or "-")
        for report in published_reports
    })
    business_groups = sorted({
        str(report.get("business_group") or "-")
        for report in published_reports
    })

    if active_view == "rounds":
        active_content_html = _render_rounds_view(published_reports)
    elif active_view == "projects":
        active_content_html = _render_projects_view(published_reports)
    elif active_view == "product_types":
        active_content_html = _render_product_types_view(
            user_id=user_id,
            published_reports=published_reports,
            comparison_reports_by_type=comparison_reports_by_type,
        )
    else:
        active_content_html = _render_fpo_view(active_view)

    html = f"""
    <div class="results-section reporting-insights-page">
        <div class="reporting-hero">
            <div>
                <h2><span class="reporting-title-prefix">Reporting & Insights:</span> Published Project Reports</h2>
                <p class="historical-page-description">
                    Review published report objects through bounded reporting views. The hub should not care whether a report came from
                    a legacy upload or a current trial; published data is published data.
                </p>
            </div>
        </div>

        <div class="reporting-metric-grid">
            <div class="reporting-metric-card">
                <div class="reporting-metric-value">{total_reports}</div>
                <div class="reporting-metric-label">Published reports</div>
            </div>
            <div class="reporting-metric-card">
                <div class="reporting-metric-value">{len(product_types)}</div>
                <div class="reporting-metric-label">Product types</div>
            </div>
            <div class="reporting-metric-card">
                <div class="reporting-metric-value">{len(business_groups)}</div>
                <div class="reporting-metric-label">Business groups</div>
            </div>
        </div>

        {_render_reporting_view_tabs(active_view)}

        {active_content_html}
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def render_reporting_insights_project_report_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    product_id: int,
    round_number: int,
    query_params,
):
    """
    GET /reporting/insights/projects/report

    Read-only published report detail view for Reporting & Insights.
    """

    from app.db.historical_aggregate_reports import historical_aggregate_report_is_visible_to_reporting_insights
    from app.handlers.historical import render_historical_aggregate_report_get

    if not historical_aggregate_report_is_visible_to_reporting_insights(
        product_id=int(product_id),
        round_number=int(round_number),
    ):
        return {"redirect": "/reporting/insights/rounds"}

    return render_historical_aggregate_report_get(
        user_id=user_id,
        base_template=base_template,
        inject_nav=inject_nav,
        product_id=product_id,
        round_number=round_number,
        query_params=query_params,
        can_manage_report=False,
        view_mode="reporting",
    )

def _render_comparison_notice(query_params):
    error = query_params.get("error", [None])[0]

    if error:
        return f"""
        <div class="alert alert-error">
            Product type comparison could not be generated: {e(error)}.
        </div>
        """

    return ""


def _render_text_list(items, *, empty_text="No saved items yet."):
    if not isinstance(items, list):
        items = []

    rendered_items = "".join(
        f"<li>{e(item)}</li>"
        for item in items
        if str(item or "").strip()
    )

    if not rendered_items:
        rendered_items = f"<li class='historical-muted'>{e(empty_text)}</li>"

    return f"<ul>{rendered_items}</ul>"


def _render_evidence_list(item):
    evidence = item.get("evidence") if isinstance(item, dict) else []
    if not isinstance(evidence, list):
        evidence = [evidence]
    return _render_text_list(evidence, empty_text="No evidence notes saved.")


def _render_comparison_body_value(value):
    if value is None:
        return ""

    if isinstance(value, list):
        rendered_items = "".join(
            f"<li>{e(item)}</li>"
            for item in value
            if str(item or "").strip()
        )

        if not rendered_items:
            return ""

        return f"<ul class='reporting-comparison-body-list'>{rendered_items}</ul>"

    text = str(value or "").strip()
    if not text:
        return ""

    return f"<p>{e(text)}</p>"


def _render_comparison_item_cards(items, *, title_key, body_key=None, fallback_title="Untitled item"):
    if not isinstance(items, list):
        items = []

    cards_html = ""
    for item in items:
        if not isinstance(item, dict):
            continue

        title = item.get(title_key) or fallback_title
        body = item.get(body_key) if body_key else None
        confidence = item.get("confidence")
        confidence_html = f"<span class='reporting-comparison-confidence'>{e(confidence)}</span>" if confidence else ""

        cards_html += f"""
        <div class="reporting-comparison-item-card">
            <div class="reporting-comparison-item-heading">
                <h4>{e(title)}</h4>
                {confidence_html}
            </div>
            {_render_comparison_body_value(body)}
            <div class="reporting-comparison-evidence">
                <div class="historical-kicker">Evidence</div>
                {_render_evidence_list(item)}
            </div>
        </div>
        """

    if not cards_html:
        cards_html = """
        <div class="reporting-comparison-item-card is-empty">
            <p>No saved comparison items yet.</p>
        </div>
        """

    return f"<div class='reporting-comparison-card-grid'>{cards_html}</div>"


def _render_comparison_details(*, title, body_html, open_by_default=False, kicker=None):
    open_attr = " open" if open_by_default else ""
    kicker_html = f"<span class='reporting-scope-chip'>{e(kicker)}</span>" if kicker else ""

    return f"""
    <details class="reporting-comparison-section"{open_attr}>
        <summary>
            <span>{e(title)}</span>
            {kicker_html}
        </summary>
        <div class="reporting-comparison-section-body">
            {body_html}
        </div>
    </details>
    """


def _render_stage_analysis(stage, *, open_by_default=False):
    if not isinstance(stage, dict):
        stage = {}

    positives = _render_comparison_item_cards(
        stage.get("positives"),
        title_key="theme",
        body_key="why_it_matters",
        fallback_title="Positive pattern",
    )
    negatives = _render_comparison_item_cards(
        stage.get("negatives"),
        title_key="theme",
        body_key="why_it_matters",
        fallback_title="Negative pattern",
    )
    positive_drivers = _render_comparison_item_cards(
        stage.get("positive_sentiment_drivers"),
        title_key="driver",
        body_key="behavioral_reason",
        fallback_title="Positive driver",
    )
    negative_drivers = _render_comparison_item_cards(
        stage.get("negative_sentiment_drivers"),
        title_key="driver",
        body_key="behavioral_reason",
        fallback_title="Negative driver",
    )

    body_html = f"""
        <p class="reporting-comparison-summary-copy">{e(stage.get("summary") or "No summary saved yet.")}</p>
        <h3>Stage positives</h3>
        {positives}
        <h3>Stage negatives</h3>
        {negatives}
        <h3>Positive sentiment drivers</h3>
        {positive_drivers}
        <h3>Negative sentiment drivers</h3>
        {negative_drivers}
        <h3>Open questions</h3>
        {_render_text_list(stage.get("open_questions"), empty_text="No open questions saved.")}
    """

    return _render_comparison_details(
        title=stage.get("stage_name") or "Stage Analysis",
        body_html=body_html,
        open_by_default=open_by_default,
    )


def _render_included_reports_table(included_reports):
    if not isinstance(included_reports, list):
        included_reports = []

    rows_html = ""
    for report in included_reports:
        if not isinstance(report, dict):
            continue

        kpis = report.get("kpis") if isinstance(report.get("kpis"), dict) else {}
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}

        rows_html += f"""
        <tr>
            <td>{e(report.get("report_label") or report.get("report_key") or "-")}</td>
            <td>{e(report.get("business_group") or "-")}</td>
            <td>{e(summary.get("survey_count") or 0)}</td>
            <td>{e(summary.get("response_count") or 0)}</td>
            <td>{e(kpis.get("star_rating") if kpis.get("star_rating") is not None else "-")}</td>
            <td>{e(kpis.get("nps") if kpis.get("nps") is not None else "-")}</td>
            <td>{e(kpis.get("ready_for_sales") if kpis.get("ready_for_sales") is not None else "-")}</td>
        </tr>
        """

    if not rows_html:
        rows_html = """
        <tr>
            <td colspan="7">No included reports saved.</td>
        </tr>
        """

    return f"""
    <div class="table-scroll">
        <table class="data-table reporting-comparison-report-table">
            <thead>
                <tr>
                    <th>Report</th>
                    <th>BG</th>
                    <th>Surveys</th>
                    <th>Responses</th>
                    <th>Star</th>
                    <th>NPS</th>
                    <th>Ready %</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """


def render_reporting_product_type_comparison_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    product_type_display: str,
    query_params,
):
    """
    GET /reporting/insights/product-types/comparison

    Read-only saved product-type comparison report view.
    """

    from app.db.product_type_comparison_reports import get_latest_product_type_comparison_report

    result = get_latest_product_type_comparison_report(product_type_display=product_type_display)
    if not result.get("success"):
        error = result.get("error") or "not_found"
        return {"redirect": f"/reporting/insights/product-types?error=comparison_{error}"}

    report = result.get("report") or {}
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}
    included_reports = report.get("included_reports") if isinstance(report.get("included_reports"), list) else []

    product_type = metadata.get("product_type_display") or product_type_display
    updated_at = metadata.get("updated_at") or metadata.get("created_at") or "-"
    included_count = metadata.get("included_report_count") or len(included_reports)

    included_reports_body = f"""
        <div class="reporting-section-header reporting-section-header-row reporting-comparison-inner-header">
            <div>
                <h3>Included published reports</h3>
                <p>This comparison is generated only from reports already published to Reporting & Insights.</p>
            </div>
        </div>
        {_render_included_reports_table(included_reports)}
    """

    category_patterns_body = f"""
        <h3>Consistent positives</h3>
        {_render_comparison_item_cards(report.get("consistent_positives"), title_key="theme", body_key="why_it_matters")}
        <h3>Consistent negatives</h3>
        {_render_comparison_item_cards(report.get("consistent_negatives"), title_key="theme", body_key="why_it_matters")}
    """

    sentiment_body = f"""
        <h3>Positive sentiment drivers</h3>
        {_render_comparison_item_cards(report.get("positive_sentiment_drivers"), title_key="driver", body_key="behavioral_reason", fallback_title="Positive driver")}
        <h3>Negative sentiment drivers</h3>
        {_render_comparison_item_cards(report.get("negative_sentiment_drivers"), title_key="driver", body_key="behavioral_reason", fallback_title="Negative driver")}
    """

    decision_guidance_body = f"""
        <h3>Must-haves</h3>
        {_render_comparison_item_cards(report.get("must_haves"), title_key="item", body_key="why", fallback_title="Must-have")}
        <h3>Nice-to-haves</h3>
        {_render_comparison_item_cards(report.get("nice_to_haves"), title_key="item", body_key="why", fallback_title="Nice-to-have")}
        <h3>Cannot ship without</h3>
        {_render_comparison_item_cards(report.get("cannot_ship_without"), title_key="item", body_key="why_blocking", fallback_title="Cannot ship without")}
    """

    behavior_questions_body = f"""
        <h3>What users forgive</h3>
        {_render_comparison_item_cards(report.get("what_users_forgive"), title_key="item", body_key="conditions", fallback_title="Forgivable friction")}
        <h3>What users do not forgive</h3>
        {_render_comparison_item_cards(report.get("what_users_do_not_forgive"), title_key="item", body_key="why", fallback_title="Non-forgivable friction")}
        <h3>Use-case differences</h3>
        {_render_comparison_item_cards(report.get("use_case_differences"), title_key="use_case", body_key="what_matters", fallback_title="Use case")}
        <h3>Product Team questions to ask next</h3>
        {_render_text_list(report.get("product_team_questions_to_ask_next"), empty_text="No saved questions yet.")}
    """

    html = f"""
    <div class="results-section reporting-insights-page reporting-comparison-report-page">
        <div class="reporting-comparison-title-row">
            <div>
                <h2>Product Type Comparison: {e(product_type)}</h2>
                <p class="historical-page-description">
                    Generated category intelligence from published Reporting & Insights project-round reports.
                </p>
            </div>
            <a class="historical-action-pill is-secondary" href="/reporting/insights/product-types">Back to Product Type</a>
        </div>

        {_render_comparison_notice(query_params)}

        <section class="reporting-comparison-hero-card">
            <div>
                <div class="historical-kicker">Executive Summary</div>
                <p>{e(report.get("executive_summary") or "No executive summary saved yet.")}</p>
            </div>
            <div class="reporting-comparison-meta-card">
                <div><strong>{e(included_count)}</strong> published reports</div>
                <div>Generated: {e(updated_at)}</div>
                <div>Version: {e(metadata.get("generation_version") or "-")}</div>
            </div>
        </section>

        {_render_comparison_details(
            title="Included published reports",
            body_html=included_reports_body,
            open_by_default=True,
            kicker="Evidence base",
        )}
        {_render_stage_analysis(report.get("survey_1_first_impressions"), open_by_default=False)}
        {_render_stage_analysis(report.get("survey_2_usage"), open_by_default=False)}
        {_render_comparison_details(title="Category patterns", body_html=category_patterns_body, open_by_default=False)}
        {_render_comparison_details(title="Sentiment drivers", body_html=sentiment_body, open_by_default=False)}
        {_render_comparison_details(title="Decision guidance", body_html=decision_guidance_body, open_by_default=False)}
        {_render_comparison_details(title="User tolerance, use cases, and next questions", body_html=behavior_questions_body, open_by_default=False)}
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_reporting_product_type_comparison_generate_post(*, user_id: str, data: dict):
    """
    POST /reporting/insights/product-types/generate-comparison

    Generate or regenerate a DB-backed product-type comparison report.
    """

    from urllib.parse import quote_plus
    from app.services.product_type_comparison_service import generate_product_type_comparison

    product_type_display = _posted_scalar(data.get("product_type"))
    product_type_display = str(product_type_display or "").strip()

    if not product_type_display:
        return {"redirect": "/reporting/insights/product-types?error=missing_product_type"}

    result = generate_product_type_comparison(
        product_type_display=product_type_display,
        generated_by_user_id=user_id,
    )

    if not result.get("success"):
        error = result.get("error") or "generation_failed"
        return {"redirect": f"/reporting/insights/product-types?error={quote_plus(error)}"}

    safe_product_type = quote_plus(product_type_display)
    return {"redirect": f"/reporting/insights/product-types/comparison?product_type={safe_product_type}&comparison=generated"}