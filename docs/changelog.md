### 2026-05-25 — Product Trial survey availability and deadline MVP

> **Summary**  
> Product Trial participant survey availability and deadlines were brought to MVP state. The system now treats Round Configuration / DB-backed UT Lead dates as canonical, keeps Product Team-requested dates separate from actual trial timing, and calculates participant survey deadlines from the correct availability trigger instead of assuming all surveys become available at the same time.
>
> **Changes Made**
> - Added participant survey availability rules for Product Trials:
>   - OOBE / First Impression surveys become available only after the participant confirms device receipt.
>   - If no OOBE / First Impression survey exists, confirming device receipt does not unlock any survey.
>   - Other participant result surveys become available only after explicit UT Lead activation.
>   - Report an Issue remains excluded from deadline logic.
> - Added +2 business-day deadline calculation using the MVP Monday-Friday business-day rule.
> - Added participant checklist deadline display so users can see when available surveys are due.
> - Added UT Lead-side deadline rule visibility in the Survey & Recruiting Setup table.
> - Added activation notification deadline copy so participants are told the survey due date when a non-OOBE survey is activated.
> - Preserved DB-as-source-of-truth behavior by using `ParticipantActivatedAt` for activated survey deadlines and device receipt confirmation time for OOBE / First Impression deadlines.
> - Confirmed the refreshed DB schema includes:
>   - `ParticipantActivatedAt`
>   - `ParticipantActivatedByUserID`
>   - `ParticipantActivationNotificationSentAt`
>
> **Confirmed Working**
> - Refreshed `app.zip` was inspected after CCPR.
> - Refreshed DB dump was inspected after CCPR.
> - Required Product Trial survey activation fields are present in the DB dump.
> - Product Trial deadline/availability files compile successfully with `py_compile`.
> - UT Lead project page code now includes deadline rule display logic.
> - Participant active trial context now includes trigger-based survey availability and deadline values.
> - Product Trial survey activation notifications now include the calculated deadline payload.
> - `/trials/open-survey` continues to enforce availability server-side rather than relying only on hidden UI links.
>
> **Design Decisions**
> - Round Configuration dates are canonical because the UT Lead controls actual trial timing.
> - Product Team-requested start dates remain request/intake information, not the final trial schedule source of truth.
> - OOBE / First Impression is the only survey type that auto-unlocks from device receipt.
> - Survey 2 and later participant surveys must remain gated by UT Lead activation.
> - Deadline rules are trigger-based:
>   - OOBE / First Impression = device receipt confirmation date + 2 business days.
>   - Other participant result surveys = UT Lead activation date + 2 business days.
> - The MVP business-day rule is Monday-Friday only.
>
> **Untested / Needs Follow-up**
> - Needs local UI smoke confirmation for:
>   - OOBE appears only after device receipt.
>   - Device receipt unlocks no survey when no OOBE / First Impression survey exists.
>   - Non-OOBE surveys remain unavailable until UT Lead activation.
>   - Activated survey notification deadline matches the Active Trials deadline.
>   - Direct access / POST attempts against unavailable surveys redirect with `survey_not_available`.
> - Needs iterative UX review after real trial data is used, especially around wording of deadline labels and participant-facing urgency.
>
> **Known Exceptions / Deferred Cleanup**
> - Regional holidays are not included in business-day calculation yet.
> - Deadline duration is fixed at 2 business days; no per-survey configurable deadline exists yet.
> - No overdue/escalation/reminder workflow was added in this slice.
> - OOBE deadline is per participant because device receipt happens per participant; UT Lead table therefore shows the rule rather than one universal OOBE due date.
> - Product Trial participant tracking tables may still need future dynamic expansion as more surveys are added.
>
> **Next Recommended Step**  
> Put a pin in Product Trial survey availability/deadline MVP work, commit this slice, then resume with the next planned UTS priority after local smoke testing confirms the deadline behavior.

### 2026-05-21 — Canonical Report Format Alignment and Legacy Aggregate Report Hardening

