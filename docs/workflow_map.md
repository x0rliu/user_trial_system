# UTS Workflow Map

This document explains the major workflows in the User Trial System.

Purpose:
- Show how users move through the system.
- Explain which routes belong to each workflow.
- Identify where state is created, updated, or read.
- Clarify which data source owns each step.
- Make the system understandable without reading every file.

This document complements:

- `README.md` — documentation entry point
- `route_map.md` — URL-by-URL request map
- `data_map.md` — database/cache/source-of-truth map
- `ai_map.md` — AI usage and output map
- `changelog.md` — session-by-session engineering history

---

# Core Architecture Pattern

UTS follows a simple request lifecycle:

```text
Browser
  → app/main.py route table
  → _render_*() for GET
  → handle_*_post() for POST
  → app/handlers/*
  → app/services/* when business logic is needed
  → app/db/* or cache layer
  → redirect or rendered page
```

## GET Rule

GET routes are render-only.

```text
GET request
  → _render_<feature>()
  → load data
  → build HTML
  → return page
```

GET routes must not mutate database state.

## POST Rule

POST routes mutate state or trigger actions.

```text
POST request
  → handle_<feature>_post()
  → validate input
  → write/update state
  → redirect to GET page
```

POST routes should not render HTML directly.

## Known Deferred Exceptions

Some working AJAX/JSON flows remain intentionally deferred:

```text
POST /legal/documents/save
POST /legal/documents/publish
POST /admin/users/update-permission
POST /settings/demographics/save
```

These should not be changed casually because frontend behavior depends on them.

---

# Actor Types

UTS currently supports several user roles and interaction patterns.

| Actor | Role in System |
|---|---|
| Guest | Can view public informational pages and legal/public content |
| Participant | Applies to trials, signs NDAs, completes onboarding, accesses surveys |
| Product Team | Requests new user trials and responds to UT review decisions |
| User Trial Lead | Configures trials, recruits users, manages selection, uploads surveys/results |
| Admin | Reviews approvals, manages users, accesses higher-level operations |
| Bonus Survey Creator | Creates bonus surveys and submits them for approval |
| Legal/Admin User | Maintains legal documents, drafts, and published versions |

---

# Workflow 1 — Public Entry, Registration, and Onboarding

## Purpose

Move a new user from public access to a complete participant account.

## High-Level Flow

```text
Guest visits site
  → registers
  → verifies email
  → logs in / session created
  → completes demographics
  → signs global NDA
  → accepts participation guidelines
  → sees welcome page
  → lands on dashboard or next required step
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Register | `/register` | `/register` | Creates user registration |
| Verify email | `/verify-email` | `/verify-email` | Marks email verified, creates session |
| Login | `/login` | `/login` | Creates session |
| Demographics | `/demographics` | `/demographics` | Saves demographic profile |
| Global NDA | `/nda` | `/nda` | Saves NDA acceptance |
| Guidelines | `/participation-guidelines` | `/participation-guidelines` | Saves guideline acknowledgement |
| Welcome | `/welcome` | `/welcome` | Marks welcome/onboarding complete |

## Source of Truth

| Data | Source |
|---|---|
| User identity | Database |
| Email verification | Database |
| Session | Session service / session store |
| Demographics | Database |
| Global NDA acceptance | Database |
| Guidelines acknowledgement | Database |
| Onboarding state | Derived from database state |

## Notes

The onboarding flow is resumable. Users may exist in partial states and should always be routed to the next incomplete requirement.

---

# Workflow 2 — Profile Completion and Settings

## Purpose

Collect participant profile data used for trial eligibility, targeting, segmentation, and participant selection.

## High-Level Flow

```text
User logs in
  → opens profile wizard
  → completes interests
  → completes basic profile
  → completes advanced profile
  → views profile summary
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Profile wizard | `/profile/wizard` | — | Render only |
| Interests | `/profile/interests` | `/profile/interests` | Saves interest selections |
| Basic profile | `/profile/basic` | `/profile/basic` | Saves basic profile answers |
| Advanced profile | `/profile/advanced` | `/profile/advanced` | Saves advanced profile answers |
| Profile summary | `/profile` | — | Render only |
| Settings | `/settings` | `/settings` | POST is fallback redirect only |
| Password change | — | `/settings/password/change` | Updates password |
| Settings demographics inline save | `/settings/demographics` | `/settings/demographics/save` | JSON exception |

