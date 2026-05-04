# UTS Route Map

This document maps the primary HTTP routes in the User Trial System.

Purpose:
- Make routing behavior explainable.
- Preserve GET/POST separation.
- Help future debugging.
- Reduce “magic app” risk by documenting what each route does.

Routing rules:
- GET routes render only.
- GET routes call `_render_*` functions.
- GET routes must not mutate database state.
- POST routes mutate state or trigger actions only.
- POST routes call `handle_*_post()` functions.
- POST routes should end in redirects unless explicitly documented as a deferred AJAX/JSON exception.

Known deferred exceptions:
- `POST /legal/documents/save`
- `POST /legal/documents/publish`
- `POST /admin/users/update-permission`
- `POST /settings/demographics/save`

These are working AJAX/JSON flows and are intentionally deferred until the related frontend behavior is redesigned.

---

# GET Routes

## Public / Auth / Onboarding

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/` | `_render_home()` | Redirects user to role/onboarding landing path | Render-safe redirect |
| GET | `/register` | `_render_register()` | Renders registration page | Public |
| GET | `/verify-email` | `_render_verify_email()` | Renders email verification result | Public-ish |
| GET | `/login` | `_render_login()` | Renders login page | Public |
| GET | `/logout` | `_render_logout()` | Renders logout confirmation page | Logout mutation is POST-only |
| GET | `/demographics` | `_render_demographics()` | Renders onboarding demographics | Auth required |
| GET | `/nda` | `_render_nda()` | Renders global NDA onboarding step | Auth required |
| GET | `/participation-guidelines` | `_render_participation_guidelines()` | Renders guidelines onboarding step | Auth required |
| GET | `/welcome` | `_render_welcome()` | Renders welcome/activation page | Auth required |

---

## Profile / Settings

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/profile/wizard` | `_render_profile_wizard()` | Renders profile wizard entry | Auth required |
| GET | `/profile/interests` | `_render_profile_interests()` | Renders interests profile step | Auth required |
| GET | `/profile/basic` | `_render_profile_basic()` | Renders basic profile step | Auth required |
| GET | `/profile/advanced` | `_render_profile_advanced()` | Renders advanced profile step | Auth required |
| GET | `/profile` | `_render_profile_summary()` | Renders profile summary | Auth required |
| GET | `/settings` | `_render_settings_page()` | Renders settings page | Auth required |
| GET | `/settings/demographics` | `_render_settings_demographics_fragment()` | Renders demographics settings fragment | Fragment response |
| GET | `/settings/interests` | `_render_settings_interests_fragment()` | Renders interests settings fragment | Fragment response |
| GET | `/settings/basic` | `_render_settings_basic_fragment()` | Renders basic settings fragment | Fragment response |
| GET | `/settings/advanced` | `_render_settings_advanced_fragment()` | Renders advanced settings fragment | Fragment response |

---

## General User Pages

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/dashboard` | `_render_dashboard()` | Renders dashboard | Auth required |
| GET | `/my_trials` | `_render_my_trials()` | Renders user trial list | Auth required |
| GET | `/history` | `_render_history()` | Renders history page | Auth required |
| GET | `/badges` | `_render_badges()` | Renders badges page | Auth required |

---

## Trial Participant Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/trials/active` | `_render_trials_active()` | Renders active trials | Auth required |
| GET | `/trials/past` | `_render_trials_past()` | Renders past trials | Auth required |
| GET | `/trials/upcoming` | `_render_trials_upcoming()` | Renders upcoming trials | Auth required |
| GET | `/trials/recruiting` | `_render_trials_recruiting()` | Renders recruiting trials | Auth required |
| GET | `/trials/interest` | `_render_trials_interest()` | Redirects to upcoming trials | GET does not record interest |
| GET | `/trials/nda` | `_render_trial_nda()` | Renders per-trial NDA | Auth required |
| GET | `/trials/responsibilities` | `_render_responsibilities()` | Renders trial responsibilities page | Auth required |

---

## Legal Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/legal/nda` | `_render_legal_nda()` | Renders public/gated NDA document | Auth required |
| GET | `/legal/download/<document_id>` | `_render_legal_download(path)` | Downloads legal document PDF | Auth required |
| GET | `/legal/signed/<slug>` | `_render_signed_legal_document(path)` | Renders signed legal document | Auth required |
| GET | `/legal/documents` | `_render_legal_documents_index()` | Renders legal document editor index | Auth required |
| GET | `/legal/documents/<doc_id>` | `_render_legal_documents_index(doc_id)` | Renders selected legal document editor | Auth required |
| GET | `/legal/<slug>` | `_render_legal_document_view(path)` | Renders public legal document | Public/gated depending on document |

