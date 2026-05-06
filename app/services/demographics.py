from dataclasses import dataclass

from app.db.user_pool import get_user_by_userid, update_user_demographics
from app.services.onboarding_state import get_onboarding_state


@dataclass
class DemographicsInput:
    user_id: str
    first_name: str
    last_name: str
    phone_number: str
    gender: str
    birth_year: str
    country: str
    city: str


@dataclass
class DemographicsResult:
    success: bool
    message: str
    next_state: str | None = None


def save_demographics(input: DemographicsInput) -> DemographicsResult:
    """
    Legacy service wrapper for demographics saves.

    Demographic identity fields live on user_pool and must be written through
    app.db.user_pool.update_user_demographics(). This wrapper exists only for
    older call sites that still construct DemographicsInput.

    phone_number is intentionally not written because user_pool.PhoneNumber is
    deprecated. Account mobile now uses MobileCountryCode, MobileNational,
    and MobileE164 through onboarding/settings handlers.
    """

    try:
        birth_year = int(input.birth_year)
    except (TypeError, ValueError):
        return DemographicsResult(False, "Invalid birth year.")

    update_user_demographics(
        user_id=input.user_id,
        first_name=(input.first_name or "").strip(),
        last_name=(input.last_name or "").strip(),
        gender=(input.gender or "").strip(),
        birth_year=birth_year,
        country=(input.country or "").strip(),
        city=(input.city or "").strip() or None,
        mobile_country_code=None,
        mobile_national=None,
        mobile_e164=None,
    )

    user = get_user_by_userid(input.user_id)
    if not user:
        return DemographicsResult(False, "User not found after update.")

    return DemographicsResult(
        True,
        "Saved.",
        next_state=get_onboarding_state(user),
    )