## Source of Truth

| Data | Source |
|---|---|
| Profile answers | Database |
| Interest profile | Database |
| Settings demographics | Database |
| Profile summary | Derived from database |

## Notes

Profile data should be treated as persistent state. No profile state should exist only in browser memory.

---

# Workflow 3 — Product Team Trial Request

## Purpose

Allow Product Team users to request a new User Trial.

## High-Level Flow

```text
Product Team user opens request trial area
  → creates draft
  → fills project basics
  → fills timing and scope
  → fills stakeholders
  → reviews request
  → submits for UT review
  → draft becomes DB-backed pending request
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Request trial home | `/product/request-trial` | — | Render only |
| Create draft | — | `/product/request-trial/create` | Creates cache draft |
| Basics | `/product/request-trial/wizard/basics` | `/product/request-trial/wizard/basics` | Saves basics to draft |
| Timing | `/product/request-trial/wizard/timing` | `/product/request-trial/wizard/timing` | Saves timing/scope to draft |
| Stakeholders | `/product/request-trial/wizard/stakeholders` | `/product/request-trial/wizard/stakeholders` | Saves stakeholders to draft |
| Review | `/product/request-trial/wizard/review` | `/product/request-trial/submit` | Converts draft to DB-backed request |
| Pending status | `/product/request-trial/pending` | — | Render only |

## Source of Truth

| Stage | Source |
|---|---|
| Drafting | Cache |
| Submitted request | Database |
| Approval status | Database |
| Notifications | Database |

## Important State Transition

```text
Cache draft
  → submit
  → database project/round records
  → cache draft deleted
  → approval notification created
```

## Notes

The draft cache is temporary. Once submitted, the database becomes the source of truth.

---

# Workflow 4 — Admin / UT Approval of Product Trial Request

## Purpose

Allow Admin or UT Lead reviewers to approve, decline, request information, or request changes for Product Team trial requests.

## High-Level Flow

```text
Reviewer receives notification
  → opens approvals dashboard
  → views project request
  → chooses approval action
  → system records decision
  → request status updates
  → Product Team is notified when action is needed
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Approval dashboard | `/admin/approvals` | — | Render only |
| Product approval detail | `/admin/approvals/project` | — | Render only |
| Submit approval action | — | `/admin/approvals/submit` | Updates approval/project-round state |
| Approval alias | — | `/admin/approval` | Updates approval/project-round state |

## Possible Actions

| Action | Result |
|---|---|
| Approve | Assigns UT Lead / moves trial forward |
| Request Info | Marks request as info requested |
| Request Changes | Marks request as change requested |
| Decline | Records decline decision |
| Withdraw | Used in some Product Team response flows |

## Source of Truth

| Data | Source |
|---|---|
| Approval request | Database |
| Approval action history | Database |
| Project round status | Database |
| Notifications | Database |

---

# Workflow 5 — Product Team Responds to Review Feedback

## Purpose

Allow Product Team users to respond when UT requests more information or proposes changes.

## High-Level Flow

```text
Product Team user sees action-required request
  → opens info-requested or change-requested page
  → submits response
  → request returns to UT review
  → UT/Admin is notified
```

## Routes

| Scenario | GET Route | POST Route | State Change |
|---|---|---|---|
| Info requested | `/product/request-trial/info-requested` | `/product/request-trial/info-requested/respond` | Records response and returns to review |
| Change requested | `/product/request-trial/change-requested` | `/product/request-trial/change-requested/respond` | Accepts/counters/withdraws |

## Source of Truth

| Data | Source |
|---|---|
| Request status | Database |
| Product Team response | Approval/action history table |
| Notification | Database |

---

# Workflow 6 — UT Lead Trial Setup and Management

## Purpose

Allow UT Leads to configure and manage approved trial rounds.

## High-Level Flow

