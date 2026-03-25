from app.db.project_rounds import get_upcoming_project_rounds
from app.db.user_pool_country_codes import get_user_country
from app.db.user_pool import get_all_users


# -------------------------
# CORE RULES
# -------------------------

def _region_matches(user_country: str, region: str) -> bool:
    if not region:
        return True

    region = region.strip().upper()

    if region == "GLOBAL":
        return True

    allowed = [c.strip() for c in region.split(",")]

    return user_country.upper() in allowed


def _user_is_eligible(user: dict) -> bool:
    """
    Mirrors your current logic:
    - active
    - email verified
    """

    return (
        user.get("ParticipantStatus") == "active"
        and user.get("EmailVerified") == 1
    )


# -------------------------
# SINGLE SOURCE OF TRUTH
# -------------------------

def is_user_visible_for_round(user: dict, round_row: dict) -> bool:

    user_id = user.get("user_id")
    round_id = round_row.get("RoundID")

    # eligibility
    if not _user_is_eligible(user):
        print(f"[VISIBILITY][BLOCKED] user={user_id} round={round_id} reason=not_eligible")
        return False

    user_country = (user.get("CountryCode") or "").strip().upper()

    if not user_country:
        print(f"[VISIBILITY][BLOCKED] user={user_id} round={round_id} reason=no_country")
        return False

    region = round_row.get("Region")

    if not _region_matches(user_country, region):
        print(f"[VISIBILITY][BLOCKED] user={user_id} round={round_id} reason=region_mismatch ({user_country} vs {region})")
        return False

    print(f"[VISIBILITY][ALLOWED] user={user_id} round={round_id}")
    return True


# -------------------------
# USER → ROUNDS
# -------------------------

def get_visible_upcoming_rounds(user_id: str):
    rounds = get_upcoming_project_rounds()

    user_country = get_user_country(user_id)

    if not user_country:
        return []

    # minimal user object to reuse logic
    user = {
        "CountryCode": user_country,
        "ParticipantStatus": "active",  # assumed from current flow
        "EmailVerified": 1,             # assumed
    }

    visible = []

    for r in rounds:
        if is_user_visible_for_round(user, r):
            visible.append(r)

    return visible


# -------------------------
# ROUND → USERS (DEBUG)
# -------------------------

def get_visible_users_for_round(round_id: int):
    """
    Debug helper.

    Returns all users who can see a given round
    using the SAME visibility logic as user-facing display.

    This is NOT wired to any route yet.
    """

    rounds = get_upcoming_project_rounds()

    round_row = next((r for r in rounds if r["RoundID"] == round_id), None)

    if not round_row:
        return []

    users = get_all_users()

    visible = []

    for u in users:
        is_visible = is_user_visible_for_round(u, round_row)

        if is_visible:
            print(f"[VISIBLE] {u.get('user_id')} -> Round {round_id}")
            visible.append(u)
        else:
            print(f"[FILTERED] {u.get('user_id')} -> Round {round_id}")

    return visible


from app.db.project_rounds import get_recruiting_project_rounds

def get_visible_recruiting_rounds(user_id: str):

    rounds = get_recruiting_project_rounds()

    user_country = get_user_country(user_id)

    if not user_country:
        return []

    user = {
        "user_id": user_id,
        "CountryCode": user_country,
        "ParticipantStatus": "active",
        "EmailVerified": 1,
    }

    visible = []

    for r in rounds:
        if is_user_visible_for_round(user, r):
            visible.append(r)

    return visible