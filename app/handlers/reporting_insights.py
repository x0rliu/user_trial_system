# app/handlers/reporting_insights.py

from app.utils.html_escape import escape_html as e


def render_reporting_insights_get(
    *,
    user_id: str,
    base_template: str,
    inject_nav,
):
    """
    GET /reporting/insights

    Management-facing reporting hub for published reports and cross-product insights.
    """

    from app.db.historical import get_published_historical_products_for_reporting_insights

    published_reports = get_published_historical_products_for_reporting_insights()

    total_reports = len(published_reports)
    product_types = sorted({
        str(report.get("product_type_display") or "-")
        for report in published_reports
    })
    business_groups = sorted({
        str(report.get("business_group") or "-")
        for report in published_reports
    })

    report_rows_html = ""

    for report in published_reports:
        product_id = report.get("product_id")
        internal_name = e(report.get("internal_name") or "-")
        market_name = e(report.get("market_name") or "-")
        business_group = e(report.get("business_group") or "-")
        product_type = e(report.get("product_type_display") or "-")
        round_count = int(report.get("round_count") or 0)
        survey_count = int(report.get("survey_count") or 0)
        dataset_count = int(report.get("dataset_count") or 0)
        published_at = report.get("published_at") or ""

        round_label = "round" if round_count == 1 else "rounds"
        survey_label = "survey" if survey_count == 1 else "surveys"
        dataset_label = "dataset" if dataset_count == 1 else "datasets"

        report_rows_html += f"""
        <tr>
            <td>
                <a class="reporting-product-link" href="/historical/product?product_id={e(str(product_id))}">
                    {internal_name} <span>({market_name})</span>
                </a>
            </td>
            <td>{business_group}</td>
            <td>{product_type}</td>
            <td>{round_count} {round_label}</td>
            <td>{survey_count} {survey_label} ({dataset_count} {dataset_label})</td>
            <td>{e(str(published_at)) if published_at else "—"}</td>
        </tr>
        """

    if not report_rows_html:
        report_rows_html = """
        <tr>
            <td colspan="6">
                <div class="empty-state">
                    <p class="empty-state-description">
                        No product lifecycle reports have been published to Reporting & Insights yet.
                    </p>
                </div>
            </td>
        </tr>
        """

    html = f"""
    <div class="results-section reporting-insights-page">
        <div class="reporting-hero">
            <div>
                <div class="historical-kicker">Reporting & Insights</div>
                <h2>Published Product Lifecycle Reports</h2>
                <p class="historical-page-description">
                    Review product-level historical reports that have been published for cross-trial analysis.
                    Product-type insight generation will build from this published report set.
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

        <section class="reporting-table-card">
            <div class="reporting-section-header">
                <h3>Published reports</h3>
                <p>
                    This list is DB-backed from historical_report_publications where Reporting & Insights visibility is enabled.
                </p>
            </div>
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>BG</th>
                            <th>Product Type</th>
                            <th>Rounds</th>
                            <th>Surveys</th>
                            <th>Published</th>
                        </tr>
                    </thead>
                    <tbody>
                        {report_rows_html}
                    </tbody>
                </table>
            </div>
        </section>
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}