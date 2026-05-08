### 2026-05-08 — Priority 6 CSRF hardening checkpoint

> **Summary**  
> Continued Priority 6 security hardening with a major CSRF remediation pass across the highest-risk UTS mutation flows. The pass expanded CSRF protection from the early baseline to most core administrative, Product Team, Bonus Survey, UT Lead, Legal, Historical, participant trial, and notification actions. The current refreshed `app.zip` confirms work through Patch 20, with notification CSRF protection present and compile checks passing.
>
> **Changes Made**
> - Added a multi-token one-time CSRF foundation so users can safely have multiple active forms/tabs without immediately invalidating other page actions.
> - Added CSRF validation to major Bonus Survey flows, including draft wizard saves, create-new action, upload, active analyze/close actions, and structure management tools.
> - Added CSRF validation to Admin approval actions, Admin user permission updates, Product Team create/wizard/response flows, Legal document save/publish actions, Historical upload and AI generation actions, UT Lead project editor actions, UT Lead selection flow, participant recruiting/application/NDA actions, active trial shipping/responsibilities actions, and notification actions.
> - Added or reinforced permission gates on several privileged routes, including Product Team create actions, Historical pages/actions, Legal document editor actions, UT Lead project actions, and Admin permission update actions.
> - Converted several invalid-CSRF behaviors from raw/scary `400` errors into clean redirects or JSON `403` responses depending on whether the endpoint is form-based or fetch/JSON-based.
> - Confirmed the refreshed `app.zip` after each completed pass before continuing to the next patch.
>
> **Confirmed Working**
> - Current refreshed `app.zip` contains Patch 20 notification CSRF changes.
> - Compile check passed for the Patch 20 touched files: `app/main.py`, `app/handlers/notifications.py`, and `app/utils/csrf.py`.
> - CSRF route scan now shows `50 / 68` POST wrappers covered, up from the early baseline of roughly `6 / 68`.
> - Major high-risk mutation areas are now covered: Admin approvals, Admin permission changes, Bonus Survey flows, Product Team flows, Legal editor actions, Historical upload/generation, UT Lead project/selection flows, participant recruiting/NDA/shipping/responsibilities actions, and notification actions.
>
> **Design Decisions**
> - Keep CSRF validation explicit and boring in `main.py` whenever possible, matching the UTS rule that `main.py` acts as the traffic cop for auth/input/mutation/redirect behavior.
> - Use redirects for normal form POST CSRF failures so users are sent back to the relevant page with `error=invalid_csrf`.
> - Use JSON `401/403` responses for JSON/fetch routes so frontend code does not accidentally receive an HTML redirect where JSON is expected.
> - Continue the checkpoint cadence: after each pass, commit locally, refresh/upload `app.zip`, confirm the refreshed zip contains the expected changes, then continue automatically if checks pass.
> - Add future security rules to `uts_rules.md` so new POST routes require auth, permission, ownership, CSRF, input validation, mutation-after-validation, and redirect/JSON response behavior by default.
>
> **Untested / Needs Follow-up**
> - Browser smoke testing is still needed for every patched flow, especially multi-form pages such as UT Lead project details, Bonus Survey structure, notification dropdown actions, Product Team wizard actions, and active trial shipping/responsibilities.
> - Remaining CSRF coverage is incomplete: `18 / 68` POST routes are still uncovered.
> - Remaining uncovered routes include account/auth special cases, onboarding/profile/settings forms, and survey leftovers: `/register`, `/verify-email`, `/demographics`, `/login`, `/logout`, `/nda`, `/participation-guidelines`, `/profile/interests`, `/profile/basic`, `/profile/advanced`, `/welcome`, `/settings`, `/settings/password/change`, `/settings/demographics/save`, `/contact-us`, `/surveys/bonus/take/open`, `/surveys/bonus/generate-sections`, and `/survey/upload`.
> - Need to decide how to handle unauthenticated/semi-public CSRF cases such as login, register, contact-us, and email verification.
> - Priority 6 still requires IDOR/ownership validation audit, permission gate audit, file upload hardening, error/debug cleanup, secrets/config review, SQL safety final pass, and IT-review packaging.
>
> **Known Exceptions / Deferred Cleanup**
> - CSRF protection is not yet global across every POST route.
> - Some remaining routes may be legacy or duplicate paths and need inspection before patching.
> - Some patched flows have compile confirmation and refreshed-zip confirmation, but not full UI smoke-test confirmation.
> - The broader security rule set has not yet been added to `uts_rules.md`; it was discussed as a needed follow-up.
> - Priority 6 is still in progress; current work only completes a large portion of 6C, not the full security hardening priority.
>
> **Next Recommended Step**  
> Resume with Patch 21: CSRF-protect onboarding, profile, and settings forms. First file to inspect: `app/handlers/onboarding.py`.