```text
UT Lead opens trials dashboard
  → opens project/round page
  → configures trial details
  → saves settings
  → uploads survey links/configuration
  → opens recruiting or selection workflows
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| UT Lead trials overview | `/ut-lead/trials` | — | Render only |
| UT Lead project page | `/ut-lead/project` | `/ut-lead/project` | Saves project/round configuration |
| Survey upload | `/survey/upload...` | `/survey/upload...` | Saves survey data/configuration |
| End recruiting | — | `/trials/end-recruiting` | Closes recruiting status |

## Source of Truth

| Data | Source |
|---|---|
| Project details | Database |
| Round details | Database |
| Survey links/configuration | Database |
| Recruiting state | Database |

## Notes

UT Lead actions should always persist to the database. Trial setup must be resumable.

---

# Workflow 7 — Participant Trial Discovery and Application

## Purpose

Allow participants to browse recruiting/upcoming trials and apply.

## High-Level Flow

```text
Participant opens recruiting trials
  → views trial details
  → applies
  → system records application
  → participant may be redirected to recruiting survey
  → participant can withdraw if needed
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Recruiting trials | `/trials/recruiting` | — | Render only |
| Upcoming trials | `/trials/upcoming` | — | Render only |
| Record interest | `/trials/interest` | `/trials/interest` | POST records interest |
| Apply | — | `/trials/apply` | Creates application |
| Withdraw | — | `/trials/withdraw` | Withdraws application |

## Source of Truth

| Data | Source |
|---|---|
| Recruiting trial visibility | Database |
| Applications | Database |
| Interest records | Database |
| Recruiting survey tokens | Database/service |

## Notes

GET `/trials/interest` does not mutate. It safely redirects back to upcoming trials.

---

# Workflow 8 — User Selection

## Purpose

Allow UT Leads to select participants from an eligible applicant/user pool.

## High-Level Flow

```text
UT Lead starts selection
  → selection session is created or loaded
  → selection page renders current pool
  → UT Lead applies selection actions
  → confirms selection
  → selection session status updates
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Start/load selection | — | `/trials/selection/init` | Creates or loads selection session |
| Selection page | `/trials/selection` | `/trials/selection` | Applies selection changes |
| Confirmation page | `/trials/selection/confirm` | `/trials/selection/confirm` | Confirms selection status |
| POST bridge | `/trials/selection/confirm/post-bridge` | — | Render-only bridge |

## Source of Truth

| Data | Source |
|---|---|
| Selection session | Database |
| Selected users | Database |
| Alternates | Database |
| Selection status | Database |

## Notes

The debug GET selection route was removed from active routing because it mutated state from GET.

---

# Workflow 9 — Active Trial Participant Onboarding

## Purpose

Move selected participants through trial-specific requirements.

## High-Level Flow

```text
Participant selected
  → sees active trial
  → signs per-trial NDA
  → confirms shipping details
  → accepts responsibilities
  → receives survey/access instructions
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Active trials | `/trials/active` | — | Render only |
| Per-trial NDA | `/trials/nda` | `/trials/nda` | Saves trial NDA acceptance |
| Confirm shipping | — | `/trials/confirm-shipping` | Confirms existing shipping info |
| Save shipping | — | `/trials/save-shipping` | Saves shipping details |
| Responsibilities | `/trials/responsibilities` | `/trials/responsibilities` | Saves acknowledgement/decline |

## Source of Truth

| Data | Source |
|---|---|
| Participant assignment | Database |
| Trial NDA acceptance | Database |
| Shipping details | Database |
| Responsibility acknowledgement | Database |

## Notes

Shipping should remain DB-derived. UT Leads should not manually check off participant status without corresponding persisted data.

---

# Workflow 10 — Notifications

## Purpose

Notify users about actions requiring attention and route them to the relevant page.

## High-Level Flow

```text
System creates notification
  → recipient sees badge/dropdown
  → user opens/dismisses/views notification
  → notification read/dismissed state updates
  → user lands on target page
```

## Routes

| Action | GET Route | POST Route | State Change |
|---|---|---|---|
| Notifications page | `/notifications` | — | Render only |
| Notification detail | `/notifications/view` | `/notifications/view` | POST marks read |
| Open target | — | `/notifications/open` | Dismisses notification and redirects |
| Dismiss | — | `/notifications/dismiss` | Dismisses notification |
| Mark all read | — | `/notifications/mark-read` | Marks all as read |

## Source of Truth

| Data | Source |
|---|---|
| Notification records | Database |
| Recipient read/dismissed state | Database |
| Badge count | Derived from database |

## Notes

Notifications should not reappear just because the underlying approval/request still exists. Notification visibility is based on read/dismissed state, not only request status.

---

# Workflow 11 — Bonus Survey Creation and Approval

## Purpose

Allow bonus survey creators to create, submit, and manage bonus surveys.

## High-Level Flow