---

## Bonus Survey Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/surveys/bonus` | `_render_bonus_surveys()` | Renders bonus survey dashboard | Auth required |
| GET | `/surveys/bonus/create` | `_render_bonus_survey_create()` | Renders bonus survey creation shell | Auth required |
| GET | `/surveys/bonus/create/template` | `_render_bonus_survey_template()` | Renders bonus survey template step | Auth required |
| GET | `/surveys/bonus/create/targeting` | `_render_bonus_survey_targeting()` | Renders bonus survey targeting step | Auth required |
| GET | `/surveys/bonus/create/review` | `_render_bonus_survey_review()` | Renders bonus survey review step | Auth required |
| GET | `/surveys/bonus/submitted` | `_render_bonus_survey_submitted()` | Renders submitted confirmation/status | Auth required |
| GET | `/surveys/bonus/pending` | `_render_bonus_survey_pending_view()` | Renders pending approval view | Auth required |
| GET | `/surveys/bonus/upload` | `_render_bonus_survey_upload()` | Renders bonus survey upload page | Auth required |
| GET | `/surveys/bonus/structure` | `_render_bonus_survey_structure()` | Renders bonus survey structure editor | Auth required |
| GET | `/surveys/bonus/active` | `_render_bonus_survey_active()` | Renders active bonus survey report/view | Auth required |
| GET | `/surveys/bonus/take` | `_render_bonus_survey_take()` | Renders available bonus surveys for participant | Auth required |
| GET | `/surveys/bonus/take/open` | `_render_bonus_survey_take_open()` | Renders safe fallback page | Actual opening is POST-only |

---

## Standard Survey Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/surveys/ut` | `_render_ut_surveys()` | Renders UT surveys placeholder/page | Auth required |
| GET | `/surveys/recruitment` | `_render_recruitment_surveys()` | Renders recruitment surveys placeholder/page | Auth required |
| GET | `/survey/upload...` | `_render_survey_upload()` | Renders survey upload page | Auth required |

---

## Admin Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/admin/users` | `_render_admin_users()` | Renders user administration page | Admin/UT permission gate |
| GET | `/admin/approvals` | `_render_admin_approvals()` | Renders approval dashboard | Admin/UT permission gate |
| GET | `/admin/approvals/view` | `_render_admin_approval_view()` | Renders bonus survey approval detail | Admin/UT permission gate |
| GET | `/admin/approvals/project` | `_render_admin_approval_project()` | Renders product trial approval detail | Admin/UT permission gate |

---

## Notifications

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/notifications` | `_render_notifications()` | Renders notifications page | Auth required |
| GET | `/notifications/view` | `_render_notification_view()` | Renders single notification detail | Auth required |
| GET | `/notifications/dismiss` | inline redirect | Redirects to `/notifications` | GET does not dismiss |
| GET | `/notifications/mark-read` | inline redirect | Redirects to `/notifications` | GET does not mark read |
| GET | `/notifications/open` | inline redirect | Redirects to `/notifications` | GET does not open/dismiss |

---

## Product Team Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/product/request-trial` | `_render_product_request_trial()` | Renders Product Team request trial entry | Product permission |
| GET | `/product/request-trial/wizard/basics` | `_render_product_request_trial_wizard_basics()` | Renders basics wizard step | Product permission |
| GET | `/product/request-trial/wizard/timing` | `_render_product_request_trial_wizard_timing()` | Renders timing wizard step | Product permission |
| GET | `/product/request-trial/wizard/stakeholders` | `_render_product_request_trial_wizard_stakeholders()` | Renders stakeholders wizard step | Product permission |
| GET | `/product/request-trial/wizard/review` | `_render_product_request_trial_wizard_review()` | Renders review/submit wizard step | Product permission |
| GET | `/product/request-trial/pending` | `_render_product_request_trial_pending()` | Renders pending approval status | Product permission |
| GET | `/product/request-trial/info-requested` | `_render_product_request_trial_info_requested()` | Renders info requested response page | Product permission |
| GET | `/product/request-trial/change-requested` | `_render_product_request_trial_change_requested()` | Renders change requested response page | Product permission |
| GET | `/product/current-trials` | `_render_product_current_trials()` | Renders current trials list/detail | Product permission |
| GET | `/product/past-trials` | `_render_product_past_trials()` | Renders past trials placeholder/page | Product permission |
| GET | `/product/comparisons` | `_render_product_comparisons()` | Renders comparisons placeholder/page | Product permission |
| GET | `/product/reports` | `_render_product_reports()` | Renders reports placeholder/page | Product permission |

