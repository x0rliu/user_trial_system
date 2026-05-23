# app/services/sso_service.py

from dataclasses import dataclass
import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request

import jwt
from jwt import PyJWKClient

from app.config.config import OKTA_SSO_CONFIG
from app.db.user_pool import (
    get_user_by_email,
    insert_sso_user_pool,
    mark_email_verified,
    update_last_login,
)
from app.services.onboarding_state import get_onboarding_state


@dataclass
class SsoStartResult:
    success: bool
    message: str
    redirect_url: str | None = None
    state: str | None = None
    nonce: str | None = None
    code_verifier: str | None = None


@dataclass
class SsoCallbackResult:
    success: bool
    message: str
    user: dict | None = None
    onboarding_state: str | None = None


def is_sso_configured() -> bool:
    if not OKTA_SSO_CONFIG.get("enabled"):
        return False

    required = ["issuer", "client_id", "redirect_uri"]
    for key in required:
        value = str(OKTA_SSO_CONFIG.get(key) or "").strip()
        if not value or value.startswith("YOUR_"):
            return False

    return True


def build_sso_login_redirect() -> SsoStartResult:
    if not is_sso_configured():
        return SsoStartResult(
            success=False,
            message="SSO is not configured yet.",
        )

    metadata = _get_oidc_metadata()

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = _build_code_verifier()
    code_challenge = _build_code_challenge(code_verifier)

    params = {
        "client_id": OKTA_SSO_CONFIG["client_id"],
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": OKTA_SSO_CONFIG["redirect_uri"],
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    redirect_url = metadata["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)

    return SsoStartResult(
        success=True,
        message="Redirecting to SSO.",
        redirect_url=redirect_url,
        state=state,
        nonce=nonce,
        code_verifier=code_verifier,
    )


def complete_sso_callback(
    *,
    code: str,
    returned_state: str,
    expected_state: str,
    code_verifier: str,
    expected_nonce: str,
) -> SsoCallbackResult:
    if not is_sso_configured():
        return SsoCallbackResult(
            success=False,
            message="SSO is not configured yet.",
        )

    if not code:
        return SsoCallbackResult(
            success=False,
            message="Missing SSO authorization code.",
        )

    if not returned_state or not expected_state or returned_state != expected_state:
        return SsoCallbackResult(
            success=False,
            message="Invalid SSO state. Please try again.",
        )

    if not code_verifier:
        return SsoCallbackResult(
            success=False,
            message="Missing SSO PKCE verifier. Please try again.",
        )

    token_payload = _exchange_code_for_tokens(
        code=code,
        code_verifier=code_verifier,
    )

    id_token = token_payload.get("id_token")

    if not id_token:
        return SsoCallbackResult(
            success=False,
            message="SSO did not return an ID token.",
        )

    claims = _validate_id_token(id_token)

    returned_nonce = str(claims.get("nonce") or "").strip()
    if expected_nonce and returned_nonce != expected_nonce:
        return SsoCallbackResult(
            success=False,
            message="Invalid SSO nonce. Please try again.",
        )

    email = str(claims.get("email") or "").strip().lower()
    if not email:
        return SsoCallbackResult(
            success=False,
            message="SSO did not return an email address.",
        )

    user = get_user_by_email(email)

    if not user:
        first_name, last_name = _extract_name_parts(claims)

        insert_sso_user_pool(
            email=email,
            first_name=first_name,
            last_name=last_name,
            internal_user=1,
            status=0,
            global_nda_status="Not Sent",
        )

        user = get_user_by_email(email)
        if not user:
            return SsoCallbackResult(
                success=False,
                message="SSO sign-in succeeded, but UTS user creation failed.",
            )

    if int(user.get("EmailVerified") or 0) != 1:
        mark_email_verified(user["user_id"])
        user = get_user_by_email(email)
        if not user:
            return SsoCallbackResult(
                success=False,
                message="SSO sign-in succeeded, but UTS user refresh failed.",
            )

    update_last_login(user["user_id"])
    onboarding_state = get_onboarding_state(user)

    return SsoCallbackResult(
        success=True,
        message="SSO login successful.",
        user=user,
        onboarding_state=onboarding_state,
    )


def _exchange_code_for_tokens(*, code: str, code_verifier: str) -> dict:
    metadata = _get_oidc_metadata()

    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": OKTA_SSO_CONFIG["redirect_uri"],
        "client_id": OKTA_SSO_CONFIG["client_id"],
        "code_verifier": code_verifier,
    }).encode("utf-8")

    request = urllib.request.Request(
        metadata["token_endpoint"],
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")

    return json.loads(raw)


def _validate_id_token(id_token: str) -> dict:
    metadata = _get_oidc_metadata()

    jwk_client = PyJWKClient(metadata["jwks_uri"])
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=OKTA_SSO_CONFIG["client_id"],
        issuer=metadata["issuer"],
        options={
            "require": ["exp", "iat", "iss", "aud", "sub"],
        },
    )

    now = int(time.time())
    exp = int(claims.get("exp", 0))
    if exp <= now:
        raise RuntimeError("SSO token has expired.")

    return claims


def _get_oidc_metadata() -> dict:
    issuer = OKTA_SSO_CONFIG["issuer"].rstrip("/")
    metadata_url = issuer + "/.well-known/openid-configuration"

    request = urllib.request.Request(
        metadata_url,
        headers={"Accept": "application/json"},
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")

    metadata = json.loads(raw)

    required = ["issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"]
    for key in required:
        if not metadata.get(key):
            raise RuntimeError(f"Missing OIDC metadata field: {key}")

    return metadata


def _extract_name_parts(claims: dict) -> tuple[str | None, str | None]:
    given_name = str(claims.get("given_name") or "").strip()
    family_name = str(claims.get("family_name") or "").strip()

    if given_name or family_name:
        return given_name or None, family_name or None

    full_name = str(claims.get("name") or "").strip()
    if not full_name:
        return None, None

    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], None

    return " ".join(parts[:-1]), parts[-1]


def _build_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def _build_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")