> **Summary**  
> Advanced the report-format alignment work toward a single canonical “super report” structure shared by Product Trial reports, Historical Aggregate reports, and future BSC / Historical Survey reports. The session focused on proving the canonical renderer with Product Trial reports, then adapting Historical Aggregate reports to use the same report shape, KPI logic, section grouping, answer-label handling, and participant-profile context model. The aggregate report is now much closer to the Product Trial report format, though final AI-generated executive summaries and insights remain deferred until a shared canonical report AI service exists.
>
> **Changes Made**
> - Added a shared canonical report renderer used first by Product Trial / By Project reports.
> - Reworked Historical Aggregate report rendering so aggregate reports use the same canonical report layout rather than a separate visual/report format.
> - Added/continued DB-backed Historical Aggregate report generation, viewing, and publish-to-Reporting-&-Insights flow.
> - Refactored Historical Aggregate report generation to convert legacy uploaded survey rows into a Product Trial-style answer-row contract.
> - Extracted/shared Product Trial KPI calculation through reusable KPI helper logic so aggregate reports can use the same KPI math as Product Trial reports.
> - Hardened KPI classification for legacy aggregate reports, including Star Rating, NPS, Ready for Sales, and Software Rating.
> - Fixed legacy KPI wording edge cases such as “ready to go to market” and product-level rating questions that do not use the exact current Product Trial wording.
> - Added conservative report answer-value splitting so comma-containing answer choices like “No, I didn’t need to” or “No, I didn’t know that I could” remain intact instead of being split incorrectly.
> - Added `app/utils/report_answer_values.py` and applied it to canonical report rendering, Historical report rendering, and Bonus Survey profile aggregation.
> - Added a canonical Participant Profile / User Context block so profile/screener answers can be preserved as report context instead of leaking into Section Results.
> - Fixed profile filtering issues that caused answers such as Gender to appear inside KPI sections.
> - Removed temporary Product Trial report-generation debug output and user-facing diagnostic text.
> - Fixed a runtime aggregate-generation failure caused by a missing `_make_qual_question(...)` helper after the participant-profile pass.
>
> **Confirmed Working**
> - Product Trial report continued to render correctly after being moved onto the canonical report renderer.
> - Historical Aggregate report generation recovered after the missing helper fix.
> - Historical Aggregate reports now regenerate and render in the canonical report layout.
> - Aggregate reports now surface KPI Summary cards and KPI section grouping more consistently than before.
> - Ready for Sales and Star Rating are now detected in legacy aggregate data when the survey wording is close enough to the supported KPI patterns.
> - Comma-containing answer choices now render as complete answer options in reports instead of being split into misleading fragments.
> - User confirmed the remaining Software Rating ambiguity is acceptable for now and should be handled by survey-design conventions rather than endless classifier complexity.
>
> **Design Decisions**
> - Continue moving toward one canonical report renderer and one canonical report object shape rather than manually aligning four separate report pages.
> - Treat Product Trial reporting as the strongest current source pattern for KPI structure, source-survey handling, and report grouping.
> - Treat Historical Aggregate as the correct publishable legacy artifact, but not as the source of canonical report structure by itself.
> - Do not add aggregate-specific Executive Summary or Generate Insights buttons yet; those should come from a future shared canonical report AI service instead of one-off aggregate logic.
> - Preserve profile/screener answers in a dedicated Participant Profile / User Context block rather than mixing them into report sections.
> - Stop expanding classifier complexity once survey wording becomes inherently ambiguous; ambiguous section classification should be corrected through survey-design conventions and future manual UT Lead overrides.
>
> **Untested / Needs Follow-up**
> - BSC / Bonus Survey reports have not yet been migrated to the canonical renderer.
> - Historical / Survey single-dataset reports have not yet been migrated to the canonical renderer.
> - Product Trial and Historical Aggregate reports now share more rendering/report-shape behavior, but the full “single Generate Report Service” is not complete yet.
> - Executive Summary generation is still not implemented as a shared canonical report AI step.
> - Aggregate-level Insights generation is still deferred until the shared report AI service is created.
> - Current KPI classification is improved but still depends on survey wording being clear enough to distinguish overall product/software KPIs from feature-level ratings.
>
> **Known Exceptions / Deferred Cleanup**
> - Add DB-backed manual report section overrides so UT Leads can move sections between KPI / OOBE / First Impressions / Usage / Other and rename sections when classifier logic gets edge cases wrong.
> - Add a shared `canonical_report_ai_service.py` for Executive Summary and Insights generation instead of maintaining source-specific AI buttons and workflows.
> - Add survey-design guidance so KPI questions use consistent wording and feature-level rating questions do not resemble overall KPI questions.
> - Add stale-source detection for Historical Aggregate reports when underlying survey data changes after aggregate generation.
> - Continue reducing report-rendering duplication as BSC and Historical / Survey are migrated.
>
> **Next Recommended Step**  
> Create `app/services/canonical_report_ai_service.py` and wire Product Trial + Historical Aggregate reports to shared Executive Summary and Insights generation, before migrating BSC and Historical / Survey into the canonical report renderer.