---

## UT Lead Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/ut-lead/trials` | `_render_ut_lead_trials()` | Renders UT Lead trials overview | UT Lead/Admin |
| GET | `/ut-lead/project` | `_render_ut_lead_project()` | Renders UT Lead project detail/configuration | UT Lead/Admin |
| GET | `/api/profile-levels` | `_render_api_profile_levels()` | Returns JSON profile-level data | Read-only API GET |
| GET | `/trials/selection` | `_render_user_selection()` | Renders user selection page | UT Lead/Admin |
| GET | `/trials/selection/confirm` | `_render_user_selection_confirm()` | Renders/redirects selection confirmation flow | UT Lead/Admin |
| GET | `/trials/selection/confirm/post-bridge` | `_render_selection_confirm_post_bridge()` | Renders POST bridge confirmation form | Render-only bridge |

---

## Historical Trial Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/historical` | `_render_historical_landing()` | Renders historical trials landing page | Auth required |
| GET | `/historical/upload` | `_render_historical_upload()` | Renders historical upload form | Auth required |
| GET | `/historical/create-context` | `_render_historical_create_context()` | Renders create historical context form | Auth required |
| GET | `/historical/context` | `_render_historical_context()` | Renders historical context detail | Auth required |
| GET | `/historical/raw` | `_render_historical_raw()` | Renders reconstructed raw data view | Auth required |

---

## Product Utility Routes

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | `/products/create` | `_render_create_product()` | Renders product creation page | Auth required |

---

## Guest Content Fallback

| Method | Path | Main wrapper | Behavior | Notes |
|---|---|---|---|---|
| GET | any unmatched path | `_render_guest_content(path)` | Renders content page by slug or 404 | Used for public content pages |

---

# POST Routes

## Auth / Onboarding / Profile / Settings

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/register` | `handle_register_post()` | Creates registration / user record | Redirect or render error |
| POST | `/verify-email` | `handle_verify_email_post()` | Verifies email and creates session | Redirect |
| POST | `/demographics` | `handle_demographics_post()` | Saves onboarding demographics | Redirect |
| POST | `/login` | `handle_login_post()` | Authenticates user and creates session | Redirect or render login error |
| POST | `/logout` | `handle_logout_post()` | Deletes session and clears cookie | Redirect |
| POST | `/nda` | `handle_nda_post()` | Saves global NDA acceptance | Redirect |
| POST | `/participation-guidelines` | `handle_guidelines_post()` | Saves guidelines acknowledgement | Redirect |
| POST | `/profile/interests` | `handle_profile_interests_post()` | Saves interest profile data | Redirect |
| POST | `/profile/basic` | `handle_profile_basic_post()` | Saves basic profile data | Redirect |
| POST | `/profile/advanced` | `handle_profile_advanced_post()` | Saves advanced profile data | Redirect |
| POST | `/welcome` | `handle_welcome_post()` | Marks welcome/onboarding complete | Redirect |
| POST | `/settings` | `handle_settings_page_post()` | Safe fallback only | Redirect |
| POST | `/settings/password/change` | `handle_settings_password_change_post()` | Changes password | Redirect |
| POST | `/settings/demographics/save` | `handle_settings_demographics_save_post()` | Saves settings demographics inline | JSON — deferred exception |

---

## Admin / Support / Legal

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/admin/users/update-permission` | `handle_update_user_permission_post()` | Updates user permission level | JSON — deferred exception |
| POST | `/contact-us` | `handle_contact_us_post()` | Saves/sends contact message | Redirect |
| POST | `/legal/documents/save` | `handle_legal_document_save_post()` | Saves legal document draft | JSON — deferred exception |
| POST | `/legal/documents/publish` | `handle_legal_document_publish_post()` | Publishes legal document version | JSON — deferred exception |

---

