# Friction Reporting

## Purpose

Friction Reporting is a diagnostic layer for UTS.

Its purpose is not to track users for curiosity, count page views for vanity metrics, or create a surveillance-style admin panel.

Its purpose is to answer one practical question:

> Where does the system hurt?

The system should identify places where users are blocked, delayed, confused, forced to repeat actions, or exposed to unexpected errors. The weekly report should turn those findings into clear evidence-backed recommendations.

## Mental Model

The system works in four layers:

1. **Record structured events** during important flows.
2. **Aggregate and trim raw events** so the database does not become bloated.
3. **Run deterministic checks** for predefined friction and security patterns.
4. **Use AI to write the human-readable diagnosis** from the measured evidence.

The system detects.
AI explains.
Admins decide.

AI must never be the source of truth for severity. Severity must come from deterministic rules and DB-backed evidence.

## Non-Goals

Friction Reporting should not become:

- A raw page-view analytics dump.
- A list of every page every user visited.
- A report that says “10 users spent X minutes on Page Y” for every page.
- A surveillance tool focused on individual browsing behavior.
- A black-box AI judgment system.
- A replacement for application logs, exception logs, or IT security review.

The report should diagnose patterns, not narrate every click.

## Core Principle

Track meaningful flow events only.

A meaningful event is one that helps determine whether a user successfully moved through a required or semi-required process.

Examples:

- User reached a required step.
- User attempted to continue.
- Validation blocked the user.
- The save succeeded.
- The flow was completed.
- The user appears to have abandoned the flow.
- The system threw an error.
- The system detected suspicious or unauthorized behavior.

## Routing and State Rules

Friction reporting must respect the UTS routing model.

- GET routes render or redirect only.
- GET routes must not silently mutate state.
- POST routes may record explicit state changes.
- JSON/fetch telemetry POST routes may record page/step events if they are intentionally defined.
- The DB is the source of truth.
- AI-generated summaries are derived artifacts, not source-of-truth data.

For implementation, this means page entry tracking should be explicit. It should not be hidden inside unrelated page rendering logic.

## Tracked Flows

Tracking should apply primarily to wizards, required flows, and linear step-based workflows.

A flow should be tracked when the user is expected to move from Step A to Step B to Step C, and failure to advance tells us something meaningful.

Initial tracked flow candidates:

| Flow Key | Reason to Track |
|---|---|
| `onboarding` | Required user setup. |
| `profile_completion` | Important for eligibility, matching, shipping, and participant readiness. |
| `product_request_trial_wizard` | Product Team draft/submission friction. |
| `survey_response` | Trial-critical completion and data collection. |
| `legal_acceptance` | NDA/legal compliance. |
| `admin_approval` | Operational bottlenecks in admin/Product Team workflows. |

Usually not tracked at first:

| Area | Reason |
|---|---|
| Dashboard browsing | Useful later, but not inherently diagnostic. |
| About/statistics pages | Low workflow value. |
| Footer/legal browsing | Usually not part of a completion flow. |
| General navigation clicks | Too noisy unless tied to a defined flow. |

## Event Categories

Events should be categorized so UX friction, system errors, and security anomalies do not blur together.

Suggested categories:

| Category | Purpose |
|---|---|
| `ux_friction` | User flow progress, validation, abandonment, repeated attempts. |
| `system_error` | Unexpected server/application failures. |
| `security` | Permission denials, CSRF failures, suspicious access patterns, upload rejections, probing. |
| `operational` | Admin/Product Team workflow bottlenecks or delayed actions. |

## Core Event Types

For tracked flows, the minimum useful events are:

| Event Type | Meaning |
|---|---|
| `step_entered` | User reached a tracked step. |
| `submit_attempted` | User attempted to save, continue, submit, approve, or complete a step. |
| `validation_failed` | User was blocked by validation. |
| `submit_succeeded` | The POST/save/submit succeeded. |
| `step_completed` | A specific step was completed. |
| `flow_completed` | The whole flow was completed. |
| `system_error` | The system encountered an unexpected error. |
| `permission_denied` | User attempted an action or page they were not allowed to access. |
| `csrf_failed` | POST failed CSRF validation. |
| `upload_rejected` | Upload failed safety/validation checks. |
| `suspicious_input` | Input matched a predefined suspicious pattern. |

Successful posts must be logged for tracked flows because they provide the denominator.

Without success events, the system can only say errors happened. It cannot say whether those errors were rare, normal, severe, or catastrophic.

## Event Data Rules

Events should contain enough information for diagnosis, but not raw sensitive content.

Recommended event fields, conceptually:

| Field | Purpose |
|---|---|
| `EventID` | Unique event identifier. |
| `EventCategory` | `ux_friction`, `system_error`, `security`, or `operational`. |
| `EventType` | Specific event type. |
| `UserID` | User involved, when authenticated. |
| `SessionID` | Session involved, when available. |
| `FlowKey` | Flow name, such as `onboarding`. |
| `StepKey` | Step name, such as `device_ownership`. |
| `RoutePath` | Route involved. |
| `Method` | GET/POST where relevant. |
| `SeverityCandidate` | Optional initial severity candidate. |
| `ErrorCode` | Stable code such as `missing_serial_number`. |
| `MetadataJSON` | Limited structured metadata. |
| `CreatedAt` | Event timestamp. |

Metadata must not store passwords, tokens, raw survey answers, private free-text fields, uploaded file contents, or sensitive profile values unless explicitly required and reviewed.

Prefer codes over raw values.

Example:

Good:

```text
ErrorCode = missing_serial_number
MetadataJSON = {"device_type": "keyboard", "field": "serial_number"}
```

Avoid:

```text
MetadataJSON = {"serial_number_entered": "actual user input here"}
```

## Severity Ladder

Severity must be assigned by deterministic rules before AI writes the report.

| Severity | Name | Plain-English Meaning | Timing |
|---|---|---|---|
| S1 | Catastrophic failure | Immediate attention required. Core workflow blocked, data/security integrity at risk, or suspected attack/anomaly detected. | Immediate alert. |
| S2 | Needs fixing | Clear measurable friction that affects completion, confidence, data quality, or operations. | Weekly report priority. |
| S3 | Annoying | Repeated irritation or inefficiency, but most users recover. | Weekly report if repeated. |
| S4 | Nice to have | Low-risk polish or workflow improvement opportunity. | Backlog suggestion. |

## S1 — Catastrophic Failure

S1 means immediate attention is required.

S1 has two subtypes.

### S1-A — Catastrophic Functional Failure

A core system workflow is blocked, unsafe, or corrupting state.

Examples:

| Trigger | Why It Matters |
|---|---|
| Users cannot log in. | Users cannot access the system. |
| Users cannot complete onboarding. | New users cannot become eligible/active. |
| Users cannot submit assigned surveys. | Trial data collection is blocked. |
| Users cannot accept required legal/NDA documents. | Compliance flow is blocked. |
| Product Team cannot submit trial requests. | Intake workflow is blocked. |
| Admin approvals cannot be completed. | Operational workflow is blocked. |
| Data appears saved in UI but is missing from DB. | Data integrity risk. |
| Repeated 500 errors on critical routes. | Core functionality may be broken. |

Example report language:

> S1-A triggered because Survey 1 submission failed 5 times in 10 minutes on a critical route. Users may be blocked from completing assigned trial work.

### S1-B — Suspected Attack / Security Anomaly

The system detects abnormal behavior consistent with probing, tampering, brute force, unauthorized access attempts, or other suspicious activity.

The system does not need to know the exact attack in advance. It can detect suspicious patterns.

Examples:

| Signal | Possible Meaning |
|---|---|
| Many failed logins from same IP or account. | Brute-force attempt. |
| Many permission denials against privileged routes. | Unauthorized probing. |
| Repeated invalid IDs in resource URLs. | Object/ID tampering. |
| Repeated CSRF failures. | Forged/scripted POST attempts. |
| Unexpected POST attempts to known routes. | Bot/scanner behavior. |
| Upload rejections with suspicious extensions/content. | Malicious upload attempt. |
| Malformed input patterns. | Injection probing. |
| Rapid route scanning. | Automated crawling/probing. |
| Low-permission user repeatedly accessing admin routes. | Privilege probing. |
| Spike in 500 errors following strange inputs. | Possible exploit attempt. |

Example report language:

> S1-B triggered because one source generated 22 permission-denied events against admin routes in 10 minutes. Permission checks appear to have held, but the pattern is consistent with unauthorized route probing.

## S2 — Needs Fixing

S2 means the flow technically works, but measurable friction is high enough that it should become prioritized work.

Examples:

| Signal | Example |
|---|---|
| High validation failure rate. | 35% of users fail the device serial number step. |
| High abandonment after step entry. | 25% reach NDA review but do not continue. |
| Repeated failed attempts before success. | Users submit the same form 3+ times before passing. |
| Drop-off from assigned action. | Participants open survey checklist but do not start survey. |
| Support/contact spike. | Users ask the same question about one step repeatedly. |
| Admin workflow bottleneck. | Approval requests pile up at the same review step. |

Example report language:

> S2 triggered because Device Ownership had an elevated failed-submit rate. Users could eventually continue, but the error rate suggests the instructions or validation rules are not clear enough.

## S3 — Annoying

S3 means users are inconvenienced, but most still recover and complete the task.

Examples:

| Signal | Example |
|---|---|
| Repeated step revisits. | Users return to Shipping Info more than expected. |
| Non-blocking validation confusion. | Optional fields create repeated warnings. |
| Slow but successful completion. | Users take longer than expected but still finish. |
| Minor navigation confusion. | Users click the wrong link first, then recover. |
| Low-volume repeated issue. | A few users hit the same minor error. |

Example report language:

> S3 triggered because several users looped between Profile and Shipping Info, but completion remained healthy. This may be worth smoothing after higher-severity items.

## S4 — Nice to Have

S4 means the data suggests a possible improvement, but there is no strong evidence of harm.

Examples:

| Signal | Example |
|---|---|
| Optional feature is rarely used. | Few users customize dashboard cards. |
| Low-risk inefficiency. | Admins take extra clicks but complete normally. |
| Helpful page gets little engagement. | Users do not open a details page from a summary. |
| Enhancement opportunity. | A shortcut could reduce repetitive admin work. |

Example report language:

> S4 triggered because admins rarely opened the detailed view from the dashboard card. Consider whether the summary already provides enough value before expanding the detail page.

## Classification Dimensions

Severity should be based on a small set of explicit dimensions.

| Dimension | Question |
|---|---|
| Criticality | Is this a core flow? |
| Frequency | How many users hit it? |
| Failure Rate | What percentage were blocked, errored, or denied? |
| Recoverability | Could users continue without admin help? |
| Data Risk | Could this corrupt, lose, or misclassify important data? |
| Security/Privacy Risk | Could users see or change things they should not? |
| Trend Direction | Is it getting worse week over week? |
| Operational Impact | Does this delay Product Team, UT Lead, or Admin work? |

A useful mental model:

> Severity = criticality × frequency × impact × recoverability risk

This does not need to be literal multiplication in the first implementation. It means severity should be evidence-based, not vibe-based.

## Draft Thresholds

Initial thresholds should be conservative and adjustable after real data exists.

