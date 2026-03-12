# app/services/profile_state.py

from __future__ import annotations

from typing import Set

import mysql.connector

from app.config.config import DB_CONFIG
from app.config.profile_layout import (
    INTEREST_PROFILE_SECTIONS,
    BASIC_PROFILE_SECTIONS,
    ADVANCED_PROFILE_SECTIONS,
)

# -------------------------
# Low-level helpers
# -------------------------

def _get_selected_interest_category_ids(user_id: str) -> Set[int]:
    """
    Returns the set of Interest CategoryIDs the user has at least one selection in.
    """
    query = """
        SELECT DISTINCT ui.CategoryID
        FROM user_interest_map uim
        JOIN user_interests ui ON ui.InterestUID = uim.InterestUID
        WHERE uim.user_id = %s
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(query, (user_id,))
        return {int(row[0]) for row in cur.fetchall()}
    finally:
        conn.close()


def _get_selected_product_type_codes(user_id: str) -> Set[str]:
    """
    Product Types live in Interest CategoryID = 102.
    We use InterestCode to know which conditional sections apply (PT102a, PT102b, etc.).
    """
    query = """
        SELECT DISTINCT ui.InterestCode
        FROM user_interest_map uim
        JOIN user_interests ui ON ui.InterestUID = uim.InterestUID
        WHERE uim.user_id = %s
          AND ui.CategoryID = 102
          AND ui.InterestCode IS NOT NULL
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(query, (user_id,))
        return {row[0] for row in cur.fetchall() if row[0]}
    finally:
        conn.close()


def _get_selected_profile_category_ids(user_id: str) -> Set[int]:
    """
    Returns the set of Profile CategoryIDs the user has at least one selection in.
    """
    query = """
        SELECT DISTINCT up.CategoryID
        FROM user_profile_map upm
        JOIN user_profiles up ON up.ProfileUID = upm.ProfileUID
        WHERE upm.user_id = %s
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(query, (user_id,))
        return {int(row[0]) for row in cur.fetchall()}
    finally:
        conn.close()


# -------------------------
# Completion checks
# -------------------------

def interests_complete(user_id: str) -> bool:
    """
    Interests are considered complete once the user has acknowledged the step
    by clicking Continue (even if they selected nothing).
    """
    query = """
        SELECT InterestsWizardCompleted
        FROM user_pool
        WHERE user_id = %s
        LIMIT 1
    """

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(query, (user_id,))
        row = cur.fetchone()
        return bool(row and int(row[0]) == 1)
    finally:
        conn.close()



def basic_profile_complete(user_id: str) -> bool:
    selected_category_ids = _get_selected_profile_category_ids(user_id)

    required_category_ids: Set[int] = set()
    for section in BASIC_PROFILE_SECTIONS:
        for cat_id in section.get("categories", []):
            required_category_ids.add(int(cat_id))

    return required_category_ids.issubset(selected_category_ids)


def advanced_profile_complete(user_id: str) -> bool:
    selected_category_ids = _get_selected_profile_category_ids(user_id)

    required_category_ids: Set[int] = set()
    for section in ADVANCED_PROFILE_SECTIONS:
        for cat_id in section.get("categories", []):
            required_category_ids.add(int(cat_id))

    return required_category_ids.issubset(selected_category_ids)


# -------------------------
# Authoritative resolver
# -------------------------

def get_profile_state(user_id: str) -> str:
    from app.db.user_pool import get_profile_wizard_step

    step = get_profile_wizard_step(user_id)

    if step < 1:
        return "interests"
    if step < 2:
        return "basic_profile"
    if step < 3:
        return "advanced_profile"
    return "complete"