### 2026-05-06 — Priority 5 closeout and Bonus Survey report rendering alignment

> **Summary**  
> Completed the Priority 5 schema/code alignment pass far enough for MVP, then began aligning Bonus Survey results rendering with the stronger Historical report format. The session moved Bonus Survey reporting from technically correct but rough output toward a structured report flow with summary, profile, segment insights, section results, and saved AI section analysis.
>
> **Changes Made**
> - Completed the Bonus Survey pipeline schema audit.
> - Fixed Bonus Survey answer deduplication so joined/profile-expanded rows dedupe by `AnswerID`.
> - Enforced `QuestionHash + QuestionOrder` as the Bonus Survey question identity contract.
> - Fixed saved report detection so the active page reads persisted report JSON from `report`, not stale `analysis`.
> - Added section metadata to generated Bonus Survey reports: `section_key`, `section_name`, `display_name`, `section_order`, and `section_contract`.
> - Added structure snapshots and `structure_fingerprint` to generated Bonus Survey reports.
> - Added stale-report detection when current section structure differs from the saved report structure.
> - Removed duplicate quote rendering and numeric-answer-as-quote behavior.
> - Removed leftover debug/dead render code from the Bonus Survey active results page.
> - Fixed Product Team approval action enum drift by removing invalid `reason_category="clarification"` writes and replacing invalid `withdrawn_by_requestor` approval actions with DB-valid `withdraw_request`.
> - Fixed project round lifecycle alignment by adding `change_requested → withdrawn` and `recruiting → closed`.
> - Completed a broad active-MVP schema drift audit.
> - Added historical-style numeric result cards with mini bars.
> - Added section result cards with section title and section average.
> - Added saved AI section analysis inside each section card, including key findings, qualitative insights, and supporting quotes.
> - Added saved Segment Insights rendering from report JSON.
> - Added a top-level Report Summary card.
> - Fixed Report Summary response count display to use authoritative DB/payload count instead of AI-generated count.
> - Normalized saved `report_json.summary.response_count` before persistence.
> - Reworked Survey User Profile rendering with a shared renderer for `data_uploaded` and `analysis_ready`.
> - Updated Survey User Profile multi-select handling so answers are split and counted individually.
> - Removed standalone raw “Representative quotes” cards from Section Results.
> - Began report title hierarchy cleanup.
> - Updated `uts_rules.md` so changelog/progress-summary format is now part of the canonical UTS rules.
>
> **Confirmed Working**
> - Full app Python compile passed during the Priority 5 closeout audit.
> - Individual `py_compile` checks passed for changed files during each implementation slice.
> - Bonus Survey report regeneration updates the existing report row instead of creating duplicate rows.
> - Stale-report warning behavior was confirmed: no warning when saved/current structure fingerprints match, warning appears after a controlled section display-name change, and warning disappears after reverting the change.
> - Bonus Survey section display names render instead of raw section keys.
> - Duplicate quote blocks are gone.
> - Numeric answers no longer appear as quotes.
> - Survey 29 response count mismatch was confirmed by SQL: DB/payload count was `21`, while the old saved AI report count was `23`.
> - Report Summary now displays `21`.
> - Saved report JSON now persists `summary.response_count = 21` after regeneration.
> - Survey User Profile renders correctly after the shared renderer change.
> - Multi-select profile answers are split and counted individually.
> - Report Summary, Survey User Profile, Segment Insights, Section Results, and Section Analysis all render on the Bonus Survey active page.
>
> **Design Decisions**
> - Priority 6 security hardening should wait until Bonus Survey results rendering is closer to the Historical report structure.
> - Bonus Survey reporting should reuse the stronger Historical report pattern instead of remaining a rough separate output path.
> - Rendering alignment should proceed in layers: first get correct report elements onto the page, then organize hierarchy, then apply visual theme/polish, then replace quote-first output with stronger summaries/SWOT/insights.
> - Response count is DB/payload-owned, not AI-owned.
> - AI can provide `key_patterns`, section findings, qualitative insights, supporting quotes, and segment insights, but factual counts must be normalized by the app.
> - Raw quote cards should not dominate the report; quotes should support analysis rather than act as the main report content.
> - Segment Insights should be improved using the existing saved report shape before adding new tables or metadata.
> - `uts_rules.md` is now the canonical rule source for UTS work and changelog formatting.
>
> **Untested / Needs Follow-up**
> - Segment Insights presentation needs a dedicated cleanup pass.
> - Full visual polish/theme alignment is not complete.
> - Button and nav colors remain inconsistent.
> - Fonts still need normalization across the Bonus Survey results page.
> - Spacing between labels, headings, and content still needs tightening.
> - Quantitative cards should be refined so multiple cards sit cleanly on one row when space allows.
> - Supporting quotes need a safer long-term evidence strategy, possibly with generic respondent labels.
> - The latest local edits should be committed and the final `app.zip` refreshed if not already done.
>
> **Known Exceptions / Deferred Cleanup**
> - Segment Insights currently renders correctly but still feels like generic text boxes.
> - Section Analysis is not yet SWOT-oriented.
> - Some styling remains inline during this transitional rendering pass.
> - The Bonus Survey results page may later need CSS/template extraction once structure stabilizes.
> - Quote attribution is deferred until a safe generic respondent-labeling model is defined.
> - Priority 6 security hardening has not started.
>
> **Next Recommended Step**  
> Continue with `5D-10b — Improve Segment Insights card presentation`, then proceed to font/spacing normalization, quantitative card row layout, and button/nav color consistency before starting Priority 6 security hardening.

