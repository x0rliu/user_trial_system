# app/services/registration.py

from dataclasses import dataclass
import bcrypt

from app.db.user_pool import user_exists_by_email, insert_user_pool
from app.db.user_blacklist import is_blacklisted_email_or_domain
from app.db.user_pool import user_exists_by_email
from app.cache.registration_cache import create_registration_entry



@dataclass
class RegistrationInput:
    email: str
    password: str


@dataclass
class RegistrationResult:
    success: bool
    message: str
    token: str | None = None


def register_user(input: RegistrationInput) -> RegistrationResult:
    email = input.email.strip().lower()
    password = input.password

    # --- basic validation ---
    if "@" not in email:
        return RegistrationResult(False, "Invalid email address.")

    if len(password) < 12:
        return RegistrationResult(False, "Password must be at least 12 characters.")

    # --- blacklist check ---
    if is_blacklisted_email_or_domain(email):
        return RegistrationResult(False, "Email or domain is not allowed.")

    # --- duplicate check ---
    if user_exists_by_email(email):
        return RegistrationResult(False, "Email already registered.")

    # --- internal user detection ---
    domain = email.split("@")[-1]
    internal_user = 1 if domain == "logitech.com" else 0

    # --- password hash ---
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    # --- cache pending registration ---
    token = create_registration_entry({
        "email": email,
        "password_hash": password_hash,
        "internal_user": internal_user,
    })


    return RegistrationResult(
        success=True,
        message="Registration successful. Please verify your email.",
        token=token,
    )

