# app/services/user_context.py

from typing import Dict

from app.services.onboarding_state import get_onboarding_state
from app.services.profile_state import get_profile_state


# -------------------------------------------------
# Onboarding configuration (authoritative)
# -------------------------------------------------

ONBOARDING_LANDING_PATHS = {
    "email_verification": "/verify-email",
    "demographics": "/demographics",
    "nda": "/nda",
    "welcome": "/welcome",
    "ready": "/dashboard",
    "unknown": "/login",
}

ONBOARDING_PAGES = {
    "email_verification": "/verify-email",
    "demographics": "/demographics",
    "nda": "/nda",
    "welcome": "/welcome",
}

# -------------------------------------------------
# Profile configuration (authoritative)
# -------------------------------------------------

PROFILE_WIZARD_ENTRY_PATHS = {
    "interests": "profile/interests",
    "basic_profile": "profile/basic",
    "advanced_profile": "profile/advanced",
    "complete": "profile",
    "unavailable": None,
}

PROFILE_WIZARD_PATHS = {
    "profile/wizard",
    "profile/interests",
    "profile/basic",
    "profile/advanced",
}

# -------------------------------------------------
# Public API
# -------------------------------------------------

def build_user_context(user: Dict) -> Dict:
    """
    Build a read-only snapshot of the user's current state, access rules,
    routing authority, and capabilities.

    No DB writes.
    No redirects.
    No side effects.

    Profile completion is derived from ProfileWizardStep through
    get_profile_state(user_id). Do not use a shadow ProfileWizardCompleted
    flag; that column is not part of the current user_pool schema.
    """

    # -------------------------
    # Anonymous / invalid user
    # -------------------------
    if not user:
        return {
            "states": {
                "onboarding": "unknown",
                "profile": "unknown",
                "trial": "unknown",
            },
            "routing": {
                "landing_path": "/login",
                "profile_wizard_entry": None,
            },
            "access": {
                "is_path_allowed": lambda path: path in ("/login", "/register"),
                "deny_redirect": lambda path: "/login",
            },
            "capabilities": {},
        }

    # -------------------------
    # Resolve authoritative states
    # -------------------------
    onboarding_state = get_onboarding_state(user)

    if onboarding_state == "ready":
        profile_state = get_profile_state(user["user_id"])
    else:
        profile_state = "unavailable"

    profile_complete = profile_state == "complete"
    profile_wizard_entry = PROFILE_WIZARD_ENTRY_PATHS.get(profile_state)

    # -------------------------
    # Landing path (onboarding owns this)
    # -------------------------
    landing_path = ONBOARDING_LANDING_PATHS.get(
        onboarding_state,
        "/login",
    )

    # -------------------------
    # Access control logic
    # -------------------------

    def is_path_allowed(path: str) -> bool:
        # Mid-onboarding: ONLY the current onboarding page is allowed.
        if onboarding_state in ONBOARDING_PAGES:
            return path == ONBOARDING_PAGES[onboarding_state]

        # Fully onboarded users may access the app.
        if onboarding_state == "ready":
            # Completed users should not re-enter the profile wizard.
            if profile_complete and path in PROFILE_WIZARD_PATHS:
                return False

            # Wizard still in progress: block onboarding pages,
            # but allow app/profile routes to make forward progress.
            return path not in ONBOARDING_PAGES.values()

        # Unknown state: only login / register allowed.
        return path in ("/login", "/register")

    def deny_redirect(path: str) -> str:
        # Completed users hitting wizard URLs → Settings/edit intent.
        if (
            onboarding_state == "ready"
            and profile_complete
            and path in PROFILE_WIZARD_PATHS
        ):
            return "/settings"

        # Default: send to onboarding landing path.
        return landing_path

    # -------------------------
    # Capabilities (non-routing)
    # -------------------------
    capabilities = {
        "onboarding_complete": onboarding_state == "ready",
        "can_edit_profile": onboarding_state == "ready",
        "profile_complete": profile_complete,
    }

    return {
        "states": {
            "onboarding": onboarding_state,
            "profile": profile_state,
            "trial": "unknown",  # reserved for later
        },
        "routing": {
            "landing_path": landing_path,
            "profile_wizard_entry": profile_wizard_entry,
        },
        "access": {
            "is_path_allowed": is_path_allowed,
            "deny_redirect": deny_redirect,
        },
        "capabilities": capabilities,
    }