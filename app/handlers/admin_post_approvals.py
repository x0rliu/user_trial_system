# app/handlers/admin_post_approvals.py

from app.db.user_roles import get_effective_permission_level
from app.db.approval_actions import insert_approval_action
from app.db.user_roles import get_users_with_permission_levels
from app.db.project_rounds import close_project_round_as_declined
from app.services.notifications import notify_user
from app.db.project_rounds import set_project_round_status


def handle_admin_approval_post(*, user_id: str, data: dict):
    """
    Authoritative approval POST handler.
    Enforces required data per action.
    """

    # --------------------------------------------------
    # Permission gate
    # --------------------------------------------------
    permission_level = get_effective_permission_level(user_id)
    if permission_level not in (70, 100):
        return {"redirect": "/dashboard"}

    # --------------------------------------------------
    # Required base fields
    # --------------------------------------------------
    approval_type = data.get("approval_type")
    approval_id_raw = data.get("approval_id")
    action = data.get("action")

    if not approval_type or not approval_id_raw or not action:
        return {
            "error": "Missing required approval fields",
            "status": 400,
        }

    try:
        approval_id = int(approval_id_raw)
    except ValueError:
        return {
            "error": "Invalid approval ID",
            "status": 400,
        }

    # --------------------------------------------------
    # Action-specific validation
    # --------------------------------------------------
    assigned_ut_lead = data.get("assigned_ut_lead")
    detail_text = data.get("detail_text", "").strip()
    reason_category = data.get("reason_category") or "clarification"

    if action == "approve":

        # 🔒 Only Admin can approve
        if permission_level != 100:
            return {
                "error": "Only Admin can approve",
                "status": 403,
            }

        # Product trial requires UT lead assignment
        if approval_type == "product_trial":
            if not assigned_ut_lead:
                return {
                    "error": "UT Lead assignment is required to approve",
                    "status": 400,
                }

            valid_ut_leads = {
                u["user_id"]
                for u in get_users_with_permission_levels([70, 100])
            }

            if assigned_ut_lead not in valid_ut_leads:
                return {
                    "error": "Assigned UT Lead must have permission level 70 or 100",
                    "status": 400,
                }

    elif action in ("decline", "info_requested", "request_change"):
        if not detail_text:
            return {
                "error": "Reason is required for this action",
                "status": 400,
            }

    elif action == "withdraw":
        from app.db.project_rounds import withdraw_project_round

        withdraw_project_round(
            round_id=approval_id,
            by_user_id=user_id,
        )

        insert_approval_action(
            approval_type="product_trial",
            approval_id=approval_id,
            action_type="withdraw_request",
            reason_category=reason_category,
            reason_text=data.get("reason_text"),
            assigned_ut_lead_id=None,
            action_by_user_id=user_id,
        )

        return {"redirect": "/product/trials"}

    else:
        return {
            "error": f"Invalid action: {action}",
            "status": 400,
        }

    # --------------------------------------------------
    # Normalize action
    # --------------------------------------------------
    ACTION_MAP = {
        "approve": "approve",
        "decline": "decline",
        "info_requested": "request_info",
        "request_change": "request_changes",
    }

    normalized_action = ACTION_MAP.get(action)

    if not normalized_action:
        return {"error": f"Invalid action: {action}", "status": 400}

    # --------------------------------------------------
    # Persist approval action (audit trail)
    # --------------------------------------------------
    insert_approval_action(
        approval_type=approval_type,
        approval_id=approval_id,
        action_type=normalized_action,
        reason_category=reason_category,
        reason_text=detail_text or None,
        assigned_ut_lead_id=assigned_ut_lead,
        action_by_user_id=user_id,
    )

    # --------------------------------------------------
    # APPLY CONSEQUENCES
    # --------------------------------------------------

    # ============================
    # PRODUCT TRIAL APPROVAL
    # ============================
    if action == "approve" and approval_type == "product_trial":

        set_project_round_status(
            round_id=approval_id,
            status="approved",
            ut_lead_id=assigned_ut_lead,
        )

        notify_user(
            user_id=data.get("requested_by"),
            type_key="product_trial_approved",
            context={
                "round_id": approval_id,
                "ut_lead_id": assigned_ut_lead,
            },
            created_by=user_id,
        )

        notify_user(
            user_id=assigned_ut_lead,
            type_key="product_trial_assigned",
            context={
                "round_id": approval_id,
            },
            created_by=user_id,
        )

    # ============================
    # BONUS SURVEY APPROVAL
    # ============================
    elif action == "approve" and approval_type == "bonus_survey":

        from app.db.surveys import (
            set_bonus_survey_status_by_tracker,
            get_bonus_survey_by_id,
        )
        from app.db.bonus_survey_tracker import (
            get_bonus_survey_id_by_tracker,
        )

        # 1️⃣ Activate survey
        set_bonus_survey_status_by_tracker(
            tracker_id=approval_id,
            new_status="active",
        )

        # 2️⃣ Resolve survey owner
        bonus_survey_id = get_bonus_survey_id_by_tracker(approval_id)
        survey = get_bonus_survey_by_id(bonus_survey_id)

        # 3️⃣ Notify BSC
        if survey:
            notify_user(
                user_id=survey["created_by_user_id"],
                type_key="bonus_survey_approved",
                context={
                    "bonus_survey_id": bonus_survey_id,
                    "survey_title": survey["survey_title"],
                },
                created_by=user_id,
            )

    # ============================
    # PRODUCT TRIAL DECLINE
    # ============================
    elif action == "decline" and approval_type == "product_trial":

        set_project_round_status(
            round_id=approval_id,
            status="declined",
        )

        notify_user(
            user_id=data.get("requested_by"),
            type_key="product_trial_declined",
            context={
                "reason": detail_text,
            },
            created_by=user_id,
        )

    # ============================
    # PRODUCT TRIAL INFO REQUESTED
    # ============================
    elif action == "info_requested" and approval_type == "product_trial":

        set_project_round_status(
            round_id=approval_id,
            status="info_requested",
        )

        notify_user(
            user_id=data.get("requested_by"),
            type_key="product_trial_info_requested",
            context={
                "reason": detail_text,
            },
            created_by=user_id,
        )

    # ============================
    # PRODUCT TRIAL CHANGE REQUESTED
    # ============================
    elif action == "request_change" and approval_type == "product_trial":

        set_project_round_status(
            round_id=approval_id,
            status="change_requested",
        )

        notify_user(
            user_id=data.get("requested_by"),
            type_key="product_trial_change_requested",
            context={
                "reason": detail_text,
            },
            created_by=user_id,
        )

    # --------------------------------------------------
    # Redirect
    # --------------------------------------------------
    return {"redirect": "/admin/approvals"}
