# User Trials Portal (POC)

## Overview

This project is a proof-of-concept for a centralized User Trials portal at Logitech.

The goal of the system is to provide a single, consistent entry point for:
- Discovering User Trials
- Understanding how trials work
- Checking participation status
- Reducing reliance on email-based communication
- Increasing transparency while preserving confidentiality

Historically, User Trials have been communicated through distributed email threads across multiple teams. This portal demonstrates how a role-based, database-driven system can reduce friction for participants while giving internal teams a clearer, more scalable operational model.

This repository currently implements:
- A **Guest / Unknown user experience**
- Static informational pages rendered dynamically from the database
- A Logitech-aligned visual layout intended to persist across all user roles

This is an early-stage architectural foundation, not a finished product.

---

## Tech Stack

- Python 3
- Built-in Python HTTP server (no external framework yet)
- HTML templates
- CSS (Logitech-inspired styling)
- MySQL (AWS RDS – internal network access required)

---

## Project Structure

ut_site/
│
├── app/
│   ├── main.py                    # Entry point / custom HTTP server & router
│
│   ├── handlers/                  # Request handlers (routing targets)
│   │   ├── auth.py                # Login / logout / auth gates
│   │   ├── onboarding.py          # Email verify, demographics, NDA
│   │   ├── dashboard.py           # User dashboard
│   │   ├── surveys.py             # Bonus surveys (take / approve / admin)
│   │   ├── product_team.py        # Product Team request-trial flows
│   │   └── admin.py               # Admin / UT Lead views
│
│   ├── db/                        # Database access layer (source of truth)
│   │   ├── users.py
│   │   ├── content_pages.py
│   │   ├── surveys.py
│   │   ├── bonus_survey_participation.py
│   │   └── projects.py
│
│   ├── services/                  # Business logic (role-agnostic)
│   │   ├── onboarding_service.py
│   │   ├── demographics_service.py
│   │   └── project_service.py
│
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── demographics.html
│   │   ├── nda.html
│   │   ├── surveys/
│   │   │   ├── bonus_layout.html
│   │   │   ├── bonus_take.html
│   │   │   └── bonus_approval.html
│   │   └── product_team/
│   │       ├── base_product_team.html
│   │       └── request_trial.html
│
│   ├── static/
│   │   ├── styles.css
│   │   ├── surveys.css
│   │   ├── product_team.css
│   │   ├── settings.css
│   │   ├── settings.js
│   │   └── bonus_rail.js
│
│   └── images/
│       └── logitech_logo.png
│
├── sql/
│   └── dump-user_trial_system_v1.sql   # Schema + seed reference
│
├── README.md
└── run_server.bat                      # Local dev launcher

## Running the Site Locally

### Prerequisites

- Python 3 installed
- Network access to the User Trials database (VPN required)
- Database credentials configured in the environment or code as appropriate

### Start the Server

From the project root:

```bash
python -m app.main

### Todo List
- Trials (Primary ROI)
    - Define minimal Trial object (id, name, status, dates, capacity, requirements)
    - Implement Trials navigation menu
    - Active Trials
    - Past Trials
    - Currently Recruiting
    - Upcoming Trials
    -  Create dummy trial data (realistic analog trials)
    -  Render trial lists per status
    -  Define user ↔ trial relationship states
        - invited
        - accepted
        - declined
        - completed
    -  Stub trial detail view (no matching logic yet)
- Legal (Template-Based, No Workflow Yet)
    - Add Legal navigation menu
    - Create Global NDA template page (view / edit)
    - Create Project NDA template page (view / edit)
    - Include placeholders (e.g. $REALNAME, $PROJECT_NAME)
        - Create Privacy Policy page (view / edit)
        - Enforce Legal role permissions
        - Explicitly document: Legal has no user-level data access
        - Note dependency: NDA signing authority TBD (Ironclad)


Rule (authoritative)

Settings POST for interests is destructive and explicit per product type.

Meaning:
    Settings does NOT infer
        No auto-select
        No “assume all if none checked”
        No wizard logic
        What the user saves is exactly what we persist
    Each product type is independent
        Keyboard settings affect only keyboards
        Mouse settings affect only mice
        No cross-contamination
Empty selection is meaningful
    If user unchecks all mouse interests:
        They are explicitly opting out of mouse trials
        Mouse Product Type remains present historically, but:
            They will not qualify
            They will not be invited
            They will not be inferred back in
DB action
    For the affected scope:
        DELETE FROM user_interest_map WHERE user_id = ? AND InterestUID IN (scope)
        INSERT only checked InterestUIDs


Plan (step-by-step, actions + why + order)

Change /profile GET gating to use wizard completion (not data completeness)

Action: In main.py GET /profile handler:

If wizard not completed → redirect to /profile/interests

Else render summary always.

Why: /profile becomes stable and reachable; no forcing users through wizard once they’ve opted out.

Add “Save & Exit Wizard” to each wizard step (POST)

Action: For each wizard step POST handler (/profile/interests, /profile/basic, /profile/advanced):

Parse form like you already do for “save”

If action == exit:

write selections

set_profile_wizard_completed(uid, True)

redirect to /profile

If action == continue:

write selections

redirect to next wizard step

Why: This implements the user’s intent explicitly and permanently.

Keep “Save & Continue” flow as-is, but mark completed at the end

Action: On the final step “continue” (likely advanced):

after save → set ProfileWizardCompleted=True → redirect /profile

Why: Wizard completion should happen on either explicit exit or reaching the end.

Add “Re-run Profile Wizard” in Settings

Action: Add a settings endpoint (POST is fine): /settings/profile_wizard/reset

set_profile_wizard_completed(uid, False)

redirect to /profile/interests

Why: Lets users re-enter the wizard without deleting partial data; wizard naturally pre-fills from DB.

Demote “profile completeness” to display-only

Action: Adjust get_profile_state() / “complete” logic so it’s used only for:

labeling (“Basic/Advanced coverage”)

progress indicators

trial matching confidence

not routing.

Why: Prevent future loops by ensuring routing never depends on “all categories selected” style logic.