def _get_all_eligible_users():
    import mysql.connector
    from app.config.config import DB_CONFIG

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT user_id
            FROM user_pool
            WHERE ParticipantStatus = 'active'
              AND EmailVerified = 1
              AND GlobalNDA_Status = 'Signed'
              AND GuidelinesCompletedAt IS NOT NULL
              AND WelcomeSeenAt IS NOT NULL
              AND Status = 0
        """)

        rows = cur.fetchall()

        users = []

        for r in rows:
            user = {
                "user_id": r["user_id"],

                # -------------------------
                # DEFAULT SCORING FIELDS
                # -------------------------
                "missed_deadlines": 0,
                "reminders_needed": 0,
                "low_quality_flags": 0,
                "applications_count": 0,
                "completed_trials": 0,
                "bonus_points": 0,
                "last_trial_date": None,
                "in_cooldown": False
            }

            # =========================
            # TEST INJECTION (CONTROLLED)
            # =========================
            if user["user_id"] == rows[0]["user_id"]:
                user["completed_trials"] = 5  # high score

            elif len(rows) > 1 and user["user_id"] == rows[1]["user_id"]:
                user["missed_deadlines"] = 3  # low score

            elif len(rows) > 2 and user["user_id"] == rows[2]["user_id"]:
                user["in_cooldown"] = True  # cooldown penalty
            # =========================

            users.append(user)

        return users

    finally:
        conn.close()