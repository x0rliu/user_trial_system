from app.db.user_profiles import get_profile_levels_by_category

def handle_api_profile_levels(query_params):

    category_id = query_params.get("category_id", [None])[0]

    if not category_id:
        return {"json": []}

    rows = get_profile_levels_by_category(category_id)

    return {"json": rows}