| Severity | Draft Threshold |
|---|---|
| S1 | Any security/data-loss issue; repeated critical-route 500s; critical flow blocked; high failure rate on required step; suspected attack pattern crosses threshold. |
| S2 | More than 15–20% validation failure on a required step; more than 10–15% abandonment after a required step; repeated failed attempts in a required flow. |
| S3 | 5–15% friction where users usually recover; repeated minor confusion; low abandonment. |
| S4 | Low friction, no meaningful abandonment, no criticality, mostly polish or efficiency. |

S1 thresholds should vary by event type. Some events are S1 even at low volume, such as permission leaks, data loss, or successful unauthorized access.

## Weekly Friction Report

The weekly report should focus on S2–S4.

S1 incidents should not wait for the weekly report. They should generate immediate alerts and then appear in the weekly report only as incident history.

Weekly report sections:

1. Executive summary.
2. Top S2 issues.
3. Repeated S3 annoyances.
4. S4 polish opportunities.
5. S1 incident recap, if any.
6. Evidence table.
7. Recommended next steps.
8. Items to monitor next week.

The weekly report should answer:

- Where did users get blocked?
- Where did users fail validation?
- Where did users abandon?
- Where did users loop or repeat steps?
- Where did system errors happen?
- Where did suspicious behavior occur?
- What changed compared with the prior period?
- What should be fixed first?

## Weekly Report Example

```text
Weekly Friction Report
Period: 2026-05-18 to 2026-05-24

Summary
Device Ownership was the clearest friction point this week. Users could eventually continue, but failed-submit rates suggest the serial number instructions or validation rules need improvement.

Top Finding — S2 Needs Fixing
Flow: onboarding
Step: device_ownership
Evidence:
- 31 users entered the step.
- 24 users attempted submission.
- 11 users hit validation failure.
- 8 failures were tied to missing or malformed serial number input.
- 6 users did not continue within 24 hours.

Diagnosis
The step appears to be understandable enough for some users to complete, but the failed-submit rate is high for a required onboarding step. The most likely issue is unclear serial number guidance or overly strict validation.

Recommended Next Step
Add inline serial number examples by device type, improve the error message, and preserve entered values after validation failure.
```

## S1 Immediate Alerts

S1 alerts should be created immediately when deterministic rules cross a threshold.

Initial alert destination:

1. Create DB alert row.
2. Create in-app admin notification.
3. Show unresolved S1 alerts in an admin-visible location.

Later alert destinations:

- Telegram.
- Email.
- Other admin notification channels.

S1 alerts should include:

| Field | Purpose |
|---|---|
| Alert ID | Unique alert. |
| Severity | Always S1 for immediate alerts. |
| Subtype | S1-A functional or S1-B security. |
| Trigger Rule | Exact deterministic rule that fired. |
| Evidence | Counts, route, flow, affected step, timeframe. |
| First Seen | First event timestamp. |
| Last Seen | Most recent event timestamp. |
| Status | Open, investigating, resolved, dismissed. |
| Resolution Notes | Admin explanation after review. |

## AI Role

AI should write the explanation, not discover truth from raw noise.

AI receives an evidence bundle prepared by deterministic code.

AI may:

- Summarize findings.
- Explain why the finding matters.
- Suggest likely causes when evidence supports them.
- Recommend next steps.
- Separate urgent items from backlog items.
- Write in clear admin-friendly language.

AI must not:

- Invent counts.
- Invent user behavior.
- Invent root causes.
- Assign severity independently.
- Claim an attack definitively occurred unless the evidence proves it.
- Store or expose sensitive raw user input.

AI should use careful language:

Good:

> This pattern is consistent with unauthorized route probing.

Avoid:

> This user attacked the system.

Good:

> The most likely explanation is unclear serial number guidance.

Avoid:

> Users were confused because the page is badly designed.

## Evidence Bundle Contract

The report generator should send AI a compact evidence bundle, not raw event logs.

Example evidence bundle shape:

```text
FindingID: onboarding_device_ownership_validation_failure
Severity: S2
FlowKey: onboarding
StepKey: device_ownership
PeriodStart: 2026-05-18
PeriodEnd: 2026-05-24
UsersEntered: 31
SubmitAttempts: 24
ValidationFailures: 11
SubmitSuccesses: 13
UsersAbandonedWithin24h: 6
TopErrorCodes:
  - missing_serial_number: 5
  - malformed_serial_number: 3
PriorWeekValidationFailureRate: 22.0%
CurrentWeekValidationFailureRate: 45.8%
SystemClassificationReason: Required onboarding step exceeded validation-failure threshold.
```

## Retention Policy

Raw events should not live forever by default.

Recommended retention:

| Data | Retention |
|---|---|
| Raw activity/friction events | 30–90 days. |
| Weekly aggregate metrics | Long-term. |
| AI-written weekly reports | Long-term. |
| S1 alerts and resolutions | Long-term. |
| Security events | Longer than normal UX events, exact duration TBD. |

Before trimming raw events, the system should create aggregate snapshots so long-term trend reporting remains possible.

The system should be able to answer:

> Did onboarding friction improve over the last six months?

without needing every raw event forever.

## Data Storage Concepts

Final schema must be defined against the current DB before implementation.

Conceptual tables:

| Table | Purpose |
|---|---|
| `site_activity_events` | Raw structured event records. |
| `site_friction_weekly_metrics` | Aggregated weekly metrics by flow/step/event type. |
| `site_friction_findings` | Deterministically classified S2–S4 findings. |
| `site_friction_reports` | AI-written weekly reports and evidence snapshots. |
| `site_friction_alerts` | Immediate S1 alerts and resolution status. |

These names are placeholders until implementation.

## Implementation Stages

### Stage 1 — Documentation and Definitions

- Define tracked flows.
- Define event categories.
- Define event types.
- Define severity ladder.
- Define retention principles.
- Define AI role.

### Stage 2 — DB Foundation

- Add raw event table.
- Add S1 alert table.
- Add weekly report storage table.
- Keep schema explicit and queryable.

### Stage 3 — Event Recording

- Instrument one flow first.
- Recommended first flow: onboarding or Product Team request wizard.
- Record success and failure events for tracked POSTs.
- Record explicit step-entry events only through approved mechanism.

### Stage 4 — Deterministic Classifier

- Calculate event counts and rates.
- Apply S1–S4 rules.
- Store findings before AI runs.

### Stage 5 — AI Report Writer

- Send AI only the evidence bundle.
- Store generated report in DB.
- Render report for admins.

### Stage 6 — S1 Alerts

- Create immediate in-app alert when S1 rule fires.
- Add Telegram/email only after in-app alerts are reliable.

### Stage 7 — Dashboard Summary

- Optional dashboard card showing latest report status.
- Optional unresolved S1 alert count.
- Do not turn the dashboard into raw traffic analytics.

## First Implementation Candidate

Start with one flow only.

Recommended first flow:

> Onboarding / Profile Completion

Reason:

- It is step-based.
- It is required or near-required.
- It has clear success/failure events.
- It is easy to reason about abandonment.
- It affects user eligibility and trial readiness.

Do not instrument every route at once.

## Open Questions Before Coding

Before implementation, decide:

1. Which flow is first: onboarding, profile completion, Product Team request wizard, or survey response?
2. What raw event retention period should MVP use: 30, 60, or 90 days?
3. Should S1 security alerts notify only in-app first, or also Telegram/email later?
4. Which permission level can view friction reports?
5. Should user-level evidence be visible to admins, or should reports stay aggregate-first?
6. Which AI endpoint/model should generate the report?
7. Should reports be generated manually first before scheduled automation exists?

## Guiding Summary

Friction Reporting should behave like a diagnostic system, not a camera feed.

It should not say:

> Here is everything users looked at.

It should say:

> Here is where users struggled, here is the evidence, here is the severity, and here is the next recommended fix.

The core operating rule:

> Metrics detect. AI interprets. Admin decides.
