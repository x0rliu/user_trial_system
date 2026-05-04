### 2026-05-04 — Notification cleanup, routing integrity, and system documentation pass

#### Summary
Cleaned up notification behavior, performed a broad GET/POST routing integrity pass, normalized POST route wrapper naming across the app, and created the first set of system documentation files to make UTS easier to understand, audit, and maintain.

#### Changes Made
- Fixed notification behavior so approval notifications dismiss correctly after being viewed/opened.
- Converted logout from GET mutation to POST-based logout with a GET confirmation page.
- Renamed major POST route wrappers in `app/main.py` to follow the `handle_*_post()` contract.
- Cleaned POST route naming across auth, onboarding, profile, settings, notifications, bonus surveys, product requests, trial flows, UT Lead flows, historical uploads, and product utilities.
- Removed a debug GET route that mutated selection state.
- Changed `POST /settings` into a safe redirect fallback.
- Removed POST HTML fallback rendering from bonus survey upload/analyze/close handlers.
- Converted Contact Us from JSON response behavior to redirect-based PRG behavior.
- Fixed product trial request stakeholder save by adding the missing stakeholders POST handler.
- Fixed product request submit CSRF parsing by keeping POST data shape consistent with the wizard.
- Fixed admin project approval detail view returning `None` by ensuring the GET renderer returns `{"html": content}`.
- Created the root-level `docs/` folder as project documentation, not app runtime documentation.
- Drafted `docs/README.md` as the front door for the documentation set.
- Drafted `docs/route_map.md` to map GET/POST routes, wrappers, behavior, and known routing exceptions.
- Drafted `docs/workflow_map.md` to explain major user journeys and system workflows.
- Drafted `docs/data_map.md` to explain data ownership, source-of-truth rules, and persistence risks.
- Drafted `docs/ai_map.md` to document AI boundaries, AI workflows, evidence guardrails, and future AI risks.
- Established `docs/changelog.md` as a chronological engineering log with newest entries first.

#### Confirmed Working
- Notifications flow.
- Auth/onboarding/profile/settings routing after renames.
- Legal document save and publish after JS binding correction.
- Bonus survey creation, approval, upload, analyze, and structure flows tested during the routing pass.
- Product request wizard, submit, pending review, admin approval detail view, and approval action flow.
- Trial interest, selection, application/onboarding, and UT Lead routing flows where tested.
- Contact Us still works after conversion to redirect behavior.
- Documentation files are located at project root under `docs/`, not inside `app/`.

#### Untested / Needs Follow-up
- Bonus survey upload/analyze/close fallback behavior after removing POST HTML rendering should be retested with dummy data.
- Historical upload / generate section names / generate summaries / generate insights should be tested with safe historical data.
- Create Product should be tested if not already covered.
- The new documentation is a strong first pass but should be reconciled against the exact live DB schema during Priority 5.
- `route_map.md`, `workflow_map.md`, `data_map.md`, and `ai_map.md` should be updated whenever major routes, workflows, tables, or AI behavior change.

#### Known Exceptions / Deferred Cleanup
- Legal document save/publish still use AJAX/JSON behavior intentionally because the legal platform is working and version-auditable.
- Admin permission update and inline settings demographics save still use JSON/AJAX behavior and should be reviewed before any PRG conversion.
- Bonus survey upload/analyze/close fallback behavior was made more routing-compliant but remains untested with dummy data.
- Duplicate render methods remain in `main.py` and should be cleaned later.
- `parse_post_data()` and `_parse_post_data()` both exist and should eventually be consolidated carefully.
- These are accepted technical debt for now, not accidental unknowns.

#### Next Recommended Step
Move to Priority 4: stabilize template escaping and notification copy, while keeping the new documentation updated as changes are made.