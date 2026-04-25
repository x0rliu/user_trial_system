# app/handlers/historical.py

from app.services.historical_ingestion import ingest_historical_csv


def handle_historical_upload_post(data):

    context_id = data.get("context_id")
    dataset_type = (data.get("dataset_type") or "").strip()

    # 🔥 HARD CLEAN (critical for your parser)
    dataset_type = dataset_type.split("\r\n")[0]

    file_item = data.get("file")

    if not context_id or not dataset_type or not file_item or not file_item.get("filename"):
        return {"redirect": "/historical/upload?error=missing"}

    try:
        context_id = int(context_id)
    except:
        return {"redirect": "/historical/upload?error=invalid_context"}

    from app.db.historical import dataset_exists_for_context

    if dataset_exists_for_context(context_id, dataset_type):
        return {
            "redirect": f"/historical/upload?context_id={context_id}&error=duplicate_dataset"
        }

    from io import BytesIO

    print("DEBUG dataset_type RAW:", repr(dataset_type))
    print("DEBUG dataset_type LEN:", len(dataset_type))

    ingest_historical_csv(
        context_id=context_id,
        dataset_type=dataset_type,
        # file_bytes = file_item["file"],
        file_obj=BytesIO(file_item["file"]),
        filename=file_item["filename"]
    )

    return {"redirect": f"/historical/context?context_id={context_id}"}

from app.db.historical import (
    get_context_with_product,
    get_datasets_by_context,
    get_historical_metrics_by_context
)
from app.utils.html_escape import escape_html as e
from app.db.historical import get_latest_insights_by_context


def render_historical_context_get(
    user_id,
    base_template,
    inject_nav,
    context_id,
    query_params
):

    # -------------------------
    # Fetch data (NO raw SQL here)
    # -------------------------
    context = get_context_with_product(context_id)
    datasets = get_datasets_by_context(context_id)
    metrics = get_historical_metrics_by_context(context_id)
    insights = get_latest_insights_by_context(context_id)

    if not context:
        return {"redirect": "/historical"}

    # -------------------------
    # Format context
    # -------------------------
    internal = e(context.get("internal_name") or "")
    market = e(context.get("market_name") or "")
    product_name = f"{internal} ({market})" if market else internal

    round_number = context.get("round_number") or "-"
    lifecycle = e(context.get("lifecycle_stage") or "-")
    purpose = e(context.get("trial_purpose") or "-")
    invited = context.get("invited_user_count") or "-"

    # -------------------------
    # Build HTML
    # -------------------------
    html = f"""
    <div class="results-section">

        <h2>{product_name} — Trial Context</h2>

        <!-- OVERVIEW -->
        <div class="card">
            <h3>Overview</h3>
            <div><strong>Round:</strong> {round_number}</div>
            <div><strong>Lifecycle:</strong> {lifecycle}</div>
            <div><strong>Purpose:</strong> {purpose}</div>
            <div><strong>Invited Users:</strong> {invited}</div>
        </div>
    """

    # -------------------------
    # DATASETS
    # -------------------------
    html += """
        <div class="card" style="margin-top:20px;">
            <h3>Datasets</h3>
    """

    if not datasets:
        html += "<p>No datasets uploaded yet.</p>"
    else:
        html += "<ul>"
        for d in datasets:
            dtype = e(d.get("dataset_type") or "")
            fname = e(d.get("source_file_name") or "")
            html += f"<li><strong>{dtype}</strong> — {fname}</li>"
        html += "</ul>"

    html += f"""
        <div style="margin-top:10px;">
            <a href="/historical/upload?context_id={context_id}">
                + Upload Dataset
            </a>
        </div>
        </div>
    """

    # -------------------------
    # METRICS
    # -------------------------
    html += """
        <div class="card" style="margin-top:20px;">
            <h3>Metrics</h3>
    """

    if not metrics:
        html += "<p>No metrics computed yet.</p>"
    else:
        html += f"""
            <div><strong>Total Responses:</strong> {metrics.get('total_responses')}</div>
            <div><strong>Completion Rate:</strong> {metrics.get('completion_rate')}</div>
            <div><strong>Avg Response Length:</strong> {metrics.get('avg_response_length')}</div>
            <div><strong>Empty Response Rate:</strong> {metrics.get('empty_response_rate')}</div>
        """

    html += "</div>"

    # -------------------------
    # INSIGHTS
    # -------------------------
    html += """
        <div class="card" style="margin-top:20px;">
            <h3>Insights</h3>
    """

    if not insights:
        html += "<p>No insights generated yet.</p>"
    else:
        for insight in insights:
            section = e(insight.get("section_name") or "")
            summary = e(insight.get("insight_summary") or "")

            html += f"""
            <div class="insight-block" style="margin-bottom:12px;">
                <strong>{section}</strong>
                <div>{summary}</div>
            </div>
            """

    html += """
        </div>
    </div>
    """

    # -------------------------
    # Final render
    # -------------------------
    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