## Bonus Survey Creation / Approval / Upload / Analysis

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/surveys/bonus/create/save-basics` | `handle_bonus_survey_basics_save_post()` | Saves bonus survey basics | Redirect |
| POST | `/surveys/bonus/create/new` | `handle_bonus_survey_create_new_post()` | Creates new bonus survey draft | Redirect |
| POST | `/surveys/bonus/create/save-template` | `handle_bonus_survey_template_save_post()` | Saves bonus survey template metadata | Redirect |
| POST | `/surveys/bonus/create/save-targeting` | `handle_bonus_survey_targeting_save_post()` | Saves bonus survey targeting | Redirect |
| POST | `/surveys/bonus/take/open` | `handle_bonus_survey_take_open_post()` | Opens/records participant bonus survey access | Redirect |
| POST | `/surveys/bonus/approve` | `handle_bonus_survey_approve_post()` | Approves bonus survey | Redirect |
| POST | `/surveys/bonus/request-changes` | `handle_bonus_survey_request_changes_post()` | Records requested changes | Redirect |
| POST | `/surveys/bonus/request-info` | `handle_bonus_survey_request_info_post()` | Records requested info | Redirect |
| POST | `/surveys/bonus/create/submit` | `handle_bonus_survey_submit_post()` | Submits bonus survey for approval | Redirect |
| POST | `/surveys/bonus/upload...` | `handle_bonus_survey_upload_post()` | Uploads bonus survey CSV/results | Redirect |
| POST | `/surveys/bonus/analyze...` | `handle_bonus_survey_analyze_post()` | Runs/stores bonus survey analysis | Redirect |
| POST | `/surveys/bonus/close...` | `handle_bonus_survey_close_post()` | Closes bonus survey | Redirect |
| POST | `/surveys/bonus/generate-sections` | `handle_bonus_survey_generate_sections_post()` | Generates survey sections | Redirect |

---

## Bonus Survey Structure

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/surveys/bonus/structure/generate` | `handle_bonus_survey_structure_generate_post()` | Generates structure from survey data | Redirect |
| POST | `/surveys/bonus/structure/reset` | `handle_bonus_survey_structure_reset_post()` | Resets generated structure | Redirect |
| POST | `/surveys/bonus/structure/classify-profile` | `handle_bonus_survey_structure_classify_profile_post()` | Classifies profile questions | Redirect |
| POST | `/surveys/bonus/structure/save` | `handle_bonus_survey_structure_save_post()` | Saves structure edits | Redirect |
| POST | `/surveys/bonus/section/add` | `handle_bonus_survey_section_add_post()` | Adds bonus survey section | Redirect |
| POST | `/surveys/bonus/section/rename` | `handle_bonus_survey_section_rename_post()` | Renames bonus survey section | Redirect |
| POST | `/surveys/bonus/section/delete` | `handle_bonus_survey_section_delete_post()` | Deletes bonus survey section | Redirect |

---

## Product Team Request Trial / Approvals

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/product/request-trial/create` | `handle_request_trial_create_post()` | Creates product trial request draft | Redirect |
| POST | `/product/request-trial/wizard/basics` | `handle_product_request_trial_wizard_basics_post()` | Saves wizard basics | Redirect |
| POST | `/product/request-trial/wizard/timing` | `handle_product_request_trial_wizard_timing_post()` | Saves wizard timing/scope | Redirect |
| POST | `/product/request-trial/wizard/stakeholders` | `handle_product_request_trial_wizard_stakeholders_post()` | Saves wizard stakeholders | Redirect |
| POST | `/product/request-trial/submit` | `handle_product_request_trial_submit_post()` | Converts draft request into DB-backed pending trial | Redirect |
| POST | `/admin/approvals/submit` | `handle_admin_approval_post()` | Handles approval actions | Redirect |
| POST | `/admin/approvals/bonus/submit` | `handle_admin_approval_post()` | Handles bonus approval actions | Redirect |
| POST | `/product/request-trial/info-requested/respond` | `handle_product_request_trial_info_requested_respond_post()` | Product responds to info request | Redirect |
| POST | `/product/request-trial/change-requested/respond` | `handle_product_request_trial_change_requested_respond_post()` | Product responds to requested change | Redirect |
| POST | `/admin/approval` | `handle_admin_approval_post()` | Handles approval action alias | Redirect |

---

## UT Lead / Survey Upload

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/ut-lead/project` | `handle_ut_lead_project_post()` | Saves UT Lead project/round configuration | Redirect |
| POST | `/trials/selection` | `handle_user_selection_post()` | Applies user selection changes | Redirect |
| POST | `/survey/upload...` | `handle_survey_upload_post()` | Uploads survey links/configuration/results | Redirect |

