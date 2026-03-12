"""
Application-level role capability mapping.

IMPORTANT:
- Database (user_role.PermissionLevel) is the source of truth for role identity
- This file defines how the application interprets those roles
- Do NOT define roles here
- Do NOT read from the database here
"""

# Base capability sets
BASE_PARTICIPANT_CAPABILITIES = {
    "profile:view",
    "profile:edit",
    "trial:apply",
    "trial:accept",
    "trial:withdraw",
    "survey:complete",
}

# By Roles

ROLE_CAPABILITIES = {
    # Guest (0)
    0: {
        "public:view",
    },

    # Participant (20)
    20: BASE_PARTICIPANT_CAPABILITIES,

    # Legal (30)
    30: BASE_PARTICIPANT_CAPABILITIES | {
        "legal_template:view",
        "legal_template:edit",
        "nda_status:view",
        "nda_document:request_access",
    },


    # Bonus Creator (40)
    40: BASE_PARTICIPANT_CAPABILITIES | {
        "bonus:create",
        "bonus:edit",
        "bonus:correct",
        "bonus:request_publish",
        "bonus:review",
        "data:view_raw",
        "data:export_csv",
    },


    # Product Team (50)
    50: BASE_PARTICIPANT_CAPABILITIES | {
        "trial_management:request",
        "profile_definition:approve",
        "survey:approve",
        "cohort:approve",
        "logistics:submit_tracking",
        "data:view_raw",
        "data:export_csv",
        "report:view",
    },


    # Management (60)
    60: BASE_PARTICIPANT_CAPABILITIES | {
        "dashboard:view",
        "metrics:view_company",
        "metrics:view_business_group",
        "metrics:view_sub_group",
        "metrics:view_category",
        "metrics:view_product_type",
        "metrics:view_project",
        "report:view",
    },

    # UT Lead (70)
    70: BASE_PARTICIPANT_CAPABILITIES | {
        # Trial lifecycle
        "trial_management:view",
        "trial_management:create",
        "trial_management:edit",
        "trial_management:manage",

        # Product collaboration
        "trial_intake:view",
        "trial_intake:clarify",

        # Profile & recruiting
        "profile_definition:create",
        "profile_definition:edit",
        "recruitment:run",
        "recruitment:view",

        # Participant management
        "participant:view",
        "participant:communicate",
        "participant:onboard",

        # NDA & compliance
        "nda_status:view",
        "nda:request_signature",
        "nda:send_reminder",

        # Logistics
        "logistics:view",
        "logistics:distribute_tracking",

        # Surveys
        "survey:create",
        "survey:edit",
        "survey:issue",
        "survey:monitor",
        "survey:send_reminder",

        # Data & analysis
        "data:view_raw",
        "analysis:perform",
        "analysis:bucket",
        "analysis:annotate",

        # Reporting
        "report:generate",
        "report:view",
    },


    # IT Admin (80)
    80: {
        "db:read",
        "db:write",
        "db:migrate",
        "db:backup",
        "db:restore",

        "system:access_logs",
        "system:config_read",
        "system:config_write",

        "infrastructure:monitor",
        "infrastructure:maintain",
    },


    # God / Site Admin (100)
    100: {
        "*",
    },
}


def get_capabilities_for_permission_level(permission_level: int) -> set[str]:
    """
    Returns the capability set for a given PermissionLevel.
    Unknown levels return an empty set (fail closed).
    """
    return ROLE_CAPABILITIES.get(permission_level, set()).copy()