from app.db.historical import get_all_historical_contexts


def render_historical_landing_get(user_id, base_template, inject_nav):

    contexts = get_all_historical_contexts()

    html = "<div class='results-section'>"
    html += "<h2>Legacy Trial History</h2>"

    html += """
    <div style="margin-bottom: 16px;">
        <a href="/historical/create-context" class="btn-primary">
            + Create Legacy Context
        </a>
    </div>
    """

    if not contexts:
        html += "<p>No historical trials loaded yet.</p>"
    else:
        html += "<div class='context-list'>"

        for ctx in contexts:
            context_id = ctx.get("context_id")
            name = ctx.get("context_name") or "Unnamed Trial"
            internal_name = ctx.get("internal_name")
            market_name = ctx.get("market_name")

            # Display logic
            if market_name:
                product = f"{internal_name} ({market_name})"
            else:
                product = internal_name or "Unknown Product"

            round_number = ctx.get("round_number")
            stage = ctx.get("lifecycle_stage")
            purpose = ctx.get("trial_purpose")

            name_parts = [product]

            if round_number:
                name_parts.append(f"R{round_number}")

            if stage:
                name_parts.append(stage)

            if purpose:
                name_parts.append(purpose)

            name = " — ".join(name_parts)
            created = ctx.get("created_at") or ""

            html += f"""
            <div class="context-item">
                <a href="/historical/context?context_id={context_id}">
                    <strong>{name}</strong>
                </a>
                <div class="context-meta">
                    {product} {created}
                </div>
            </div>
            """

        html += "</div>"

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

from app.db.historical import get_all_historical_contexts
from app.db.connection import get_db_connection


from app.db.connection import get_db_connection

def render_historical_upload_get(user_id, base_template, inject_nav, context_id, query_params):

    from app.db.historical import get_context_with_product, get_datasets_by_context

    context = get_context_with_product(context_id)
    error = query_params.get("error", [None])[0]
    
    if not context:
        return {"redirect": "/historical"}

    datasets = get_datasets_by_context(context_id)

    if not context:
        return {"redirect": "/historical"}

    # -------------------------
    # Build HTML
    # -------------------------
    from app.utils.html_escape import escape_html as e

    safe_context_id = e(str(context_id))

    html = f"""
    <div class="results-section">
        <h2>Upload Data for Context #{safe_context_id}</h2>
    """

    # -------------------------
    # Error block (OUTSIDE f-string)
    # -------------------------
    if error == "duplicate_dataset":
        html += """
        <div class="alert alert-error">
            Dataset already exists for this context.
        </div>
        """

    # -------------------------
    # Continue HTML
    # -------------------------
    html += f"""
        <form method="POST" action="/historical/upload" enctype="multipart/form-data">

            <input type="hidden" name="context_id" value="{safe_context_id}">

            <label>Dataset Name:</label><br>
            <input type="text" name="dataset_type" placeholder="e.g. survey_1, validation_round2" required><br><br>

            <label>CSV File:</label><br>
            <input type="file" name="file" required><br><br>

            <button type="submit">Upload</button>

        </form>
    </div>
    """
    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_historical_create_context_post(data):

    product_id = data.get("product_id", [""])[0]
    round_number = data.get("round_number", [""])[0]
    lifecycle_stage = data.get("lifecycle_stage", [""])[0]
    trial_purpose = data.get("trial_purpose", [""])[0]
    mix = data.get("internal_vs_external_mix", [""])[0]
    invited = data.get("invited_user_count", [""])[0]
    description = data.get("description", [""])[0]

# -------------------------
# Validate required fields
# -------------------------

    if not product_id:
        return {"error": "missing_product"}

    if not lifecycle_stage:
        return {"error": "missing_stage"}

    if not trial_purpose:
        return {"error": "missing_purpose"}

    if not mix:
        return {"error": "missing_scope"}

    try:
        product_id = int(product_id)
    except:
        return {"error": "invalid_product"}

    round_number = int(round_number) if round_number else None
    invited = int(invited) if invited else None

    from app.db.historical import create_historical_context

    context_id = create_historical_context(
        product_id,
        round_number,
        lifecycle_stage,
        trial_purpose,
        mix,
        invited,
        description
    )

    return {
        "redirect": f"/historical/upload?context_id={context_id}"
    }

