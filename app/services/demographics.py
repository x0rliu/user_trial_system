from dataclasses import dataclass
from app.db.user_profiles import update_basic_demographics
from app.db.user_pool import get_user_by_userid
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
    update_basic_demographics(
        user_id=input.user_id,
        first_name=input.first_name,
        last_name=input.last_name,
        phone_number=input.phone_number,
        gender=input.gender,
        birth_year=input.birth_year,
        country=input.country,
        city=input.city,
    )

    user = get_user_by_userid(input.user_id)
    if not user:
        return DemographicsResult(False, "User not found after update.")

    return DemographicsResult(
        True,
        "Saved.",
        next_state=get_onboarding_state(user)
    )

