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

    project_id = report.get("project_id")
    if project_id not in (None, ""):
        return f"project:{project_id}"

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


def _render_project_report_generation_controls(*, project_key, project_report, can_generate_project_reports, csrf_token):
    safe_project_key = str(project_key or "").strip()
    project_report_href = f"/reporting/insights/projects/project-report?project_key={quote_plus(safe_project_key)}"

    if project_report:
        updated_at = project_report.get("updated_at") or ""
        status_html = f"""
            <span class="reporting-comparison-state is-generated">Project report generated</span>
            <span class="reporting-product-type-meta">Updated {e(str(updated_at)) if updated_at else '-'}</span>
        """
        view_html = f"""
            <a class="historical-action-pill is-secondary" href="{e(project_report_href)}" onclick="event.stopPropagation();">
                View Project Report
            </a>
        """
        label = "Regenerate Project Report"
    else:
        status_html = '<span class="reporting-comparison-state is-ready">Generate available</span>'
        view_html = ""
        label = "Generate Project Report"

    if not can_generate_project_reports:
        if project_report:
            return f"""
                <span class="reporting-project-report-action-stack">
                    {status_html}
                    {view_html}
                    <span class="reporting-comparison-note">Read-only view. UT Lead/Admin can regenerate.</span>
                </span>
            """
        return '<span class="reporting-comparison-note">Project report can be generated by UT Lead/Admin.</span>'

    return f"""
        <span class="reporting-project-report-action-stack">
            {status_html}
            {view_html}
            <form method="POST" action="/reporting/insights/projects/generate-report" class="reporting-inline-form" onsubmit="startAnalysisLoading();">
                <input type="hidden" name="csrf_token" value="{e(csrf_token)}">
                <input type="hidden" name="project_key" value="{e(safe_project_key)}">
                <button type="submit" class="historical-action-pill">{e(label)}</button>
            </form>
        </span>
    """


