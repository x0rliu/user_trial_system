# services/selection_profile_service.py

import mysql.connector
from app.config.config import DB_CONFIG


def get_effective_profile_criteria(*, session_id: int, round_id: int):
    """
    Merge baseline + overrides into structured profile criteria
    """

    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        cur = conn.cursor(dictionary=True)

        result = {}

        # -------------------------
        # BASELINE
        # -------------------------
        cur.execute("""
            SELECT rpc.ProfileUID, rpc.Operator, up.CategoryID
            FROM round_profile_criteria rpc
            JOIN user_profiles up
                ON rpc.ProfileUID = up.ProfileUID
            WHERE rpc.RoundID = %s
        """, (round_id,))

        for row in cur.fetchall():
            cat = row["CategoryID"]

            if cat not in result:
                result[cat] = {
                    "include": set(),
                    "exclude": set(),
                    "boost": {},
                    "deprioritize": {}
                }

            if row["Operator"] == "INCLUDE":
                result[cat]["include"].add(row["ProfileUID"])

            elif row["Operator"] == "EXCLUDE":
                result[cat]["exclude"].add(row["ProfileUID"])

        # -------------------------
        # OVERRIDES
        # -------------------------
        cur.execute("""
            SELECT spo.ProfileUID, spo.Operator, spo.Weight, up.CategoryID
            FROM selection_profile_overrides spo
            JOIN user_profiles up
                ON spo.ProfileUID = up.ProfileUID
            WHERE spo.SessionID = %s
        """, (session_id,))

        for row in cur.fetchall():
            cat = row["CategoryID"]

            if cat not in result:
                result[cat] = {
                    "include": set(),
                    "exclude": set(),
                    "boost": {},
                    "deprioritize": {}
                }

            uid = row["ProfileUID"]
            op = row["Operator"].upper()

            if op == "INCLUDE":
                result[cat]["include"].add(uid)
                result[cat]["exclude"].discard(uid)

            elif op == "EXCLUDE":
                result[cat]["exclude"].add(uid)
                result[cat]["include"].discard(uid)

            elif op == "BOOST":
                result[cat]["boost"][uid] = row["Weight"] or 1.2

            elif op == "DEPRIORITIZE":
                result[cat]["deprioritize"][uid] = row["Weight"] or 0.8

        return result

    finally:
        conn.close()