from app.db.connection import get_db_connection
from app.utils.html_escape import escape_html as e

def render_historical_create_context_get(user_id, base_template, inject_nav):

    from app.db.historical import get_all_products_for_context_creation

    products = get_all_products_for_context_creation()

    product_options = ""

    for p in products:
        internal = e(p.get("internal_name") or "")
        market = e(p.get("market_name") or "")

        label = internal
        if market:
            label += f" ({market})"

        product_options += f"<option value='{p['product_id']}'>{label}</option>"

    html = f"""
    <div class="results-section">
        <h2>Create Legacy Trial Context</h2>

        <form method="POST" action="/historical/create-context" class="form-stack">

            <div class="form-group">
                <label>Product</label>
                <select name="product_id" class="form-input" required>
                    <option value="" disabled selected>Select your product</option>
                    {product_options}
                </select>
            </div>

            <div class="form-group">
                <label>Lifecycle Stage</label>
                <select name="lifecycle_stage" class="form-input" required>
                    <option value="" disabled selected>Select your stage</option>
                    <option value="Pre G1">Pre G1</option>
                    <option value="PB1">PB1</option>
                    <option value="PB2">PB2</option>
                    <option value="PBX">PBX</option>
                    <option value="GX">GX</option>
                </select>
            </div>

            <div class="form-group">
                <label>Trial Purpose</label>
                <select name="trial_purpose" class="form-input" required>
                    <option value="" disabled selected>Select your purpose</option>
                    <option value="Mechanical">Mechanical</option>
                    <option value="Functional">Functional</option>
                    <option value="Standard Trial">Standard Trial</option>
                    <option value="Software Focused">Software Focused</option>
                </select>
            </div>

            <div class="form-group">
                <label>Internal vs External</label>
                <select name="internal_vs_external_mix" class="form-input" required>
                    <option value="" disabled selected>Set user scope</option>
                    <option value="Internal">Internal</option>
                    <option value="External">External</option>
                    <option value="Hybrid">Hybrid</option>
                </select>
            </div>

            <div class="form-group">
                <label>Invited User Count</label>
                <input type="number" name="invited_user_count" class="form-input" value="30">
            </div>

            <div class="form-group">
                <label>Description (Optional)</label>
                <textarea name="description" class="form-input" rows="4"></textarea>
            </div>

            <div style="margin-top: 16px;">
                <button type="submit" class="btn-primary">Create Context</button>
            </div>

            <div style="margin-top: 12px; font-size: 13px; color: #666;">
                After creating this context, you will upload survey data in the next step.
            </div>

        </form>
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}

from app.db.historical import get_legacy_contexts
from app.utils.html_escape import escape_html as e


def render_historical_landing_get(user_id, base_template, inject_nav):

    contexts = get_legacy_contexts()

    html = """
    <div class="results-section">
        <h2>Legacy Trial History</h2>

        <div style="margin-bottom: 16px;">
            <a href="/historical/create-context" class="btn-secondary">
                + Create Legacy Context
            </a>
        </div>
    """

    if not contexts:
        html += "<p>No historical trials loaded yet.</p>"
    else:
        html += """
        <table class="data-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Product</th>
                    <th>Internal</th>
                    <th>Round</th>
                    <th>Lifecycle</th>
                    <th>Purpose</th>
                    <th>Report</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
        """

        for idx, c in enumerate(contexts, start=1):

            product = e(c.get("market_name") or "-")
            internal = e(c.get("internal_name") or "-")
            round_number = c.get("round_number") or "-"
            lifecycle = e(c.get("lifecycle_stage") or "-")
            purpose = e(c.get("trial_purpose") or "-")
            context_id = c.get("context_id")

            html += f"""
            <tr>
                <td>{idx}</td>
                <td>{product}</td>
                <td>{internal}</td>
                <td>{round_number}</td>
                <td>{lifecycle}</td>
                <td>{purpose}</td>
                <td>
                    <a href="/historical/context?context_id={context_id}">
                        View
                    </a>
                </td>
                <td>
                    <a href="/historical/upload?context_id={context_id}">
                        Upload
                    </a>
                </td>
            </tr>
            """

        html += """
            </tbody>
        </table>
        """

    html += "</div>"

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}