def _render_projects_view(published_reports, project_reports_by_key=None, can_generate_project_reports=False, user_id=None):
    project_reports_by_key = project_reports_by_key or {}
    csrf_token = generate_csrf_token(user_id) if can_generate_project_reports and user_id else ""
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

        project_report = project_reports_by_key.get(project_key)
        project_report_controls = _render_project_report_generation_controls(
            project_key=project_key,
            project_report=project_report,
            can_generate_project_reports=can_generate_project_reports,
            csrf_token=csrf_token,
        )

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
                <span>{project_report_controls}</span>
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
            <div>Project Report</div>
        </div>
        <div class="reporting-product-type-row-list">
            {rows_html}
        </div>
        {overflow_note}
    </section>
    """


def _render_product_types_view(*, user_id, published_reports, comparison_reports_by_type, can_generate_comparisons=False):
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
            if can_generate_comparisons:
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
            else:
                comparison_controls = f"""
                    <div class="reporting-comparison-actions">
                        <a class="historical-action-pill" href="{e(_comparison_report_href(product_type))}">View Comparison</a>
                        <span class="reporting-comparison-note">Read-only view. UT Lead/Admin can regenerate this comparison.</span>
                    </div>
                """
        elif support_status.get("is_ready"):
            comparison_summary = "<span class='reporting-comparison-state is-ready'>Generate available</span>"
            if can_generate_comparisons:
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
                comparison_controls = """
                    <div class="reporting-comparison-note">
                        Comparison can be generated by UT Lead/Admin.
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
    permission_level: int = 0,
):
    """
    GET /reporting/insights/*

    Reporting hub for published reports and cross-product insights.
    """

    from app.db.historical import list_published_historical_survey_reports_for_reporting_insights
    from app.db.historical_aggregate_reports import list_published_historical_aggregate_reports_for_reporting_insights
    from app.db.product_trial_reports import list_published_product_trial_reports_for_reporting_insights
    from app.db.product_type_comparison_reports import list_latest_product_type_comparison_reports
    from app.db.reporting_project_reports import list_latest_reporting_project_reports

    if active_view not in REPORTING_VIEW_CONFIG:
        active_view = "rounds"

    published_reports = list_published_historical_aggregate_reports_for_reporting_insights()
    published_reports.extend(list_published_historical_survey_reports_for_reporting_insights())
    published_reports.extend(list_published_product_trial_reports_for_reporting_insights())
    comparison_reports = list_latest_product_type_comparison_reports()
    project_reports = list_latest_reporting_project_reports()
    project_reports_by_key = {
        str(row.get("project_key") or "").strip(): row
        for row in project_reports
        if str(row.get("project_key") or "").strip()
    }
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
        active_content_html = _render_projects_view(
            published_reports,
            project_reports_by_key=project_reports_by_key,
            can_generate_project_reports=(int(permission_level or 0) >= 70),
            user_id=user_id,
        )
    elif active_view == "product_types":
        active_content_html = _render_product_types_view(
            user_id=user_id,
            published_reports=published_reports,
            comparison_reports_by_type=comparison_reports_by_type,
            can_generate_comparisons=(int(permission_level or 0) >= 70),
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


def _render_reporting_project_report_source_table(source_reports: list[dict]) -> str:
    rows_html = ""
    for source in source_reports or []:
        report_href = str(source.get("report_href") or "").strip()
        report_label = str(source.get("round_label") or "").strip()
        if not report_label:
            report_label = f"Round {source.get('round_number')}" if source.get("round_number") not in (None, "") else "Source Report"

        if report_href:
            report_link = f'<a class="reporting-product-link" href="{e(report_href)}">{e(report_label)}</a>'
        else:
            report_link = e(report_label)

        if source.get("has_saved_report_json"):
            saved_json_label = "Saved report JSON"
        elif source.get("has_validation_kpis"):
            saved_json_label = "Validation KPI source"
        else:
            saved_json_label = "Audit-only"

        digest = str(source.get("source_report_digest") or "").strip()
        digest_label = digest[:12] if digest else "—"

        rows_html += f"""
            <tr>
                <td>{report_link}</td>
                <td>{e(source.get("report_source_label") or source.get("report_source") or "-")}</td>
                <td>{e(saved_json_label)}</td>
                <td>{_format_count(source.get("survey_count") or 0, "survey")} ({_format_count(source.get("dataset_count") or 0, "dataset")})</td>
                <td>{e(source.get("response_count") or 0)} responses</td>
                <td>{e(source.get("answer_count") or 0)} answers</td>
                <td>{e(digest_label)}</td>
                <td class="reporting-published-cell">{e(str(source.get("published_at") or "—"))}</td>
            </tr>
        """

    if not rows_html:
        rows_html = """
            <tr>
                <td colspan="8">No source reports were stored for this project report.</td>
            </tr>
        """

    return f"""
        <details class="reporting-table-card" style="margin-top:18px;">
            <summary style="cursor:pointer;">
                <div class="reporting-section-header reporting-section-header-row" style="margin-bottom:0;">
                    <div>
                        <h3>Source Details / Audit Trail</h3>
                        <p>Published source reports used at generation time. This section is audit metadata, not the analytical body of the Project Report.</p>
                    </div>
                    <span class="reporting-scope-chip">Audit</span>
                </div>
            </summary>
            <div class="table-scroll" style="margin-top:14px;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Report</th>
                            <th>Source</th>
                            <th>Analytical status</th>
                            <th>Surveys</th>
                            <th>Responses</th>
                            <th>Answers</th>
                            <th>Digest</th>
                            <th class="reporting-published-cell">Published</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </details>
    """

def _project_report_metric_display(value, suffix=""):
    if value in (None, ""):
        return "—"

    try:
        text = f"{float(value):.1f}"
    except (TypeError, ValueError):
        text = str(value)

    if text.endswith(".0"):
        text = text[:-2]

    return f"{e(text)}{e(suffix)}"


def _project_report_generated_label(report: dict, row: dict) -> str:
    metadata = report.get("metadata") if isinstance(report.get("metadata"), dict) else {}

    generated_at = (
        metadata.get("updated_at")
        or row.get("updated_at")
        or metadata.get("created_at")
        or row.get("created_at")
        or ""
    )

    generation_version = (
        metadata.get("generation_version")
        or metadata.get("version")
        or row.get("generation_version")
        or ""
    )

    if not generated_at:
        return "Last generated: —"

    if generation_version:
        return f"Last generated: {generated_at} · {generation_version}"

    return f"Last generated: {generated_at}"


def _project_report_status_label(status):
    safe_status = str(status or "").strip().lower()
    if safe_status == "pass":
        return "Pass"
    if safe_status == "fail":
        return "Fail"
    if safe_status == "missing":
        return "Missing"
    return safe_status.title() if safe_status else "—"


def _project_report_kpi_source_label(source_type: object) -> str:
    safe_source_type = str(source_type or "").strip()

    if safe_source_type == "validation_kpi_source":
        return "validation evidence"

    if safe_source_type == "saved_round_report_json":
        return "saved round report"

    return ""


def _project_report_source_label(source: dict) -> str:
    round_label = str(source.get("round_label") or "").strip()
    if round_label:
        return round_label

    round_number = source.get("round_number")
    if round_number not in (None, ""):
        return f"Round {round_number}"

    return "Source Report"


def _render_project_report_source_status_notice(report: dict) -> str:
    source_reports = report.get("source_reports")
    if not isinstance(source_reports, list):
        return ""

    validation_kpi_sources = [
        source for source in source_reports
        if isinstance(source, dict)
        and not source.get("has_saved_report_json")
        and source.get("has_validation_kpis")
    ]

    audit_only_sources = [
        source for source in source_reports
        if isinstance(source, dict)
        and not source.get("has_saved_report_json")
        and not source.get("has_validation_kpis")
    ]

    if not validation_kpi_sources and not audit_only_sources:
        return ""

    rows_html = ""

    for source in validation_kpi_sources:
        report_href = str(source.get("report_href") or "").strip()
        source_label = _project_report_source_label(source)
        source_type = source.get("report_source_label") or source.get("report_source") or "Validation Source"
        report_scope = source.get("report_scope") or "validation"
        reason = "Included in KPI progression as validation evidence"

        if report_href:
            source_link = f'<a class="reporting-product-link" href="{e(report_href)}">{e(source_label)}</a>'
        else:
            source_link = e(source_label)

        rows_html += f"""
            <tr>
                <td>{source_link}</td>
                <td>{e(source_type)}</td>
                <td>{e(report_scope)}</td>
                <td>Validation KPI source</td>
                <td>{e(reason)}</td>
            </tr>
        """

    for source in audit_only_sources:
        report_href = str(source.get("report_href") or "").strip()
        source_label = _project_report_source_label(source)
        source_type = source.get("report_source_label") or source.get("report_source") or "Source"
        report_scope = source.get("report_scope") or "audit-only"
        reason = "No saved round report JSON and no validation KPI payload"

        if report_href:
            source_link = f'<a class="reporting-product-link" href="{e(report_href)}">{e(source_label)}</a>'
        else:
            source_link = e(source_label)

        rows_html += f"""
            <tr>
                <td>{source_link}</td>
                <td>{e(source_type)}</td>
                <td>{e(report_scope)}</td>
                <td>Audit-only</td>
                <td>{e(reason)}</td>
            </tr>
        """

    return f"""
        <section class="reporting-table-card" style="margin-top:18px; border-left:5px solid #7bd7c5;">
            <div class="reporting-section-header reporting-section-header-row">
                <div>
                    <h3>Validation and audit source status</h3>
                    <p>
                        Some sources may not have saved round report JSON. Validation KPI sources still contribute to KPI progression;
                        true audit-only sources remain traceability-only.
                    </p>
                </div>
                <span class="reporting-scope-chip">Source status</span>
            </div>
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Source</th>
                            <th>Type</th>
                            <th>Scope</th>
                            <th>Status</th>
                            <th>How used</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </section>
    """


def _render_project_report_checkpoint_summary(report: dict) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    final_recommendation = report.get("final_recommendation") if isinstance(report.get("final_recommendation"), dict) else {}

    conclusion = (
        summary.get("checkpoint_conclusion")
        or final_recommendation.get("conclusion")
        or "Insufficient data"
    )
    next_action = (
        summary.get("next_action")
        or final_recommendation.get("next_action")
        or "Review saved source reports before checkpoint approval."
    )
    executive_summary = summary.get("executive_summary") or ""

    return f"""
        <section class="reporting-table-card" style="margin-top:18px; border-left:5px solid #7bd7c5;">
            <div class="reporting-section-header reporting-section-header-row">
                <div>
                    <h3>Executive Checkpoint Conclusion</h3>
                    <p>Product Team decision language generated from saved round reports and validation KPI evidence.</p>
                </div>
                <span class="reporting-scope-chip">{e(conclusion)}</span>
            </div>
            <div style="font-size:15px; line-height:1.7; color:#344054;">
                {e(executive_summary)}
            </div>
            <div style="margin-top:12px; padding:12px 14px; border:1px solid #e5e7eb; border-radius:12px; background:#f9fafb;">
                <div class="historical-kicker">Next action</div>
                <div style="font-size:15px; color:#111827; font-weight:700; line-height:1.5;">
                    {e(next_action)}
                </div>
            </div>
        </section>
    """


def _render_project_report_kpi_progression(report: dict) -> str:
    kpi_progression = report.get("kpi_progression")
    if not isinstance(kpi_progression, list) or not kpi_progression:
        return f"""
            <section class="reporting-table-card" style="margin-top:18px;">
                <div class="reporting-section-header reporting-section-header-row">
                    <div>
                        <h3>KPI Summary and Progression</h3>
                        <p>No saved round or validation KPI progression was available in this generated Project Report.</p>
                    </div>
                    <span class="reporting-scope-chip">KPIs</span>
                </div>
            </section>
        """

    rows_html = ""
    for item in kpi_progression:
        if not isinstance(item, dict):
            continue

        suffix = item.get("suffix") or ""
        round_values = item.get("round_values") if isinstance(item.get("round_values"), list) else []
        round_value_html = ""

        for round_value in round_values:
            if not isinstance(round_value, dict):
                continue

            source_label = _project_report_kpi_source_label(round_value.get("source_type"))
            source_label_html = ""
            if source_label:
                source_label_html = f"""
                    <span style="font-size:11px; color:#667085; border-left:1px solid #e5e7eb; padding-left:6px;">
                        {e(source_label)}
                    </span>
                """

            round_value_html += f"""
                <span style="display:inline-flex; align-items:center; gap:4px; margin:2px 6px 2px 0; padding:4px 8px; border:1px solid #e5e7eb; border-radius:999px; background:#ffffff; white-space:nowrap;">
                    <strong>{e(round_value.get("round_label") or "Round")}</strong>
                    <span>{_project_report_metric_display(round_value.get("value"), suffix)}</span>
                    {source_label_html}
                </span>
            """

        if not round_value_html:
            round_value_html = "—"

        rows_html += f"""
            <tr>
                <td><strong>{e(item.get("label") or item.get("key") or "KPI")}</strong></td>
                <td>{round_value_html}</td>
                <td>{_project_report_metric_display(item.get("delta"), suffix)}</td>
                <td>{_project_report_metric_display(item.get("final_value"), suffix)}</td>
                <td>{_project_report_metric_display(item.get("target"), suffix)}</td>
                <td>{e(_project_report_status_label(item.get("status")))}</td>
            </tr>
        """

    return f"""
        <section class="reporting-table-card" style="margin-top:18px;">
            <div class="reporting-section-header reporting-section-header-row">
                <div>
                    <h3>KPI Summary and Progression</h3>
                    <p>Round-by-round Star Rating, NPS, and Ready for Sales using saved round reports plus validation KPI evidence when available.</p>
                </div>
                <span class="reporting-scope-chip">KPIs</span>
            </div>
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>KPI</th>
                            <th>Progression</th>
                            <th>Delta</th>
                            <th>Final</th>
                            <th>Threshold</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </section>
    """


def _project_report_issue_status_label(status: object) -> str:
    safe_status = str(status or "").strip().lower()

    labels = {
        "resolved": "Resolved",
        "improved": "Improved",
        "validated": "Validated",
        "persistent": "Persistent",
        "new": "New",
        "worsened": "Worsened",
        "watchout": "Watchout",
    }

    return labels.get(safe_status, safe_status.title() if safe_status else "Watchout")


def _project_report_issue_status_style(status: object) -> str:
    safe_status = str(status or "").strip().lower()

    if safe_status in {"resolved", "validated"}:
        return "background:#ecfdf3; color:#027a48; border-color:#abefc6;"

    if safe_status == "improved":
        return "background:#f0fdf9; color:#0f766e; border-color:#99f6e4;"

    if safe_status == "new":
        return "background:#fff7ed; color:#b45309; border-color:#fed7aa;"

    if safe_status == "worsened":
        return "background:#fef3f2; color:#b42318; border-color:#fecdca;"

    return "background:#fffbeb; color:#92400e; border-color:#fde68a;"


def _project_report_issue_meta_value(value: object) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def _project_report_risk_level_label(risk_level: object) -> str:
    safe_level = str(risk_level or "").strip().lower()

    labels = {
        "positive": "Positive",
        "low": "Low",
        "medium": "Medium",
        "high": "High",
    }

    return labels.get(safe_level, safe_level.title() if safe_level else "Watchout")


def _project_report_risk_level_style(risk_level: object) -> str:
    safe_level = str(risk_level or "").strip().lower()

    if safe_level == "positive":
        return "background:#ecfdf3; color:#027a48; border-color:#abefc6;"

    if safe_level == "low":
        return "background:#f0fdf9; color:#0f766e; border-color:#99f6e4;"

    if safe_level == "medium":
        return "background:#fffbeb; color:#92400e; border-color:#fde68a;"

    if safe_level == "high":
        return "background:#fef3f2; color:#b42318; border-color:#fecdca;"

    return "background:#eef2ff; color:#3730a3; border-color:#c7d2fe;"


def _render_project_report_risk_assessment(report: dict) -> str:
    risk_assessment = report.get("risk_assessment")
    if not isinstance(risk_assessment, list) or not risk_assessment:
        return """
            <section class="reporting-table-card" style="margin-top:18px;">
                <div class="reporting-section-header reporting-section-header-row">
                    <div>
                        <h3>Checkpoint Risk Assessment</h3>
                        <p>No checkpoint-level risk assessment was stored in this generated Project Report.</p>
                    </div>
                    <span class="reporting-scope-chip">Risk</span>
                </div>
            </section>
        """

    rows_html = ""

    for item in risk_assessment:
        if not isinstance(item, dict):
            continue

        signal = item.get("signal") or "Risk signal"
        risk_level = item.get("risk_level") or "watchout"
        risk_label = _project_report_risk_level_label(risk_level)
        risk_style = _project_report_risk_level_style(risk_level)
        evidence_strength = item.get("evidence_strength") or "—"
        trend = item.get("trend") or "—"
        validation = item.get("validation") or "—"
        decision_impact = item.get("decision_impact") or "—"
        summary = item.get("summary") or "No summary stored."
        source_issue_count = item.get("source_issue_count")
        raw_detail_type = item.get("raw_detail_type") or "project_synthesis"

        supporting_evidence = item.get("supporting_evidence")
        if not isinstance(supporting_evidence, list):
            supporting_evidence = []

        source_issue_names = item.get("source_issue_names")
        if not isinstance(source_issue_names, list):
            source_issue_names = []

        evidence_items = "".join(
            f"<li>{e(value)}</li>"
            for value in supporting_evidence[:8]
            if str(value or "").strip()
        )
        if not evidence_items:
            evidence_items = "<li>No supporting evidence stored.</li>"

        source_issue_items = "".join(
            f"<li>{e(value)}</li>"
            for value in source_issue_names[:8]
            if str(value or "").strip()
        )
        if not source_issue_items:
            source_issue_items = "<li>No source issue examples stored.</li>"

        rows_html += f"""
            <tr>
                <td style="font-size:12px; line-height:1.35;">
                    <strong style="color:#111827;">{e(signal)}</strong>
                    <div style="margin-top:3px; color:#667085; font-size:11px;">
                        {e(summary)}
                    </div>
                </td>
                <td style="font-size:12px; white-space:nowrap;">
                    <span style="
                        display:inline-flex;
                        align-items:center;
                        justify-content:center;
                        padding:3px 8px;
                        border:1px solid;
                        border-radius:999px;
                        font-size:11px;
                        font-weight:800;
                        white-space:nowrap;
                        {risk_style}
                    ">
                        {e(risk_label)}
                    </span>
                </td>
                <td style="font-size:12px; color:#475467;">
                    {e(evidence_strength)}
                </td>
                <td style="font-size:12px; color:#475467;">
                    {e(trend)}
                </td>
                <td style="font-size:12px; color:#475467;">
                    {e(validation)}
                </td>
                <td style="font-size:12px; color:#344054;">
                    <strong>{e(decision_impact)}</strong>
                </td>
                <td style="font-size:12px; white-space:nowrap;">
                    <details>
                        <summary style="cursor:pointer; color:#0f766e; font-weight:800;">
                            Evidence
                        </summary>
                        <div class="reporting-project-issue-detail-panel">
                            <div class="historical-kicker">Supporting evidence</div>
                            <ul style="margin:6px 0 12px 18px;">
                                {evidence_items}
                            </ul>

                            <div class="historical-kicker">Source issue examples</div>
                            <ul style="margin:6px 0 12px 18px;">
                                {source_issue_items}
                            </ul>

                            <div class="historical-kicker">Traceability</div>
                            <div style="margin-top:6px;">
                                Source issue count: {e(source_issue_count if source_issue_count is not None else "—")}<br>
                                Raw detail type: {e(raw_detail_type)}
                            </div>
                        </div>
                    </details>
                </td>
            </tr>
        """

    return f"""
        <section class="reporting-table-card" style="margin-top:18px;">
            <div class="reporting-section-header reporting-section-header-row">
                <div>
                    <h3>Checkpoint Risk Assessment</h3>
                    <p>Product Team checkpoint view. This groups raw feedback into decision-level signals so one-off comments do not dominate the report.</p>
                </div>
                <span class="reporting-scope-chip">Risk</span>
            </div>
            <div class="table-scroll">
                <table class="data-table" style="font-size:12px;">
                    <thead>
                        <tr>
                            <th>Signal</th>
                            <th>Risk</th>
                            <th>Evidence strength</th>
                            <th>Trend</th>
                            <th>Validation</th>
                            <th>Decision impact</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </section>
    """


def _render_project_report_issue_progression(report: dict) -> str:
    issue_progression = report.get("issue_progression")
    if not isinstance(issue_progression, list) or not issue_progression:
        return """
            <section class="reporting-table-card" style="margin-top:18px;">
                <div class="reporting-section-header reporting-section-header-row">
                    <div>
                        <h3>Detailed Issue Progression</h3>
                        <p>No issue progression was stored in this generated Project Report.</p>
                    </div>
                    <span class="reporting-scope-chip">Issues</span>
                </div>
            </section>
        """

    def _round_text(value: object) -> str:
        value_text = _project_report_issue_meta_value(value)
        if value_text == "—":
            return "—"
        if value_text.lower().startswith("round"):
            return value_text
        return f"Round {value_text}"

    def _joined_text(values: object) -> str:
        if isinstance(values, list):
            safe_values = [
                str(value).strip()
                for value in values
                if str(value or "").strip()
            ]
            if safe_values:
                return ", ".join(safe_values)

        if str(values or "").strip():
            return str(values).strip()

        return "—"

    def _list_items(values: object, *, empty_text: str) -> str:
        if not isinstance(values, list):
            values = []

        items_html = "".join(
            f"<li>{e(value)}</li>"
            for value in values[:6]
            if str(value or "").strip()
        )

        if items_html:
            return items_html

        return f"<li>{e(empty_text)}</li>"

    rows_html = ""

    for issue in issue_progression:
        if not isinstance(issue, dict):
            continue

        issue_name = issue.get("issue_name") or "Unnamed issue"
        status = issue.get("status") or "watchout"
        status_label = _project_report_issue_status_label(status)
        status_style = _project_report_issue_status_style(status)

        pre_validation_status = str(issue.get("pre_validation_status") or "").strip()

        first_seen_text = _round_text(issue.get("first_seen_round"))
        latest_seen_text = _round_text(issue.get("latest_seen_round"))
        latest_validation_text = _project_report_issue_meta_value(issue.get("latest_validation_label"))
        affected_rounds_text = _joined_text(issue.get("affected_rounds"))

        if latest_validation_text != "—":
            rounds_text = f"{first_seen_text} → {latest_seen_text} → {latest_validation_text}"
        else:
            rounds_text = f"{first_seen_text} → {latest_seen_text}"

        validation_status = str(issue.get("validation_status") or "").strip()
        validation_sources_text = _joined_text(issue.get("validation_sources"))

        validation_label = latest_validation_text if latest_validation_text != "—" else validation_sources_text

        if validation_status == "validation_passed":
            validation_text = f"{validation_label}: passed"
        elif validation_status == "validation_validated_with_kpi_watchout":
            validation_text = f"{validation_label}: validated, KPI watchout"
        elif validation_status == "validation_failed_or_mixed":
            validation_text = f"{validation_label}: mixed / failed KPI"
        elif validation_status:
            validation_text = f"{validation_label}: evidence present"
        else:
            validation_text = "No validation source"

        latest_evidence_text = _project_report_issue_meta_value(issue.get("latest_evidence_count"))
        total_evidence_text = _project_report_issue_meta_value(issue.get("total_evidence_count"))
        recommendation = issue.get("final_recommendation") or "Review before checkpoint approval."

        evidence_items = _list_items(
            issue.get("evidence"),
            empty_text="No short evidence excerpt stored.",
        )
        validation_evidence_items = _list_items(
            issue.get("validation_evidence"),
            empty_text="No validation KPI evidence stored for this issue.",
        )

        failed_kpis = issue.get("validation_failed_kpis")
        if isinstance(failed_kpis, list) and failed_kpis:
            failed_kpi_items = "".join(
                f"<li>{e(item.get('evidence_text') if isinstance(item, dict) else item)}</li>"
                for item in failed_kpis[:6]
                if str((item.get("evidence_text") if isinstance(item, dict) else item) or "").strip()
            )
        else:
            failed_kpi_items = "<li>No failed validation KPI stored.</li>"

        rows_html += f"""
            <tr title="{e(issue_name)}">
                <td>
                    <strong style="color:#111827;">{e(issue_name)}</strong>
                </td>
                <td style="font-size:12px;">
                    <span style="
                        display:inline-flex;
                        align-items:center;
                        justify-content:center;
                        padding:3px 8px;
                        border:1px solid;
                        border-radius:999px;
                        font-size:11px;
                        font-weight:800;
                        white-space:nowrap;
                        {status_style}
                    ">
                        {e(status_label)}
                    </span>
                </td>
                <td title="Affected: {e(affected_rounds_text)}">
                    <strong>{e(rounds_text)}</strong>
                </td>
                <td title="{e(validation_text)}">
                    {e(validation_text)}
                </td>
                <td title="{e(latest_evidence_text)} latest">
                    {e(total_evidence_text)} total
                </td>
                <td title="{e(recommendation)}">
                    {e(recommendation)}
                </td>
                <td>
                    <details>
                        <summary style="cursor:pointer; color:#0f766e; font-weight:800;">
                            Details
                        </summary>
                        <div class="reporting-project-issue-detail-panel">
                            <div class="historical-kicker">Evidence excerpts</div>
                            <ul style="margin:6px 0 12px 18px;">
                                {evidence_items}
                            </ul>

                            <div class="historical-kicker">Validation KPI evidence</div>
                            <ul style="margin:6px 0 12px 18px;">
                                {validation_evidence_items}
                            </ul>

                            <div class="historical-kicker">Failed validation KPIs</div>
                            <ul style="margin:6px 0 12px 18px;">
                                {failed_kpi_items}
                            </ul>

                            <div class="historical-kicker">Issue metadata</div>
                            <div style="margin-top:6px;">
                                First seen: {e(first_seen_text)}<br>
                                Latest analytical evidence: {e(latest_seen_text)}<br>
                                Latest validation evidence: {e(latest_validation_text)}<br>
                                Validation sources: {e(validation_sources_text)}
                            </div>
                        </div>
                    </details>
                </td>
            </tr>
        """

    return f"""
        <details class="reporting-table-card" style="margin-top:18px;">
            <summary style="cursor:pointer; list-style:none;">
                <div class="reporting-section-header reporting-section-header-row">
                    <div>
                        <h3>Raw Issue Evidence / Audit Trail</h3>
                        <p>Collapsed by default. This preserves traceability without making one-off comments the main Project Report story.</p>
                    </div>
                    <span class="reporting-scope-chip">Audit evidence</span>
                </div>
            </summary>
            <div class="table-scroll" style="margin-top:12px;">
                <table class="data-table reporting-project-issue-table">
                    <colgroup>
                        <col style="width:30%;">
                        <col style="width:9%;">
                        <col style="width:17%;">
                        <col style="width:18%;">
                        <col style="width:8%;">
                        <col style="width:12%;">
                        <col style="width:6%;">
                    </colgroup>
                    <thead>
                        <tr>
                            <th>Issue</th>
                            <th>Status</th>
                            <th>Rounds</th>
                            <th>Validation</th>
                            <th>Evidence</th>
                            <th>Recommendation</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </details>
    """


def _render_project_report_final_recommendation(report: dict) -> str:
    final_recommendation = report.get("final_recommendation")
    if not isinstance(final_recommendation, dict):
        return ""

    remaining_risks = final_recommendation.get("remaining_risks")
    accepted_watchouts = final_recommendation.get("accepted_watchouts")

    if not isinstance(remaining_risks, list):
        remaining_risks = []
    if not isinstance(accepted_watchouts, list):
        accepted_watchouts = []

    risk_items = "".join(f"<li>{e(item)}</li>" for item in remaining_risks[:8] if str(item or "").strip())
    watchout_items = "".join(f"<li>{e(item)}</li>" for item in accepted_watchouts[:8] if str(item or "").strip())

    if not risk_items:
        risk_items = "<li>No remaining risks stored in the generated Project Report.</li>"
    if not watchout_items:
        watchout_items = "<li>No accepted watchouts stored in the generated Project Report.</li>"

    return f"""
        <section class="reporting-table-card" style="margin-top:18px;">
            <div class="reporting-section-header reporting-section-header-row">
                <div>
                    <h3>Final Risks and Recommendation</h3>
                    <p>Short Product Team checkpoint language. Audit counts are intentionally excluded from this decision block.</p>
                </div>
                <span class="reporting-scope-chip">Recommendation</span>
            </div>
            <div style="display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px;">
                <div style="padding:12px 14px; border:1px solid #e5e7eb; border-radius:12px; background:#ffffff;">
                    <div class="historical-kicker">Remaining risks</div>
                    <ul style="margin:8px 0 0 18px; color:#475467; line-height:1.55;">
                        {risk_items}
                    </ul>
                </div>
                <div style="padding:12px 14px; border:1px solid #e5e7eb; border-radius:12px; background:#ffffff;">
                    <div class="historical-kicker">Accepted watchouts</div>
                    <ul style="margin:8px 0 0 18px; color:#475467; line-height:1.55;">
                        {watchout_items}
                    </ul>
                </div>
            </div>
        </section>
    """


def _project_report_without_source_details(report: dict) -> dict:
    if not isinstance(report, dict):
        return {}

    display_report = dict(report)
    display_report["source_surveys"] = []

    sections = report.get("sections")
    if isinstance(sections, list):
        display_report["sections"] = [
            section for section in sections
            if not (
                isinstance(section, dict)
                and section.get("report_group") == "Detailed Issue Progression"
            )
        ]

    return display_report


def render_reporting_project_report_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    GET /reporting/insights/projects/project-report

    Read-only project-level report view for generated Reporting & Insights project reports.
    """

    from app.db.reporting_project_reports import get_reporting_project_report_for_reporting_insights
    from app.services.canonical_report_renderer import render_canonical_report_panel

    query_params = query_params or {}
    project_key = _posted_scalar(query_params.get("project_key"))
    project_key = str(project_key or "").strip()

    if not project_key:
        return {"redirect": "/reporting/insights/projects?error=missing_project_key"}

    report_result = get_reporting_project_report_for_reporting_insights(project_key=project_key)
    if not report_result.get("success"):
        return {"redirect": "/reporting/insights/projects?error=project_report_not_found"}

    report = report_result.get("report") or {}
    row = report_result.get("row") or {}
    product = report.get("product") if isinstance(report.get("product"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}

    report_title = (
        product.get("project_label")
        or row.get("project_label")
        or "Project Report"
    )

    source_reports_html = _render_reporting_project_report_source_table(report.get("source_reports") or [])
    checkpoint_html = _render_project_report_checkpoint_summary(report)
    kpi_progression_html = _render_project_report_kpi_progression(report)
    risk_assessment_html = _render_project_report_risk_assessment(report)
    issue_progression_html = _render_project_report_issue_progression(report)
    final_recommendation_html = _render_project_report_final_recommendation(report)
    generated_label = _project_report_generated_label(report, row)
    source_status_notice_html = _render_project_report_source_status_notice(report)

    body_html = render_canonical_report_panel(
        report=_project_report_without_source_details(report),
        panel_id="reporting-project-report",
        panel_title="Project Report Details",
        panel_status="Generated",
        notice_html="",
        primary_action_html="",
        source_title="Source Details / Audit Trail",
    )

    html = f"""
    <div class="results-section reporting-insights-page">
        <div class="reporting-comparison-title-row">
            <div>
                <h2>{e(report_title)}</h2>
                <p class="historical-page-description">
                    Generated Project Report using {e(summary.get("analytical_source_report_count") or 0)} saved analytical source report(s)
                    and {e(summary.get("validation_kpi_source_count") or 0)} validation KPI source(s).
                    Source inventory and row counts are kept in the audit trail at the bottom.
                    <br>
                    <strong>{e(generated_label)}</strong>
                </p>
            </div>
            <a class="historical-action-pill is-secondary" href="/reporting/insights/projects">Back to Projects</a>
        </div>
        {checkpoint_html}
        {source_status_notice_html}
        {kpi_progression_html}
        {risk_assessment_html}
        {body_html}
        {final_recommendation_html}
        {issue_progression_html}
        {source_reports_html}
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

def _format_comparison_kpi_value(value, suffix=""):
    if value in (None, ""):
        return "—"
    return f"{e(value)}{e(suffix)}"


def _render_category_kpi_snapshot(category_kpis: dict) -> str:
    if not isinstance(category_kpis, dict) or not category_kpis:
        return """
            <div class="reporting-comparison-item-card is-empty">
                <p>No category KPI snapshot was saved with this comparison.</p>
            </div>
        """

    kpi_specs = [
        ("star_rating", "Star Rating", " / 5"),
        ("nps", "Recommendation / NPS", ""),
        ("ready_for_sales", "Ready for Sales", "%"),
        ("software_rating", "Software Rating", " / 5"),
    ]

    cards_html = ""
    for key, label, suffix in kpi_specs:
        kpi = category_kpis.get(key) if isinstance(category_kpis.get(key), dict) else {}
        if not kpi:
            continue

        average = kpi.get("weighted_average")
        range_info = kpi.get("range") if isinstance(kpi.get("range"), dict) else {}
        range_copy = ""
        if range_info.get("min") is not None and range_info.get("max") is not None:
            range_copy = f"Range: {e(range_info.get('min'))}–{e(range_info.get('max'))}{e(suffix)}"

        extra_copy = ""
        if key == "ready_for_sales" and kpi.get("total_blocking_no") not in (None, ""):
            extra_copy = f"Blocking No total: {e(kpi.get('total_blocking_no'))}"

        cards_html += f"""
            <div class="reporting-comparison-item-card">
                <div class="historical-kicker">{e(label)}</div>
                <h4>{_format_comparison_kpi_value(average, suffix)}</h4>
                <p>{range_copy or 'No range available.'}</p>
                {f'<p>{extra_copy}</p>' if extra_copy else ''}
            </div>
        """

    if not cards_html:
        cards_html = """
            <div class="reporting-comparison-item-card is-empty">
                <p>No populated category KPIs were saved with this comparison.</p>
            </div>
        """

    return f"<div class='reporting-comparison-card-grid'>{cards_html}</div>"


def _first_sentence_preview(value, *, fallback="No theme summary saved.", max_chars=180) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return fallback

    sentence_end = None
    for marker in (". ", "! ", "? "):
        marker_index = text.find(marker)
        if marker_index >= 0:
            sentence_end = marker_index + 1 if sentence_end is None else min(sentence_end, marker_index + 1)

    if sentence_end is not None:
        return text[:sentence_end].strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars].rstrip() + "…"


