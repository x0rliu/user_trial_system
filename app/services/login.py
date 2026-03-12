from dataclasses import dataclass
import bcrypt
from app.db.user_pool import update_last_login
from app.db.user_pool import get_user_by_email
from app.services.onboarding_state import get_onboarding_state


@dataclass
class LoginInput:
    email: str
    password: str


@dataclass
class LoginResult:
    success: bool
    message: str
    user: dict | None = None
    onboarding_state: str | None = None


def login_user(input: LoginInput) -> LoginResult:
    email = input.email.strip().lower()
    password = input.password

    user = get_user_by_email(email)

    if not user:
        return LoginResult(
            success=False,
            message="Invalid email or password."
        )

    stored_hash = user.get("PasswordHash")

    if not stored_hash:
        return LoginResult(
            success=False,
            message="Account exists but password is not set."
        )

    if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        return LoginResult(
            success=False,
            message="Invalid email or password."
        )

    # ✅ LOGIN IS CONFIRMED AT THIS POINT
    # Record last login timestamp
    update_last_login(user["user_id"])

    # Resolve onboarding state AFTER login is recorded
    onboarding_state = get_onboarding_state(user)

    return LoginResult(
        success=True,
        message="Login successful.",
        user=user,
        onboarding_state=onboarding_state
    )

