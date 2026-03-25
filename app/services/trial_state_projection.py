def get_pt_trial_bucket(round_row):
    status = (round_row.get("Status") or "").lower()

    if status in ("closed", "completed"):
        return "past"

    if status in ("approved", "recruiting", "running"):
        return "current"

    return "requesting"