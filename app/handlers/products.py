from app.db.products import create_product
from app.utils.html_escape import escape_html as e


def render_create_product_get(user_id, base_template, inject_nav):

    html = """
    <div class="results-section">
        <h2>Create Product</h2>

        <form method="POST" action="/products/create" class="form-stack">

            <div class="form-group">
                <label>Internal Name</label>
                <input type="text" name="internal_name" class="form-input" required>
            </div>

            <div class="form-group">
                <label>Market Name</label>
                <input type="text" name="market_name" class="form-input">
            </div>

            <div class="form-group">
                <label>Product Type</label>
                <select name="product_type_key" class="form-input" required>
                    <option value="headset">Headset</option>
                    <option value="mouse">Mouse</option>
                    <option value="keyboard">Keyboard</option>
                    <option value="webcam">Webcam</option>
                </select>
            </div>

            <div class="form-group">
                <label>Business Group</label>
                <select name="business_group" class="form-input" required>
                    <option value="Gaming">Gaming</option>
                    <option value="PWS">PWS</option>
                </select>
            </div>

            <div style="margin-top:16px;">
                <button type="submit" class="btn-primary">Create Product</button>
            </div>

        </form>
    </div>
    """

    full_html = base_template.replace("__BODY__", html)
    full_html = inject_nav(full_html, mode="internal")

    return {"html": full_html}


def handle_create_product_post(data):

    internal_name = data.get("internal_name", [""])[0]
    market_name = data.get("market_name", [""])[0]
    product_type_key = data.get("product_type_key", [""])[0]
    business_group = data.get("business_group", [""])[0]

    if not internal_name or not product_type_key or not business_group:
        return {"error": "missing"}

    product_id = create_product(
        internal_name,
        market_name,
        product_type_key,
        business_group
    )

    return {"redirect": f"/historical/create-context"}