---

## Trial Application / Participant Onboarding

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/trials/apply` | `handle_trial_apply_post()` | Applies user to recruiting trial | Redirect |
| POST | `/trials/withdraw` | `handle_trial_withdraw_post()` | Withdraws application | Redirect |
| POST | `/trials/end-recruiting` | `handle_end_recruiting_post()` | Ends recruiting for round | Redirect |
| POST | `/trials/nda` | `handle_trial_nda_post()` | Saves per-trial NDA acceptance | Redirect |
| POST | `/trials/confirm-shipping` | `handle_confirm_shipping_post()` | Confirms shipping address | Redirect |
| POST | `/trials/responsibilities` | `handle_responsibilities_post()` | Saves responsibility acknowledgement/decline | Redirect |
| POST | `/trials/save-shipping` | `handle_save_shipping_post()` | Saves participant shipping details | Redirect |

---

## Notifications

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/notifications/open` | `handle_notification_open_post()` | Dismisses notification and redirects to target | Redirect |
| POST | `/notifications/view` | `handle_notification_view_post()` | Marks notification read and redirects to view | Redirect |
| POST | `/notifications/dismiss` | `handle_notification_dismiss_post()` | Dismisses notification | Redirect |
| POST | `/notifications/mark-read` | `handle_notifications_mark_read_post()` | Marks all notifications read | Redirect |

---

## Trial Interest / Selection Session

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/trials/interest` | `handle_trials_interest_post()` | Records interest in upcoming trial | Redirect |
| POST | `/trials/selection/init` | `handle_selection_init_post()` | Creates/loads selection session | Redirect |
| POST | `/trials/selection/confirm` | `handle_selection_confirm_post()` | Confirms selection session status | Redirect |

---

## Historical Trials / Product Utilities

| Method | Path | Main wrapper | Behavior | Response |
|---|---|---|---|---|
| POST | `/historical/upload` | `handle_historical_upload_post()` | Uploads historical dataset | Redirect |
| POST | `/historical/create-context` | `handle_historical_create_context_post()` | Creates historical trial context | Redirect |
| POST | `/products/create` | `handle_create_product_post()` | Creates product record | Redirect |
| POST | `/historical/generate-section-names` | `handle_generate_section_names_post()` | Generates historical section names | Redirect |
| POST | `/historical/generate-section-summaries` | `handle_generate_section_summaries_post()` | Generates historical section summaries | Redirect |
| POST | `/historical/generate-insights` | `handle_generate_insights_post()` | Generates historical insights | Redirect |

---

# Deferred Cleanup

## AJAX / JSON POST Endpoints

These currently break the strict “POST must redirect” rule, but are intentionally deferred because they are working frontend-bound flows.

| Path | Reason deferred | Risk |
|---|---|---|
| `/legal/documents/save` | Legal editor depends on AJAX save behavior | Medium/high — legal versioning must not be broken |
| `/legal/documents/publish` | Legal editor depends on AJAX publish behavior | Medium/high — legal publication history must remain auditable |
| `/admin/users/update-permission` | Likely inline admin control | Medium |
| `/settings/demographics/save` | Inline settings save behavior | Low/medium |

Future cleanup should inspect the frontend JS before converting these to PRG.

---

## POST Handlers Requiring Retest

These were changed to avoid POST HTML rendering but need dummy/safe data retesting.

| Path | Reason |
|---|---|
| `/surveys/bonus/upload...` | POST HTML fallback removed |
| `/surveys/bonus/analyze...` | POST HTML fallback removed |
| `/surveys/bonus/close...` | POST HTML fallback removed |

---

## Duplicate / Cleanup Candidates

These are not immediate routing blockers but should be cleaned later.

| Area | Note |
|---|---|
| `_render_ut_lead_trials()` | Appears duplicated in `main.py` |
| `_render_ut_lead_project()` | Appears duplicated in `main.py` |
| `_render_product_current_trials()` | Appears duplicated in `main.py` |
| `/historical/raw` GET branch | Appears duplicated in route table |
| `_handle_legal_save_draft()` | Stale legacy method; not currently routed |
| `parse_post_data()` and `_parse_post_data()` | Two parsing helpers exist; should eventually consolidate carefully |