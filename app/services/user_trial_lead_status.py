from datetime import date, timedelta


def derive_lifecycle_status(row: dict) -> str:
    """
    Derives UT Lead lifecycle status from project_rounds row.

    Stored Status = decision state
    Derived status = lifecycle state
    """

    today = date.today()

    raw_status = row.get("Status")

    # 1. Hard stops
    if raw_status in ("declined", "withdrawn"):
        return "Withdrawn"

    end_date = row.get("EndDate")
    start_date = row.get("StartDate")
    ship_date = row.get("ShipDate")

    # Normalize MySQL zero dates
    def valid(d):
        return d not in (None, "", "0000-00-00")

    # 2. Completed
    if valid(end_date) and end_date < today:
        return "Completed"

    # 3. Ongoing
    if valid(start_date) and start_date <= today:
        return "Ongoing"

    # 4. Under Planning (≤ 6 weeks to ship)
    if valid(ship_date) and ship_date <= today + timedelta(days=42):
        return "Under Planning"

    # 5. Upcoming (date known, but far out)
    if valid(ship_date):
        return "Upcoming"

    # 6. Fallback
    return "Draft / Unscheduled"
