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