### 2026-05-19 — Product Trial report alignment and UT Lead project cleanup

> **Summary**  
> Continued the Product Trial reporting buildout on the UT Lead project page. The report generation flow was reset away from the earlier ad-hoc Product Trial report model and moved much closer to the Historical report pattern: DB-backed saved reports, grouped section results, generated section names, generated SWOT summaries, and report controls inside the UT Lead project page. Several UT Lead page layout issues were also cleaned up around participant tracking, report grouping, and project metadata display.
>
> **Changes Made**
> - Added Product Trial report persistence through `product_trial_reports`.
> - Wired UT Lead report generation through POST-only actions on `/ut-lead/project`.
> - Reworked Product Trial report generation to follow the Historical-style report structure rather than a raw survey dump.
> - Fixed Google Forms CSV ingestion so duplicate column headers like repeated “Can you elaborate?” prompts are read positionally instead of being collapsed by `DictReader`.
> - Updated Product KPI detection so Star Rating and Software Rating are calculated from the actual Product Trial survey questions.
> - Rebuilt Product Trial report sectioning around the Product Trial survey rhythm: normal sections as 2–4 quant/categorical questions plus 1 qualitative follow-up, and KPI sections as 1 quant/categorical question plus 1 qualitative follow-up.
> - Added stable section grouping for Product Trial reports: KPIs, OOBE, First Impressions, Usage, and Other.
> - Added visible phase group headers to the Product Trial report section results.
> - Added Generate Names, Generate Summaries, and Generate Insights controls for saved Product Trial reports.
> - Moved Product Trial report success feedback toward toast-style behavior instead of permanent inline green notices.
> - Reduced top-level report chrome by removing the prominent mode/timestamp area and moving source details toward supporting metadata.
> - Tightened the participant execution tracking table by shortening survey headers, centering status/reminder columns, removing optional detail textareas, and keeping an explicit Save Tracking Changes button.
> - Improved UT Lead project page readability by replacing misleading “Round 26” display with an internal ID label and improving Wanted User Profile and recruiting date presentation.
>
> **Confirmed Working**
> - `python -m compileall app` passed after the report and layout passes that were locally applied.
> - Product Readiness Snapshot now calculates Star Rating and Software Rating from the uploaded Product Trial survey data.
> - Product Trial report generation now creates grouped section results instead of a raw unstructured survey dump.
> - Duplicate Google Forms question headers are now preserved by positional CSV ingestion.
> - Participant tracking table layout is more compact and easier to scan.
>
> **Design Decisions**
> - Product Trial reports should follow the Historical report model rather than becoming a separate reporting language.
> - GET renders remain read-only and display saved DB/report JSON state only.
> - Report generation, name generation, summary generation, and insights generation remain POST actions.
> - Product Trial report sections should be based on the known survey structure instead of relying entirely on AI inference.
> - Manual UT Lead section editing is needed later because even strong heuristics will not cover every real survey edge case.
> - Participant tracking should keep an explicit Save button for now instead of autosaving on every dropdown change.
> - Metrics should not be duplicated inside the report when the Product Readiness Snapshot already shows them.
> - Executive Summary should stay hidden until there is real generated insight/synthesis, not a stats-only placeholder.
>
> **Untested / Needs Follow-up**
> - The latest SWOT summary prompt change still needs a smoke test after applying the final service update.
> - Verify whether generated SWOT summaries now match Historical behavior closely enough or whether display-side empty-card cleanup is needed.
> - Confirm whether Product Trial Insights generation should use the Historical insights pattern exactly or a PT-specific adaptation.
> - Confirm Product Team Past Trials can display the saved generated Product Trial report under Reports & Insights.
>
> **Known Exceptions / Deferred Cleanup**
> - Manual UT Lead section editing is deferred until after generated summaries/SWOT behavior is stable.
> - Participant tracking tables and other survey-status tracking tables should later be built dynamically from configured round surveys as more surveys are added.
> - Uploading files currently returns the user to the top of the page; this scroll-position annoyance is deferred.
> - BSC/Bonus Survey reporting still needs to be realigned with the improved Historical/Product Trial pattern later.
> - The Product Trial report summary/insights layer is not finished.
>
> **Next Recommended Step**  
> Apply and smoke-test the latest Product Trial SWOT prompt alignment in `app/services/product_trial_report_service.py`, then inspect whether the renderer in `app/handlers/user_trial_lead_project.py` needs to hide empty SWOT categories or adjust the summary layout.10b

