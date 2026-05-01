# app/services/password_service.py

from dataclasses import dataclass
import bcrypt

from app.db.user_pool import get_user_by_userid, update_password_hash


@dataclass
class PasswordChangeResult:
    success: bool
    error_code: str | None = None


def change_password(
    *,
    user_id: str,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> PasswordChangeResult:
    """
    Change a user's password.

    No rendering.
    No redirects.
    No session mutation.
    """

    if not user_id:
        return PasswordChangeResult(False, "user_missing")

    if not current_password:
        return PasswordChangeResult(False, "current_password_required")

    if not new_password:
        return PasswordChangeResult(False, "new_password_required")

    if not confirm_password:
        return PasswordChangeResult(False, "confirm_password_required")

    if new_password != confirm_password:
        return PasswordChangeResult(False, "new_password_mismatch")

    if len(new_password) < 12:
        return PasswordChangeResult(False, "new_password_too_short")

    user = get_user_by_userid(user_id)
    if not user:
        return PasswordChangeResult(False, "user_not_found")

    stored_hash = user.get("PasswordHash")
    if not stored_hash:
        return PasswordChangeResult(False, "password_not_set")

    if not bcrypt.checkpw(
        current_password.encode("utf-8"),
        stored_hash.encode("utf-8"),
    ):
        return PasswordChangeResult(False, "current_password_invalid")

    if bcrypt.checkpw(
        new_password.encode("utf-8"),
        stored_hash.encode("utf-8"),
    ):
        return PasswordChangeResult(False, "new_password_same")

    new_password_hash = bcrypt.hashpw(
        new_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    update_password_hash(
        user_id=user_id,
        password_hash=new_password_hash,
    )

    return PasswordChangeResult(True)