### 2026-05-04 — Priority 4 notification, template, and Settings cleanup

> **Summary**  
> Continued Priority 4 by stabilizing notification copy/rendering, tightening the template renderer contract, converting the Settings demographics fragment to the current `__KEY__` anchor standard, and cleaning up the Personal Details experience in Settings.
>
> **Changes Made**
> - Added a plain-text notification rendering boundary so accidental HTML tags in notification titles/messages are stripped before display.
> - Normalized notification copy generators for bonus survey and product trial notifications.
> - Added missing notification renderers for approved, assigned, info-provided, change-accepted, change-countered, withdrawn, and recruiting-started notification types.
> - Cleaned notification DB hygiene:
>   - Removed debug prints from notification dismissal.
>   - Removed duplicate `mark_notification_read()` definition.
>   - Moved repeated imports to the top of `app/db/notifications.py`.
> - Updated `app/utils/templates.py` so template values preserve meaningful falsey values like `0` and `False` instead of converting them to blank strings.
> - Confirmed the renderer continues supporting both legacy `{{ key }}` tokens and current `__KEY__` anchors.
> - Converted `app/templates/settings/edit_demographics.html` away from mixed `{{ }}` and `__KEY__` anchors.
> - Added/confirmed the Settings Personal Details flow as the canonical editable location for account demographics.
> - Clarified the ownership model:
>   - Onboarding demographics = first-time required capture.
>   - Settings demographics = editable source.
>   - Profile demographics = read-only display.
> - Added Personal Details to the Settings Account section.
> - Removed the visible “Loading personal details…” placeholder by rendering the demographics form server-side inside the Settings page.
> - Kept Personal Details collapsed by default.
> - Began visual cleanup for the Personal Details form:
>   - Reduced nested-panel feel.
>   - Planned lighter save button styling.
>   - Planned full-country dropdown display while preserving country code storage.
>   - Planned mobile number alignment cleanup.
>
> **Confirmed Working**
> - Notification dropdown/page no longer displays raw HTML tags.
> - Notification read/dismiss behavior still works.
> - Notification debug logs no longer print during dismissal.
> - Settings page still renders after template renderer cleanup.
> - Personal Details section now appears in Settings.
> - Personal Details can remain collapsed by default.
> - Legal document save/publish behavior remained intact after earlier JS binding correction.
>
> **Design Decisions**
> - Email remains non-editable because it is the primary account identity and link to `user_id`.
> - First name, last name, country, birth year, and gender are required eligibility/account fields.
> - Gender remains required because “Prefer not to say” and “Non-binary” are valid intentional responses and can be treated as wildcard/backfill categories for selection balancing.
> - Missing birth year should exclude users from trials because adult eligibility cannot be confirmed.
> - Missing country should exclude users from trials because region eligibility cannot be confirmed.
> - City and mobile number are optional in Settings because they are not required until selection/logistics.
> - Shipping information should not be merged into Personal Details. It belongs in a separate future Shipping & Delivery section or trial-specific logistics flow.
>
> **Untested / Needs Follow-up**
> - Final Personal Details visual cleanup should be confirmed after the next run:
>   - Country displays full country name.
>   - Country still saves country code.
>   - Mobile row aligns cleanly.
>   - Save button visual weight is reduced.
> - Settings demographics save validation should be revisited to enforce the finalized required/optional rules:
>   - Required: first name, last name, country, birth year, gender.
>   - Optional: city, mobile number.
> - Profile page should eventually display demographics read-only and link back to Settings for edits.
> - Documentation maps should be updated to reflect Settings as the canonical post-onboarding demographics editor.
>
> **Known Exceptions / Deferred Cleanup**
> - Settings demographics save remains an intentional AJAX/JSON exception for now.
> - Legal document save/publish remains AJAX/JSON because the legal editor is working and version-auditable.
> - The broader template migration is still gradual: only actively modified templates should be converted to `__KEY__` anchors.
> - Shipping & Delivery should be designed later as its own section, not added to Personal Details during this pass.
>
> **Next Recommended Step**  
> Finish Priority 4 by confirming the remaining Personal Details visual cleanup, then move to Priority 5: align the live DB schema with current app code.

