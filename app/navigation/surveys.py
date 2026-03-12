# app/navigation/surveys.py

# Role levels
PARTICIPANT_LEVEL = 20
BSC_LEVEL = 40
UT_LEAD_LEVEL = 70
ADMIN_LEVEL = 100

BONUS_SURVEY_LEVELS = {BSC_LEVEL, UT_LEAD_LEVEL, ADMIN_LEVEL}
UT_SURVEY_LEVELS = {UT_LEAD_LEVEL, ADMIN_LEVEL}
RECRUITMENT_SURVEY_LEVELS = {UT_LEAD_LEVEL, ADMIN_LEVEL}

MANAGE_SURVEY_LEVELS = (
    BONUS_SURVEY_LEVELS
    | UT_SURVEY_LEVELS
    | RECRUITMENT_SURVEY_LEVELS
)

ALL_SURVEY_LEVELS = MANAGE_SURVEY_LEVELS | {PARTICIPANT_LEVEL}


def get_navigation(permission_level: int) -> str:
    if permission_level < PARTICIPANT_LEVEL:
        return ""

    items = []

    # --- Participate ---
    if permission_level >= PARTICIPANT_LEVEL:
        items.append('<a href="/surveys/bonus/take">Take a Bonus Survey</a>')
        items.append('<div class="dropdown-divider"></div>')

    # --- Manage ---
    if permission_level in BONUS_SURVEY_LEVELS:
        items.append('<a href="/surveys/bonus">Bonus Surveys</a>')

    # if permission_level in UT_SURVEY_LEVELS:
    #    items.append('<a href="/surveys/ut">User Trial Surveys</a>')

    # if permission_level in RECRUITMENT_SURVEY_LEVELS:
    #    items.append('<a href="/surveys/recruitment">Recruitment Surveys</a>')

    return f"""
    <div class="dropdown role-menu">
        <a href="#" class="dropdown-trigger role-anchor">
            Bonus Surveys ▾
        </a>

        <div class="dropdown-menu role-dropdown">
            {''.join(items)}
        </div>
    </div>
    """
