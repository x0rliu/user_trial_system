# app/handlers/reporting_insights.py

from app.utils.html_escape import escape_html as e


REPORTING_VIEW_CONFIG = {
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


def _render_projects_view(published_reports):
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
            <td>{e(str(published_at)) if published_at else "—"}</td>
        </tr>
        """

    if not report_rows_html:
        report_rows_html = """
        <tr>
            <td colspan="6">
                <div class="empty-state">
                    <p class="empty-state-description">
                        No project reports have been published to Reporting & Insights yet.
                    </p>
                </div>
            </td>
        </tr>
        """

    overflow_note = ""
    if len(published_reports) > 10:
        overflow_note = f"""
        <div class="reporting-bounded-note">
            Showing the 10 latest reports. Search and pagination will be added after the reporting object model is stable.
        </div>
        """

    return f"""
    <section class="reporting-table-card">
        <div class="reporting-section-header reporting-section-header-row">
            <div>
                <h3>Latest published project reports</h3>
                <p>
                    Reports & Insights treats every published project-round report as a report object. The source can be legacy or current trial data.
                </p>
            </div>
            <span class="reporting-scope-chip">Projects</span>
        </div>
        <div class="table-scroll">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Project Round</th>
                        <th>Source</th>
                        <th>BG</th>
                        <th>Product Type</th>
                        <th>Surveys</th>
                        <th>Published</th>
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


def _render_product_types_view(published_reports):
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

        if report_count >= 2:
            readiness_badge = "<span class='reporting-readiness-badge is-ready'>Ready for comparison</span>"
            insight_note = "This insight group auto-updates when another published report in this product type becomes visible to Reporting & Insights."
        else:
            readiness_badge = "<span class='reporting-readiness-badge is-limited'>Needs more reports</span>"
            insight_note = "One report is useful context, but not enough for cross-product pattern claims."

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
                <td>{e(str(published_at)) if published_at else "—"}</td>
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
            </summary>
            <div class="reporting-product-type-row-detail">
                <p>{insight_note}</p>
                <div class="table-scroll">
                    <table class="data-table reporting-product-type-project-table">
                        <thead>
                            <tr>
                                <th>Included Project Round</th>
                                <th>Source</th>
                                <th>BG</th>
                                <th>Surveys</th>
                                <th>Published</th>
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
                    Product types are insight groups built from the currently published project-round reports, regardless of source.
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
    active_view: str = "projects",
):
    """
    GET /reporting/insights/*

    Reporting hub for published reports and cross-product insights.
    """

    from app.db.historical_aggregate_reports import list_published_historical_aggregate_reports_for_reporting_insights

    if active_view not in REPORTING_VIEW_CONFIG:
        active_view = "projects"

    published_reports = list_published_historical_aggregate_reports_for_reporting_insights()

    total_reports = len(published_reports)
    product_types = sorted({
        str(report.get("product_type_display") or "-")
        for report in published_reports
    })
    business_groups = sorted({
        str(report.get("business_group") or "-")
        for report in published_reports
    })

    if active_view == "projects":
        active_content_html = _render_projects_view(published_reports)
    elif active_view == "product_types":
        active_content_html = _render_product_types_view(published_reports)
    else:
        active_content_html = _render_fpo_view(active_view)

    html = f"""
    <div class="results-section reporting-insights-page">
        <div class="reporting-hero">
            <div>
                <div class="historical-kicker">Reporting & Insights</div>
                <h2>Published Project Reports</h2>
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