### 2026-05-12 — Feedback-first survey result ingestion

> **Summary**  
> Implemented the feedback-first ingestion model for Product Trial and Bonus/BSC survey result uploads. Recruiting remains identity-strict, but PT and Bonus/BSC result ingestion now preserves valid submitted feedback even when participant identity cannot be confidently matched. Attribution is now tracked separately through token, email, anonymous, unmatched, and review-required states.
>
> **Changes Made**
> - Added DB-backed attribution metadata for Bonus/BSC participation, Product Trial survey distribution, and upload audit records.
> - Updated Bonus/BSC result ingestion so token matches are high-confidence, email matches are medium-confidence, and anonymous/unmatched responses are still ingested with low-confidence attribution.
> - Updated PT result ingestion with the same feedback-first model while preserving strict identity requirements for Recruiting uploads.
> - Added upload audit counts for total respondent rows, token matches, email matches, anonymous rows, unmatched rows, and review-needed rows.
> - Added persistent attribution summaries to Bonus/BSC and PT result views.
> - Added tracked SQL migration documentation at `app/docs/db/feedback_first_survey_ingestion.sql`.
>
> **Confirmed Working**
> - Latest refreshed zip `app_20260512_122035_959948.zip` was verified.
> - Targeted `py_compile` passed across the touched handlers, DB helpers, and services.
> - Migration SQL file was confirmed present and populated.
> - Bonus/BSC ingestion was user-confirmed working.
> - The feedback-first ingestion behavior was confirmed as the target design for PT and Bonus/BSC reporting workflows.
>
> **Design Decisions**
> - Recruiting remains identity-strict because recruiting depends on verified system membership and eligibility.
> - PT and Bonus/BSC result uploads are now feedback-first: submitted feedback is included even when attribution is imperfect.
> - Identity matching now enriches attribution rather than deciding whether a response exists.
> - Tokens remain the strongest attribution method, email is a fallback, and anonymous/unmatched rows are preserved with explicit low-confidence/review metadata.
> - Reports should disclose attribution quality instead of silently dropping unmatched feedback.
>
> **Untested / Needs Follow-up**
> - PT upload output should be visually smoke-tested after the next normal Survey 1 or Survey 2 results upload.
> - Bonus/BSC and PT report analysis should be audited to confirm anonymous/unmatched responses are included in analysis but not overused for identity-sensitive conclusions.
> - Attribution output/banner formatting works functionally but still needs visual polish.
>
> **Known Exceptions / Deferred Cleanup**
> - Attribution display needs UI refinement.
> - Bonus Survey report page still has some nested container complexity.
> - Collapsible Bonus Survey report sections are deferred.
> - Neutral route rename from `/surveys/bonus/active?survey_id=...` to a clearer view/detail route is deferred.
> - CEO-style high-ROI recommended actions are deferred until the saved report schema supports them.
>
> **Next Recommended Step**  
> Start Priority 7: harden the current survey/reporting pipeline, beginning with an audit of report generation after feedback-first ingestion to ensure unmatched/anonymous feedback is included, clearly disclosed, and not incorrectly used for identity-sensitive participant/profile conclusions.

### 2026-05-11 — Priority 6 IT-review security hardening completed

