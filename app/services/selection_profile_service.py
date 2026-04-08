# services/selection_profile_service.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_effective_profile_criteria(*, session_id: int, round_id: int):
    """
    Merge baseline + overrides into structured profile criteria
    with readable category / level labels for display.
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        result = {}

        def ensure_category(cat_id, category_name):
            if cat_id not in result:
                result[cat_id] = {
                    "category_id": cat_id,
                    "category_name": category_name or f"Category {cat_id}",
                    "include": {},
                    "exclude": {},
                    "boost": {},
                    "deprioritize": {},
                }
            elif category_name and not result[cat_id].get("category_name"):
                result[cat_id]["category_name"] = category_name

        # -------------------------
        # BASELINE
        # -------------------------
        cur.execute("""
            SELECT
                rpc.ProfileUID,
                rpc.Operator,
                up.CategoryID,
                up.CategoryName,
                up.LevelDescription
            FROM round_profile_criteria rpc
            JOIN user_profiles up
                ON rpc.ProfileUID = up.ProfileUID
            WHERE rpc.RoundID = %s
        """, (round_id,))

        for row in cur.fetchall():
            cat_id = row["CategoryID"]
            uid = row["ProfileUID"]
            category_name = row.get("CategoryName")
            level_description = row.get("LevelDescription") or uid

            ensure_category(cat_id, category_name)

            if row["Operator"] == "INCLUDE":
                result[cat_id]["include"][uid] = level_description

            elif row["Operator"] == "EXCLUDE":
                result[cat_id]["exclude"][uid] = level_description

        # -------------------------
        # OVERRIDES
        # -------------------------
        cur.execute("""
            SELECT
                spo.ProfileUID,
                spo.Operator,
                spo.Weight,
                up.CategoryID,
                up.CategoryName,
                up.LevelDescription
            FROM selection_profile_overrides spo
            JOIN user_profiles up
                ON spo.ProfileUID = up.ProfileUID
            WHERE spo.SessionID = %s
        """, (session_id,))

        for row in cur.fetchall():
            cat_id = row["CategoryID"]
            uid = row["ProfileUID"]
            op = row["Operator"].upper()
            weight = row["Weight"]
            category_name = row.get("CategoryName")
            level_description = row.get("LevelDescription") or uid

            ensure_category(cat_id, category_name)

            if op == "INCLUDE":
                result[cat_id]["include"][uid] = level_description
                result[cat_id]["exclude"].pop(uid, None)

            elif op == "EXCLUDE":
                result[cat_id]["exclude"][uid] = level_description
                result[cat_id]["include"].pop(uid, None)

            elif op == "BOOST":
                result[cat_id]["boost"][uid] = {
                    "label": level_description,
                    "weight": weight or 1.2,
                }

            elif op == "DEPRIORITIZE":
                result[cat_id]["deprioritize"][uid] = {
                    "label": level_description,
                    "weight": weight or 0.8,
                }

        return result

    finally:
        conn.close()