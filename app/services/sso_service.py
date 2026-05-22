# app/services/sso_service.py

from dataclasses import dataclass
import json
import secrets
import time
import urllib.parse
import urllib.request

import jwt
from jwt import PyJWKClient

from app.config.config import OKTA_SSO_CONFIG
from app.db.user_pool import get_user_by_email, update_last_login
from app.services.onboarding_state import get_onboarding_state


@dataclass
class SsoStartResult:
    success: bool
    message: str
    redirect_url: str | None = None
    state: str | None = None


@dataclass
class SsoCallbackResult:
    success: bool
    message: str
    user: dict | None = None
    onboarding_state: str | None = None


def is_sso_configured() -> bool:
    if not OKTA_SSO_CONFIG.get("enabled"):
        return False

    required = ["issuer", "client_id", "client_secret", "redirect_uri"]
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

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    issuer = OKTA_SSO_CONFIG["issuer"].rstrip("/")
    authorize_url = issuer + "/v1/authorize"

    params = {
        "client_id": OKTA_SSO_CONFIG["client_id"],
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": OKTA_SSO_CONFIG["redirect_uri"],
        "state": state,
        "nonce": nonce,
    }

    redirect_url = authorize_url + "?" + urllib.parse.urlencode(params)

    return SsoStartResult(
        success=True,
        message="Redirecting to SSO.",
        redirect_url=redirect_url,
        state=state,
    )


def complete_sso_callback(*, code: str, returned_state: str, expected_state: str) -> SsoCallbackResult:
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

    token_payload = _exchange_code_for_tokens(code)
    id_token = token_payload.get("id_token")

    if not id_token:
        return SsoCallbackResult(
            success=False,
            message="SSO did not return an ID token.",
        )

    claims = _validate_id_token(id_token)

    email = str(claims.get("email") or "").strip().lower()
    if not email:
        return SsoCallbackResult(
            success=False,
            message="SSO did not return an email address.",
        )

    user = get_user_by_email(email)
    if not user:
        return SsoCallbackResult(
            success=False,
            message="SSO sign-in succeeded, but this email is not registered in UTS yet.",
        )

    update_last_login(user["user_id"])
    onboarding_state = get_onboarding_state(user)

    return SsoCallbackResult(
        success=True,
        message="SSO login successful.",
        user=user,
        onboarding_state=onboarding_state,
    )


def _exchange_code_for_tokens(code: str) -> dict:
    issuer = OKTA_SSO_CONFIG["issuer"].rstrip("/")
    token_url = issuer + "/v1/token"

    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": OKTA_SSO_CONFIG["redirect_uri"],
        "client_id": OKTA_SSO_CONFIG["client_id"],
        "client_secret": OKTA_SSO_CONFIG["client_secret"],
    }).encode("utf-8")

    request = urllib.request.Request(
        token_url,
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
    issuer = OKTA_SSO_CONFIG["issuer"].rstrip("/")
    jwks_url = issuer + "/v1/keys"

    jwk_client = PyJWKClient(jwks_url)
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=OKTA_SSO_CONFIG["client_id"],
        issuer=issuer,
        options={
            "require": ["exp", "iat", "iss", "aud", "sub"],
        },
    )

    now = int(time.time())
    exp = int(claims.get("exp", 0))
    if exp <= now:
        raise RuntimeError("SSO token has expired.")

    return claims