> **Summary**  
> Completed the Priority 6 security hardening and IT-review readiness pass for UTS. The work covered CSRF, IDOR/object ownership, permission gates, SQL safety, upload validation, debug/error leakage, secrets/config handling, browser security headers, login throttling, trusted proxy IP handling, POST body-size limits, legal document sanitization, registration token TTL, and final Codex read-only straggler review. The final Codex pass found no confirmed Critical, High, or Medium patch-today findings remaining.
>
> **Changes Made**
> - Completed CSRF coverage across POST routes, including delegated Product Team handlers and JSON/fetch-style routes where applicable.
> - Hardened IDOR/object ownership validation for key route identifiers including `project_id`, `round_id`, `survey_id`, `bonus_survey_id`, `section_id`, `context_id`, `dataset_id`, `notification_id`, `document_id`, `session_id`, and selected user IDs.
> - Added explicit permission gates to privileged GET routes for UT Lead, Product Team, Admin approvals, UT Lead selection, Bonus Survey management, and survey management pages.
> - Hardened SQL safety by validating dynamic `IN (...)` placeholder builders, lookup IDs, permission levels, sort/status filters, and whitelisted dynamic SQL fragments.
> - Added shared CSV upload validation, including file presence, CSV extension checks, size checks, empty-file rejection, filename sanitization, and safe upload/ingest failure redirects.
> - Removed or neutralized raw debug/error leakage from browser-facing paths, Bonus Survey flows, Historical flows, login telemetry, survey upload ingestion, selection scoring, profile scoring, and security logging.
> - Hardened secrets/config behavior, including required DB config, safer AI token cache handling, sanitized AI/token error output, stricter SMTP configuration, production secure-cookie guardrails, and local secret ignore rules.
> - Added centralized app-level security headers, including `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Content-Security-Policy`, and `Cache-Control` for non-static responses.
> - Fixed static asset MIME handling so JavaScript files are served as `application/javascript` under `nosniff`, restoring Historical report expand/collapse behavior.
> - Added DB-backed login throttling through `login_rate_limits`, replacing process-local lockout state.
> - Added trusted-proxy-only client IP resolution for login throttling, with `TRUSTED_PROXY_IPS` expected to be set for production nginx.
> - Added a centralized POST body-size guard using `MAX_POST_BODY_BYTES` before request-body parsing.
> - Added legal document HTML sanitization for public rendering, editor loading, draft saving, and publishing.
> - Added registration-token TTL enforcement through `REGISTRATION_TOKEN_TTL_SECONDS`, with expired tokens deleted on read.
>
> **Confirmed Working**
> - Patch-level `py_compile` checks passed throughout the security remediation pass.
> - Final touched security files compiled successfully after the latest refresh.
> - The latest timestamped app zip was confirmed after the static MIME hotfix, login throttling/body-size/proxy patch, legal sanitizer patch, and registration TTL patch.
> - Historical Trial report section expansion was UI-confirmed working again after the static MIME hotfix.
> - Final Codex read-only review confirmed the current repo was not stale and found no confirmed Critical, High, or Medium patch-today findings remaining.
> - Final Codex review confirmed prior fixes remained present, including security headers, static MIME handling, DB-backed login throttling, trusted proxy IP handling, legal sanitization, registration TTL, logout `HttpOnly`, sensitive logging cleanup, and upload debug cleanup.
>
> **Design Decisions**
> - Stopped the Codex/security loop after the final pass produced no Critical, High, or Medium patch-today findings, to avoid diminishing returns and unnecessary churn.
> - Treated `main.py` as the explicit traffic cop and kept changes compatible with the current manual routing architecture rather than introducing framework-level rewrites.
> - Kept CSP `'unsafe-inline'` as a known staged hardening exception because the current UI still relies on inline scripts/styles/event handlers; strict CSP should be handled later as a dedicated hardening project.
> - Treated Bonus Survey external survey redirects as intentional product behavior, not a patch-today vulnerability, because Bonus Surveys may legitimately redirect users to external survey providers.
> - Chose app-side and infrastructure-side layered controls for request size, trusted proxy handling, HTTPS/session cookie behavior, and upload validation.
>
> **Untested / Needs Follow-up**
> - Browser-level negative tests can still be expanded later for bad CSRF tokens, tampered IDs, invalid uploads, oversized requests, expired registration tokens, and lower-permission access attempts.
> - Production environment values still need to be confirmed when deploying, especially `APP_ENV=production`, `SESSION_COOKIE_SECURE=true`, `TRUSTED_PROXY_IPS=127.0.0.1`, and `MAX_POST_BODY_BYTES=12582912`.
> - nginx should retain or add `client_max_body_size 12m` and `X-Forwarded-Proto $scheme` for the UTS server block.
> - IT may still request evidence screenshots, route matrices, response-header samples, or environment/config screenshots.
>
> **Known Exceptions / Deferred Cleanup**
> - Bonus Survey launch currently redirects to an externally configured survey URL after validating `http/https`, netloc presence, and exactly one `user_token_here` placeholder. This is intentional behavior, but future hardening should add an approved survey-host allowlist or governance workflow.
> - CSP still allows `'unsafe-inline'` for scripts/styles. This is deferred because immediate removal would likely break existing inline UI behavior; strict CSP should be handled later by moving inline scripts/event handlers to static JS or adding nonce/hash support.
> - Duplicate/stale code still exists in parts of `main.py`; cleanup remains deferred because the security pass intentionally avoided broad refactoring.
> - Some remaining Low/Info hardening items may be found by future audits, but no confirmed Critical/High/Medium patch-today findings remain from the final Codex pass.
>
> **Next Recommended Step**  
> Return to the paused MVP workstream: Priority 5D — align Bonus Survey results rendering with the Historical report format.

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