```text
Creator creates bonus survey draft
  → saves basics
  → saves template
  → saves targeting
  → reviews survey
  → submits for approval
  → reviewer approves or requests changes/info
  → survey becomes active
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Bonus survey dashboard | `/surveys/bonus` | — | Render only |
| Create shell | `/surveys/bonus/create` | `/surveys/bonus/create/new` | Creates draft |
| Basics | `/surveys/bonus/create` | `/surveys/bonus/create/save-basics` | Saves basics |
| Template | `/surveys/bonus/create/template` | `/surveys/bonus/create/save-template` | Saves template |
| Targeting | `/surveys/bonus/create/targeting` | `/surveys/bonus/create/save-targeting` | Saves targeting |
| Review | `/surveys/bonus/create/review` | `/surveys/bonus/create/submit` | Submits for approval |
| Submitted/pending | `/surveys/bonus/submitted`, `/surveys/bonus/pending` | — | Render only |
| Approve | — | `/surveys/bonus/approve` | Activates survey |
| Request info | — | `/surveys/bonus/request-info` | Records request |
| Request changes | — | `/surveys/bonus/request-changes` | Records request |

## Source of Truth

| Stage | Source |
|---|---|
| Draft | Cache/database depending on current implementation |
| Submitted survey | Database |
| Approval tracker | Database |
| Active survey status | Database |
| Notifications | Database |

---

# Workflow 12 — Bonus Survey Participation

## Purpose

Allow eligible users to open and complete bonus surveys.

## High-Level Flow

```text
Participant opens available bonus surveys
  → chooses survey
  → POST records/open survey access
  → redirects to external/internal survey link
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Available surveys | `/surveys/bonus/take` | — | Render only |
| Open survey fallback | `/surveys/bonus/take/open` | — | Safe render fallback |
| Open survey action | — | `/surveys/bonus/take/open` | Records/open access and redirects |

## Source of Truth

| Data | Source |
|---|---|
| Bonus survey eligibility | Database |
| Survey access/open record | Database |
| Survey status | Database |

---

# Workflow 13 — Bonus Survey Upload, Structure, and Analysis

## Purpose

Upload bonus survey results, structure survey questions, and generate insights.

## High-Level Flow

```text
Creator/UT uploads survey CSV
  → system stores answers
  → structure editor groups questions
  → profile questions are classified
  → section structure is saved
  → analysis runs
  → report/results are rendered from stored data
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Upload page | `/surveys/bonus/upload` | `/surveys/bonus/upload...` | Saves uploaded survey data |
| Structure page | `/surveys/bonus/structure` | — | Render only |
| Generate structure | — | `/surveys/bonus/structure/generate` | Writes generated structure |
| Reset structure | — | `/surveys/bonus/structure/reset` | Resets structure |
| Classify profile | — | `/surveys/bonus/structure/classify-profile` | Updates placement/classification |
| Save structure | — | `/surveys/bonus/structure/save` | Saves manual edits |
| Add section | — | `/surveys/bonus/section/add` | Adds section |
| Rename section | — | `/surveys/bonus/section/rename` | Renames section |
| Delete section | — | `/surveys/bonus/section/delete` | Deletes section |
| Analyze | — | `/surveys/bonus/analyze...` | Runs/stores analysis |
| Close survey | — | `/surveys/bonus/close...` | Closes survey |
| Active/report view | `/surveys/bonus/active` | — | Renders stored results |

## Source of Truth

| Data | Source |
|---|---|
| Uploaded raw answers | Database |
| Question hash/order mapping | Database |
| Structure/sections | Database |
| AI-generated summaries/insights | Database |
| Report view | Derived from database |

## Notes

Question text alone is not enough to identify questions. Repeated prompts such as “Can you elaborate?” require question hash and order/position handling.

---

# Workflow 14 — Legal Document Management

## Purpose

Maintain legal documents with drafts, published versions, and auditable history.

## High-Level Flow

```text
Legal/admin user opens legal document editor
  → edits document
  → saves draft
  → publishes version
  → published legal document becomes available to users
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Legal index/editor | `/legal/documents` | — | Render only |
| Specific legal doc | `/legal/documents/<doc_id>` | — | Render only |
| Save draft | — | `/legal/documents/save` | Saves draft |
| Publish document | — | `/legal/documents/publish` | Publishes version |
| Public legal view | `/legal/<slug>` | — | Render only |
| Signed legal view | `/legal/signed/<slug>` | — | Render only |
| Download | `/legal/download/<document_id>` | — | Sends PDF/file |

