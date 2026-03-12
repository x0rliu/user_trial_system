def demographics_complete(user: dict) -> bool:
    required = [
        user.get("FirstName"),
        user.get("LastName"),
        user.get("Gender"),
        user.get("BirthYear"),
        user.get("Country"),
        user.get("City"),
    ]
    return all(v not in (None, "", 0) for v in required)


def nda_signed(user: dict) -> bool:
    return (
        user.get("GlobalNDA_Status") == "Signed"
        and bool(user.get("GlobalNDA_SignedAt"))
    )


def email_verified(user: dict) -> bool:
    return int(user.get("EmailVerified") or 0) == 1


def get_onboarding_state(user: dict) -> str:
    """
    Single authoritative onboarding state resolver.
    Business readiness + one-time welcome interceptor.
    """

    if not user:
        return "unknown"

    # 1️⃣ Email verification
    if not email_verified(user):
        return "email_verification"

    # 2️⃣ Demographics
    if not demographics_complete(user):
        return "demographics"

    # 3️⃣ NDA
    if not nda_signed(user):
        return "nda"

    # 4️⃣ Participation Guidelines
    if not user.get("GuidelinesCompletedAt"):
        return "participation_guidelines"

    # 5️⃣ Welcome (one-time interceptor)
    if not user.get("WelcomeSeenAt"):
        return "welcome"

    # 6️⃣ Fully activated user
    return "ready"