def _render_theme_analysis_cards(theme_analyses) -> str:
    if not isinstance(theme_analyses, list):
        theme_analyses = []

    cards_html = ""
    for theme in theme_analyses:
        if not isinstance(theme, dict):
            continue

        theme_name = theme.get("theme_name") or theme.get("theme_key") or "Theme"
        source_report_count = theme.get("source_report_count") or 0
        summary_preview = _first_sentence_preview(theme.get("summary"))

        questions_html = _render_text_list(
            theme.get("product_team_questions"),
            empty_text="No saved questions for this theme.",
        )
        positives = _render_comparison_item_cards(
            theme.get("positives"),
            title_key="theme",
            body_key="why_it_matters",
            fallback_title="Positive pattern",
        )
        negatives = _render_comparison_item_cards(
            theme.get("negatives"),
            title_key="theme",
            body_key="why_it_matters",
            fallback_title="Negative pattern",
        )
        product_specific = _render_comparison_item_cards(
            theme.get("product_specific_patterns"),
            title_key="report_label",
            body_key="pattern",
            fallback_title="Product-specific pattern",
        )
        evidence_gaps = _render_text_list(
            theme.get("evidence_gaps"),
            empty_text="No saved evidence gaps for this theme.",
        )

        status = str(theme.get("ai_status") or "generated").strip()
        failed_notice = ""
        if status == "failed":
            failed_notice = f"""
                <div class="notice-card warning">
                    This theme chunk did not complete in the AI pass.
                    Error: {e(theme.get('ai_error') or 'unknown')}
                </div>
            """

        cards_html += f"""
            <details class="reporting-comparison-section">
                <summary class="reporting-theme-summary-row">
                    <span class="reporting-theme-title-block">
                        <span class="reporting-theme-title">{e(theme_name)}</span>
                        <span class="reporting-theme-summary-preview">{e(summary_preview)}</span>
                    </span>
                    <span class="reporting-scope-chip reporting-theme-report-count">{e(source_report_count)} report(s)</span>
                </summary>
                <div class="reporting-comparison-section-body">
                    {failed_notice}
                    <p class="reporting-comparison-summary-copy">{e(theme.get('summary') or 'No theme summary saved.')}</p>
                    <h3>Category pattern</h3>
                    <p>{e(theme.get('category_pattern') or 'No category pattern saved.')}</p>
                    <h3>Product-specific patterns</h3>
                    {product_specific}
                    <h3>User expectation</h3>
                    <p>{e(theme.get('user_expectation') or 'No user expectation saved.')}</p>
                    <h3>Theme positives</h3>
                    {positives}
                    <h3>Theme negatives</h3>
                    {negatives}
                    <h3>Evidence gaps</h3>
                    {evidence_gaps}
                    <h3>Product Team questions</h3>
                    {questions_html}
                </div>
            </details>
        """

    if not cards_html:
        return """
            <div class="reporting-comparison-item-card is-empty">
                <p>No saved theme analyses yet.</p>
            </div>
        """

    return f"""
        <div class="reporting-theme-analysis-list">
            {cards_html}
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

    category_kpi_body = _render_category_kpi_snapshot(report.get("category_kpi_snapshot"))
    theme_analysis_body = _render_theme_analysis_cards(report.get("theme_analyses"))

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
        {_render_comparison_details(title="Category KPI snapshot", body_html=category_kpi_body, open_by_default=True, kicker="KPIs")}
        {_render_comparison_details(title="Theme-level category analysis", body_html=theme_analysis_body, open_by_default=True, kicker="Themes")}
        {_render_comparison_details(title="Category patterns", body_html=category_patterns_body, open_by_default=False)}
        {_render_comparison_details(title="Sentiment drivers", body_html=sentiment_body, open_by_default=False)}
        {_render_comparison_details(title="Decision guidance", body_html=decision_guidance_body, open_by_default=False)}
        {_render_comparison_details(title="User tolerance, use cases, and next questions", body_html=behavior_questions_body, open_by_default=False)}
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

def render_reporting_product_trial_report_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
    query_params: dict | None = None,
):
    """
    GET /reporting/insights/product-trial-report

    Read-only Product Trial report view for reports published to R&I.
    """

    from app.db.product_trial_reports import get_published_product_trial_report_for_reporting_insights
    from app.services.canonical_report_renderer import render_canonical_report_panel

    query_params = query_params or {}
    round_id = _posted_scalar(query_params.get("round_id"))

    try:
        safe_round_id = int(round_id)
    except (TypeError, ValueError):
        return {"redirect": "/reporting/insights/rounds?error=invalid_report"}

    report_result = get_published_product_trial_report_for_reporting_insights(
        round_id=safe_round_id,
    )
    if not report_result.get("success"):
        return {"redirect": "/reporting/insights/rounds?error=report_not_found"}

    report = report_result.get("report") or {}
    row = report_result.get("row") or {}

    report_title = _format_project_round_label({
        "internal_name": row.get("internal_name"),
        "market_name": row.get("market_name"),
        "round_number": row.get("round_number"),
    })

    body_html = render_canonical_report_panel(
        report=report,
        panel_id="published-product-trial-report",
        panel_title="Published Product Trial Report",
        panel_status="Published",
        notice_html="",
        primary_action_html='<a class="historical-action-pill is-secondary" href="/reporting/insights/rounds">Back to Rounds</a>',
        source_title="Report Source Details",
    )

    html = f"""
    <div class="results-section reporting-insights-page">
        <div class="reporting-comparison-title-row">
            <div>
                <h2>{e(report_title)}</h2>
                <p class="historical-page-description">
                    This Product Trial report was published to Reporting & Insights.
                </p>
            </div>
            <a class="historical-action-pill is-secondary" href="/reporting/insights/rounds">Back to Rounds</a>
        </div>
        {body_html}
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_reporting_project_report_generate_post(*, user_id: str, data: dict):
    """
    POST /reporting/insights/projects/generate-report

    Generate or regenerate a DB-backed project-level report.
    """

    from urllib.parse import quote_plus
    from app.services.project_report_service import generate_project_report

    project_key = _posted_scalar(data.get("project_key"))
    project_key = str(project_key or "").strip()

    if not project_key:
        return {"redirect": "/reporting/insights/projects?error=missing_project_key"}

    result = generate_project_report(
        project_key=project_key,
        generated_by_user_id=user_id,
    )

    if not result.get("success"):
        error = result.get("error") or "generation_failed"
        return {"redirect": f"/reporting/insights/projects?error={quote_plus(error)}"}

    return {"redirect": "/reporting/insights/projects?project_report=generated"}


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