## Source of Truth

| Data | Source |
|---|---|
| Legal draft content | Database |
| Published legal versions | Database |
| Signed document records | Database |
| Downloaded document output | Generated/read from stored content |

## Known Exception

Legal save/publish currently use AJAX/JSON responses. This is intentionally deferred because the workflow is working and version-auditable.

Do not convert this flow to PRG without inspecting and redesigning the editor frontend behavior.

---

# Workflow 15 — Historical Trial Ingestion and Reporting

## Purpose

Import pre-UTS trial data so legacy trials can be analyzed and compared with newer trials.

## High-Level Flow

```text
User creates historical context
  → uploads historical CSV
  → system reconstructs survey answer rows
  → system builds/generates section names
  → system generates section summaries
  → system generates insights
  → historical report can be viewed
```

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Historical landing | `/historical` | — | Render only |
| Create context | `/historical/create-context` | `/historical/create-context` | Creates context |
| Upload | `/historical/upload` | `/historical/upload` | Saves uploaded dataset |
| Context detail | `/historical/context` | — | Render only |
| Raw data | `/historical/raw` | — | Render only |
| Generate section names | — | `/historical/generate-section-names` | Stores generated names |
| Generate summaries | — | `/historical/generate-section-summaries` | Stores generated summaries |
| Generate insights | — | `/historical/generate-insights` | Stores generated insights |

## Source of Truth

| Data | Source |
|---|---|
| Historical context | Database |
| Historical dataset metadata | Database |
| Historical survey answers | Database |
| Generated section names | Database |
| Generated summaries/insights | Database |

## Notes

Historical ingestion must preserve question order/position to prevent section leakage and repeated-question collisions.

---

# Workflow 16 — Product Utility Creation

## Purpose

Allow product records to be created for use in project/trial workflows.

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| Create product form | `/products/create` | `/products/create` | Creates product record |

## Source of Truth

| Data | Source |
|---|---|
| Product record | Database |

---

# Workflow 17 — Admin User Management

## Purpose

Allow admins or authorized users to manage user permissions.

## Routes

| Step | GET Route | POST Route | State Change |
|---|---|---|---|
| User admin page | `/admin/users` | — | Render only |
| Update permission | — | `/admin/users/update-permission` | Updates permission level |

## Source of Truth

| Data | Source |
|---|---|
| User roles/permissions | Database |

## Known Exception

`POST /admin/users/update-permission` currently returns JSON. This is deferred pending frontend review.

---

# Workflow 18 — AI-Assisted Workflows

## Purpose

Use AI to assist with survey structuring, summaries, insights, and reporting.

## Current AI-Adjacent Workflows

| Workflow | AI Role | Output |
|---|---|---|
| Bonus survey section generation | Suggests/derives structure | Stored section/question mappings |
| Bonus survey analysis | Summarizes qualitative feedback and insights | Stored reports/insights |
| Historical section naming | Generates readable section names | Stored section names |
| Historical section summaries | Summarizes section feedback | Stored summaries |
| Historical insights | Generates broader report insights | Stored insight records |

## Source of Truth

AI output is not the source of truth by itself.

AI output becomes usable only after it is written to the database and rendered from stored records.

## Guardrail

AI should not invent evidence. Insights should be grounded in uploaded survey data, stored answers, and available quotes.

---

# Workflow Health Notes

## Strong Areas

- Main route table is now much easier to read.
- POST wrappers mostly follow `handle_*_post()` naming.
- GET wrappers mostly follow `_render_*()` naming.
- Major workflows now use redirect-after-POST behavior.
- Notifications now separate notification visibility from underlying approval status.
- Product request flow now has clear draft-to-database handoff.
- Bonus survey structure and analysis are increasingly DB-driven.

## Known Deferred Issues

| Area | Issue |
|---|---|
| Legal save/publish | AJAX/JSON exception intentionally preserved |
| Admin permission update | JSON exception |
| Settings demographics inline save | JSON exception |
| Bonus upload/analyze/close | Changed to redirect fallback but needs dummy-data retest |
| Duplicate render methods | Some duplicate definitions remain in `main.py` |
| Parser helpers | Both `parse_post_data()` and `_parse_post_data()` exist |
| Template anchors | Some templates may still mix legacy `{{ }}` and newer `__KEY__` patterns |