### 2026-05-04 — Notification cleanup, routing integrity, and system documentation pass

> **Summary**  
> Cleaned up notification behavior, performed a broad GET/POST routing integrity pass, normalized POST route wrapper naming across the app, and created the first set of system documentation files to make UTS easier to understand, audit, and maintain.
>
> **Changes Made**
> - Fixed notification behavior so approval notifications dismiss correctly after being viewed/opened.
> - Converted logout from GET mutation to POST-based logout with a GET confirmation page.
> - Renamed major POST route wrappers in `app/main.py` to follow the `handle_*_post()` contract.
> - Cleaned POST route naming across auth, onboarding, profile, settings, notifications, bonus surveys, product requests, trial flows, UT Lead flows, historical uploads, and product utilities.
> - Removed a debug GET route that mutated selection state.
> - Changed `POST /settings` into a safe redirect fallback.
> - Removed POST HTML fallback rendering from bonus survey upload/analyze/close handlers.
> - Converted Contact Us from JSON response behavior to redirect-based PRG behavior.
> - Fixed product trial request stakeholder save by adding the missing stakeholders POST handler.
> - Fixed product request submit CSRF parsing by keeping POST data shape consistent with the wizard.
> - Fixed admin project approval detail view returning `None` by ensuring the GET renderer returns `{"html": content}`.
> - Created the root-level `docs/` folder as project documentation, not app runtime documentation.
> - Drafted `docs/README.md` as the front door for the documentation set.
> - Drafted `docs/route_map.md` to map GET/POST routes, wrappers, behavior, and known routing exceptions.
> - Drafted `docs/workflow_map.md` to explain major user journeys and system workflows.
> - Drafted `docs/data_map.md` to explain data ownership, source-of-truth rules, and persistence risks.
> - Drafted `docs/ai_map.md` to document AI boundaries, AI workflows, evidence guardrails, and future AI risks.
> - Established `docs/changelog.md` as a chronological engineering log with newest entries first.
>
> **Confirmed Working**
> - Notifications flow.
> - Auth/onboarding/profile/settings routing after renames.
> - Legal document save and publish after JS binding correction.
> - Bonus survey creation, approval, upload, analyze, and structure flows tested during the routing pass.
> - Product request wizard, submit, pending review, admin approval detail view, and approval action flow.
> - Trial interest, selection, application/onboarding, and UT Lead routing flows where tested.
> - Contact Us still works after conversion to redirect behavior.
> - Documentation files are located at project root under `docs/`, not inside `app/`.
>
> **Untested / Needs Follow-up**
> - Bonus survey upload/analyze/close fallback behavior after removing POST HTML rendering should be retested with dummy data.
> - Historical upload / generate section names / generate summaries / generate insights should be tested with safe historical data.
> - Create Product should be tested if not already covered.
> - The new documentation is a strong first pass but should be reconciled against the exact live DB schema during Priority 5.
> - `route_map.md`, `workflow_map.md`, `data_map.md`, and `ai_map.md` should be updated whenever major routes, workflows, tables, or AI behavior change.
>
> **Known Exceptions / Deferred Cleanup**
> - Legal document save/publish still use AJAX/JSON behavior intentionally because the legal platform is working and version-auditable.
> - Admin permission update and inline settings demographics save still use JSON/AJAX behavior and should be reviewed before any PRG conversion.
> - Bonus survey upload/analyze/close fallback behavior was made more routing-compliant but remains untested with dummy data.
> - Duplicate render methods remain in `main.py` and should be cleaned later.
> - `parse_post_data()` and `_parse_post_data()` both exist and should eventually be consolidated carefully.
> - These are accepted technical debt for now, not accidental unknowns.
>
> **Next Recommended Step**  
> Move to Priority 4: stabilize template escaping and notification copy, while keeping the new documentation updated as changes are made.