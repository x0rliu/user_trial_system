# UTS Data Map

This document explains where User Trial System data lives, which layer owns each type of state, and how data moves between workflows.

Purpose:
- Identify the source of truth for each workflow.
- Prevent shadow state.
- Make resume behavior explainable.
- Help future debugging and IT review.
- Clarify where cache, database, uploaded files, and AI outputs fit into the system.

This document complements:

- `README.md` — documentation entry point
- `route_map.md` — route-by-route request map
- `workflow_map.md` — user journey and workflow map
- `ai_map.md` — AI input/output boundaries
- `changelog.md` — session-by-session engineering history

---

# Core Data Rule

The database is the source of truth.

Temporary cache may exist only for draft/in-progress workflows before formal submission. Once a workflow is submitted, approved, uploaded, accepted, or otherwise committed, the database must own the state.

No critical workflow state should exist only in:

- Browser state
- HTML
- URL parameters
- Session-only state
- AI memory
- Local variables
- Temporary frontend JavaScript objects

---

# Data Layers

## 1. Database

The database stores persistent system state.

Examples:

- Users
- Roles and permissions
- Onboarding completion
- Demographics
- Profile answers
- Legal documents
- NDA signatures
- Product trial requests
- Project rounds
- Participants
- Applicants
- Notifications
- Survey links
- Uploaded survey answers
- Bonus survey structures
- Historical trial data
- AI-generated stored reports/insights

Database-backed state should be resumable.

---

## 2. Cache

Cache is allowed only for temporary drafts or short-lived intermediate state.

Known cache-backed areas:

| Area | Cache Purpose | Must Become DB? |
|---|---|---|
| Product Team trial request draft | Holds draft wizard data before submission | Yes, on submit |
| Bonus survey draft | Holds in-progress survey setup before submission | Yes, on submit/finalize depending on flow |

Cache is not the final authority for submitted workflows.

---

## 3. Uploaded Files

Uploaded files are inputs, not the long-term source of truth by themselves.

Examples:

- Bonus survey CSV uploads
- Historical trial CSV uploads
- Survey result exports

After upload, important data should be parsed and persisted into database rows.

The file may be retained for audit/reference, but analysis should read from stored database records, not repeatedly depend on the raw upload.

---

## 4. Generated AI Outputs

AI output is not source of truth until stored.

AI may generate:

- Section names
- Survey structure suggestions
- Qualitative summaries
- Insight narratives
- Historical report summaries
- Pattern analysis

Usable AI output should be stored in the database and rendered from stored records.

The app should not require rerunning AI just to render a page.

---

## 5. Session / Cookie State

Session data identifies the current user.

Session state should answer:

```text
Who is making this request?
```

It should not be the authority for:

```text
What onboarding step is complete?
What trial is active?
Who signed an NDA?
Who uploaded a survey?
What analysis exists?
```

Those must be database-derived.

---

# User / Account Data

## User Identity

| Data | Source of Truth | Notes |
|---|---|---|
| User ID | Database | Primary identity key used across workflows |
| Email | Database | Used for login/contact/account identity |
| Name | Database | Used for display and notifications |
| Password/auth credential | Database/auth service | Should never be exposed in app output |
| Email verification status | Database | Drives onboarding/login flow |
| Account creation date | Database | Audit/account history |

## Related Workflows

- Registration
- Email verification
- Login
- Role navigation
- Dashboard routing

## Important Rule

A user may exist in a partial onboarding state. The system should route them based on database-derived completion state.

---

# Session Data

| Data | Source of Truth | Notes |
|---|---|---|
| Session ID | Session service/store | Stored in cookie |
| User ID from session | Session service/store | Used to identify current actor |
| Cookie | Browser | Pointer only, not full state |

## Related Workflows

- Login
- Logout
- Authenticated route access
- Role navigation

## Important Rule

Logout must be POST-based because it mutates session state.

---

# Role / Permission Data

| Data | Source of Truth | Notes |
|---|---|---|
| Role mappings | Database | Used for permission checks |
| Effective permission level | Derived from database | Usually highest role level |
| Role navigation | Derived from permission level | Render-time only |

## Related Workflows

- Admin users
- Product Team views
- UT Lead views
- Legal/admin access
- Approvals

## Known Deferred Exception

`POST /admin/users/update-permission` currently uses JSON/AJAX behavior and is intentionally deferred pending frontend review.

The data itself remains database-backed.

---

# Onboarding Data

## Demographics

| Data | Source of Truth | Notes |
|---|---|---|
| Country | Database | Used for profile/eligibility |
| Gender | Database | Used for demographic targeting/reporting |
| Age/date-of-birth fields | Database | Used for eligibility and profile |
| Other onboarding demographics | Database | Should be resumable |

## NDA / Guidelines / Welcome

| Data | Source of Truth | Notes |
|---|---|---|
| Global NDA acceptance | Database | Required before full participation |
| Participation guidelines acknowledgement | Database | Required onboarding state |
| Welcome seen / onboarding complete | Database | Drives landing behavior |

## Related Workflows

- Registration
- Onboarding
- Dashboard routing

## Important Rule

Onboarding state should be derived from database completion flags/records, not stored as a separate shadow state.

---

# Profile Data

## Profile Answers

| Data | Source of Truth | Notes |
|---|---|---|
| Interests | Database | Trial matching and targeting |
| Basic profile answers | Database | Eligibility and segmentation |
| Advanced profile answers | Database | Deeper trial targeting |
| Profile summary | Derived from database | Rendered view only |

## Related Workflows

- Profile wizard
- Profile summary
- Settings
- Trial selection
- Survey segmentation

## Important Rule

Profile completion must be resumable. A partial profile is valid state.

---

# Settings Data

| Data | Source of Truth | Notes |
|---|---|---|
| Password change | Database/auth layer | Redirect-based POST |
| Settings demographics | Database | Currently inline JSON save |
| Settings fragments | Derived from database | GET fragments render current state |

## Known Deferred Exception

`POST /settings/demographics/save` currently uses JSON/AJAX behavior and is intentionally deferred pending frontend review.

---

# Legal Document Data

## Legal Documents

| Data | Source of Truth | Notes |
|---|---|---|
| Legal document draft | Database | Editable draft content |
| Published legal version | Database | Auditable published state |
| Document type | Database | Privacy, terms, NDA, etc. |
| Version number | Database | Used for audit/version history |
| Published timestamp | Database | Audit history |
| Published by | Database | Audit history |

## Signed Legal Documents

| Data | Source of Truth | Notes |
|---|---|---|
| Signed NDA record | Database | User acceptance |
| Signed document version | Database | Must reference the accepted version |
| Signed timestamp | Database | Audit requirement |
| Signed by user | Database | User identity |

## Related Workflows

- Legal editor
- Legal publish
- Public legal document view
- Signed document view
- Legal download
- Global NDA
- Per-trial NDA

## Known Deferred Exception

Legal save and publish currently use AJAX/JSON:

```text
POST /legal/documents/save
POST /legal/documents/publish
```

These are intentionally preserved because the legal workflow is working and auditable.

Do not convert this flow without inspecting the legal editor JavaScript and preserving version history.

---

# Product Team Trial Request Data

## Draft Stage

| Data | Source of Truth | Notes |
|---|---|---|
| Draft project ID | Cache | Temporary only |
| Basics | Cache | Project name, business group, category, purpose |
| Timing/scope | Cache | Shipping date, Gate X, countries, notes |
| Stakeholders | Cache | Names/roles/notes |
| Draft wizard state | Derived from cache | Not separately authoritative |

## Submitted Stage

| Data | Source of Truth | Notes |
|---|---|---|
| Project record | Database | Created on submit |
| Round record | Database | Created on submit |
| Submitted snapshot | Database | Should preserve request details |
| Request status | Database | Pending, approved, info requested, etc. |
| Approval notification | Database | Created on submit |

## Important Transition

```text
Product request draft in cache
  → POST /product/request-trial/submit
  → database project/round records created
  → cache draft deleted
  → notification created
```

After submission, the database is the source of truth.

---

# Product Trial Approval Data

| Data | Source of Truth | Notes |
|---|---|---|
| Approval request | Database | Based on submitted project/round |
| Approval action | Database | Approve, decline, request info, request changes |
| Reason category | Database | For non-approve actions |
| Reason/detail text | Database | Reviewer explanation |
| Assigned UT Lead | Database | Required on approval |
| Project round status | Database | Updated by approval action |
| Notifications | Database | Created for relevant users |

## Related Workflows

- Admin approval dashboard
- Product approval detail
- Product Team action-required responses

## Important Rule

Approval decisions must be auditable. They should not exist only as final status fields; action history matters.

---

# Product Team Review Response Data

| Data | Source of Truth | Notes |
|---|---|---|
| Info response text | Database/action history | Product response to UT request |
| Change response decision | Database/action history | Accept, counter, withdraw |
| Counter proposal detail | Database/action history | Required when countering |
| Updated request status | Database | Usually returns to pending UT review |
| Notification to UT/Admin | Database | Created after response |

## Related Workflows

- Info requested
- Change requested
- Product Team response

---

# Project / Round Data

## Project

| Data | Source of Truth | Notes |
|---|---|---|
| Project ID | Database | Stable project identity |
| Project name | Database | Display/reporting |
| Market name | Database | Product context |
| Business group | Database | Reporting/filtering |
| Product type/category | Database | Reporting/filtering |
| Description/purpose | Database | Request context |
| Created by | Database | Ownership/audit |
| Created/updated timestamps | Database | Audit |

## Round

| Data | Source of Truth | Notes |
|---|---|---|
| Round ID | Database | Stable trial round identity |
| Round name/number | Database | Trial execution |
| Region/countries | Database | Eligibility and reporting |
| User scope | Database | Internal/external/hybrid |
| Target users | Database | Recruiting/selection |
| Start/end dates | Database | Trial timeline |
| Ship date | Database | Shipping operations |
| Gate X date | Database/project/round | Decision timing |
| UT Lead | Database | Assigned owner |
| Status | Database | Request/recruiting/running/closed/etc. |

## Related Workflows

- Product request
- Approval
- UT Lead setup
- Recruiting
- Selection
- Active trial management
- Product Team current trials

---

# UT Lead Trial Configuration Data

| Data | Source of Truth | Notes |
|---|---|---|
| Trial/round configuration | Database | Saved from UT Lead project page |
| Profile criteria | Database | Used for recruiting and selection |
| Survey links/configuration | Database | Uploaded/saved by UT Lead |
| Recruiting status | Database | Open/closed state |
| Participant target | Database | Used by selection |

## Related Workflows

- UT Lead project setup
- Survey upload
- Recruiting
- Selection

## Important Rule

UT Lead setup must persist after every save. A user should be able to leave and return without losing configuration.

---

# Trial Application Data

| Data | Source of Truth | Notes |
|---|---|---|
| Application record | Database | User applied to round |
| Motivation text | Database | Optional/required depending on form |
| Withdrawal status | Database | User withdrew |
| Recruiting survey token | Database/service | Used to personalize recruiting survey link |
| Interest record | Database | User expressed interest in upcoming trial |

## Related Workflows

- Recruiting trials
- Upcoming trials
- Trial application
- Trial withdrawal
- Recruiting survey redirect

## Important Rule

GET `/trials/interest` must not record interest. Interest recording belongs to POST only.

---

# Selection Data

| Data | Source of Truth | Notes |
|---|---|---|
| Selection session | Database | Created/loaded by POST |
| Eligible/current pool | Database/derived service | Based on criteria and session |
| Selection steps | Database | Applied filters/actions |
| Selected users | Database | Final selected participants |
| Alternates | Database | Backup participants |
| Selection status | Database | Draft/selection/confirmed states |

## Related Workflows

- UT Lead selection
- Participant assignment
- Trial onboarding

## Important Rule

Selection state must not be created or changed from GET routes. The previous debug GET mutation was removed from routing.

---

# Participant / Active Trial Data

| Data | Source of Truth | Notes |
|---|---|---|
| Participant assignment | Database | User selected for trial |
| Per-trial NDA acceptance | Database | Required before access |
| Shipping details | Database | Participant-provided or confirmed |
| Shipping confirmation | Database | Confirmed by participant |
| Responsibility acknowledgement | Database | Accepted/declined by participant |
| Trial progress/status | Database | Used for active trial checklist |

## Related Workflows

- Active trials
- Trial NDA
- Shipping confirmation
- Responsibilities
- Survey access

## Important Rule

Checklist status should be derived from database records, not manually checked off in the UI.

---

# Shipping Data

| Data | Source of Truth | Notes |
|---|---|---|
| Delivery type | Database | Home/office/etc. |
| Recipient first/last name | Database | May differ from account name |
| Phone country/area/subscriber fields | Database | Structured phone |
| Address line 1/2 | Database | Shipping destination |
| City/state/postal/country | Database | Shipping destination |
| Office ID | Database | For office delivery |
| Save globally flag | Database behavior TBD | Needs careful design |

## Related Workflows

- Trial onboarding
- Shipping confirmation
- UT Lead logistics

## Important Rule

Shipping recipient identity is not necessarily the same as account identity.

---

# Survey Link / Upload Data

| Data | Source of Truth | Notes |
|---|---|---|
| Survey type | Database | Recruiting, survey 1, survey 2, consolidated, bonus, etc. |
| Internal/edit link | Database | Used by UT/Product/admin |
| Participant/distribution link | Database | Used by participants |
| Uploaded survey metadata | Database | File/source context |
| Survey completion data | Database once uploaded | Used for reminders/reporting |

## Related Workflows

- UT Lead survey setup
- Product current trials
- Participant checklist
- Reporting

## Important Rule

Survey upload should overwrite/update trial survey state for that trial. Completion status should be DB-derived.

---

# Notification Data

| Data | Source of Truth | Notes |
|---|---|---|
| Notification record | Database | Type and payload |
| Notification payload | Database | Context for rendering/action links |
| Recipient record | Database | Who receives notification |
| Read state | Database | Badge/dropdown behavior |
| Dismissed state | Database | Notification visibility |
| Created by | Database | Audit/source |
| Created timestamp | Database | Ordering/history |

## Related Workflows

- Product trial approvals
- Bonus survey approvals
- Product Team responses
- Trial reminders
- General system alerts

## Important Rule

Notification visibility should be controlled by notification recipient state, not only by the underlying object status.

A dismissed approval notification should not reappear simply because the request still exists.

---

# Bonus Survey Data

## Bonus Survey Draft / Setup

| Data | Source of Truth | Notes |
|---|---|---|
| Draft ID | Cache/database depending on implementation | Temporary drafting |
| Survey title/name | Database after save/submit | Display and approval |
| Purpose | Database | Context |
| Open/close dates | Database | Availability |
| Internal/edit link | Database | Creator/admin use |
| Participant/fill link | Database | Participant use |
| Targeting | Database | Eligibility |
| Approval status | Database | Draft/pending/active/etc. |

## Bonus Survey Approval

| Data | Source of Truth | Notes |
|---|---|---|
| Tracker ID | Database | Approval tracker |
| Approval action | Database | Approved/info/change/etc. |
| Actor user ID | Database | Who acted |
| Detail text | Database | Reviewer note |
| Status update | Database | Survey status change |

## Bonus Survey Participation

| Data | Source of Truth | Notes |
|---|---|---|
| Participation record | Database | User/survey association |
| Open/access record | Database | User opened survey |
| Survey token/link behavior | Database/service | Link personalization if used |

---

# Bonus Survey Uploaded Answers

| Data | Source of Truth | Notes |
|---|---|---|
| Bonus survey answer rows | Database | One row per answer/question/user |
| Participation ID | Database | Links answer to participant |
| Question text | Database | Human-readable question |
| Question hash | Database | Stable-ish question identity |
| Question order | Database | Required for repeated question text |
| Answer text | Database | Raw answer |
| Created/upload timestamp | Database | Audit |
| Bonus survey ID | Database | Survey ownership |

## Important Rule

Question text alone is not a safe key.

Repeated question text like:

```text
Can you elaborate?
```

must be disambiguated with question hash and order/position.

---

# Bonus Survey Structure Data

| Data | Source of Truth | Notes |
|---|---|---|
| Question structure rows | Database | Mapping questions to sections/profile/ignored |
| Section key | Database | Stable section identity |
| Section label/name | Database | Display |
| Section order | Database | Report ordering |
| Question order | Database | Question ordering |
| Placement type | Database | Profile/section/ignored/etc. if still used |
| Lock status | Database | Protects manual edits |

## Related Workflows

- Structure generation
- Manual structure editing
- Profile classification
- Report generation

## Important Rule

Survey structure should be saved before analysis. Analysis should read saved structure, not re-infer structure every time.

---

# Bonus Survey Analysis / Report Data

| Data | Source of Truth | Notes |
|---|---|---|
| Quantitative results | Derived from database answers | Should be recomputable |
| Qualitative themes | Database if AI-generated/stored | Stored output |
| Section summaries | Database | Generated or manually updated |
| Quotes/evidence | Database/report JSON | Must come from uploaded answers |
| Report JSON | Database | Cached/stored analysis output |
| Segment insights | Database/report JSON | Should use explicit segment builder |

## Related Workflows

- Bonus survey report view
- Re-generate insights
- Product/UT review of feedback

## Important Rule

AI-generated insight must be grounded in stored survey answers. It should not invent evidence.

---

# Historical Trial Data

## Historical Context

| Data | Source of Truth | Notes |
|---|---|---|
| Context ID | Database | Historical trial context |
| Product ID | Database | Links to product |
| Round number | Database | Historical round identity |
| Lifecycle stage | Database | Historical stage |
| Trial purpose | Database | Context |
| Internal/external mix | Database | Participant mix |
| Invited user count | Database | Historical metric |
| Description | Database | Context |
| Start/end dates | Database | Timeline |

## Historical Dataset

| Data | Source of Truth | Notes |
|---|---|---|
| Dataset ID | Database | Uploaded dataset |
| Context ID | Database | Parent context |
| Dataset type | Database | Survey 1, survey 2, validation, etc. |
| Source file name/path | Database/file storage | Audit/reference |
| Uploaded by | Database | Audit |
| Created timestamp | Database | Audit |

## Historical Survey Answers

| Data | Source of Truth | Notes |
|---|---|---|
| Response group ID | Database | Groups answers from one response |
| Question text | Database | Human-readable |
| Question hash | Database | Disambiguation |
| Question position | Database | Required for reconstruction |
| Answer text | Database | Raw answer |
| Numeric answer | Database | Quantitative value if available |
| Answer option | Database | Categorical value if available |
| Submitted timestamp | Database | If available |
| Metadata JSON | Database | Additional source info |

## Historical AI Outputs

| Data | Source of Truth | Notes |
|---|---|---|
| Section names | Database | Generated/stored |
| Section summaries | Database | Generated/stored |
| Insights | Database | Generated/stored |
| Insight run metadata | Database | Audit/rerun tracking |

## Important Rule

Historical ingestion must preserve question position. Without position, repeated qualitative prompts can leak across sections.

---

# Product Records

| Data | Source of Truth | Notes |
|---|---|---|
| Product ID | Database | Stable product identity |
| Product name | Database | Display/reporting |
| Product type/category | Database | Reporting and grouping |
| Business group | Database | Reporting and grouping |
| Market name | Database | Product context |

## Related Workflows

- Product creation
- Historical context creation
- Product Team requests
- Reporting and comparisons

---

# AI Data Boundary

AI does not own state.

AI may read:

- Uploaded survey answers
- Stored question structures
- Historical answer rows
- Product/trial metadata
- Segment views built by deterministic services

AI may produce:

- Suggested section names
- Summaries
- Themes
- Insights
- Recommendations

AI output becomes system data only after being stored.

## Important Rule

AI should not independently invent segmentation, eligibility, or source data. It should operate on explicit payloads built by the system.

See `ai_map.md` for detailed AI boundaries.

---

# Data Ownership by Workflow

| Workflow | Primary Source of Truth |
|---|---|
| Registration/login | Database + session service |
| Onboarding | Database |
| Profile | Database |
| Settings | Database |
| Legal documents | Database |
| Product request draft | Cache before submit |
| Product request submitted | Database |
| Product approval | Database |
| UT Lead trial setup | Database |
| Trial application | Database |
| Selection | Database |
| Participant onboarding | Database |
| Shipping | Database |
| Notifications | Database |
| Bonus survey draft/setup | Cache/database depending on stage |
| Bonus survey submitted/active | Database |
| Bonus survey answers | Database |
| Bonus survey structure | Database |
| Bonus survey analysis | Database |
| Historical upload/context | Database |
| Historical answers | Database |
| Historical insights | Database |
| Product records | Database |

---

# Known Deferred / Needs Verification

These items should be verified during Priority 5: Align DB schema with current app code.

| Area | Need |
|---|---|
| Exact table names | Confirm all names against live schema |
| Exact column names | Confirm against migrations/schema/export |
| Bonus survey draft storage | Confirm whether cache, DB, or hybrid currently owns each stage |
| Product request cache format | Document exact cache object shape |
| Legal version tables | Document exact draft/publish/signature relationships |
| Survey upload tables | Confirm all survey link/result tables |
| Historical insight tables | Confirm current insight run/output schema |
| Profile answer tables | Confirm profile mapping and answer storage |
| Notification recipient table | Confirm read/dismissed field names |
| Selection session tables | Confirm exact session/step/user structures |

---

# Data Integrity Risks

## 1. Shadow State

Risk:
State exists in cache, browser, or AI output but not database.

Mitigation:
Persist every meaningful transition to database and render from database.

## 2. Repeated Question Text

Risk:
Survey questions like “Can you elaborate?” appear multiple times and can contaminate analysis.

Mitigation:
Use question hash plus question order/position.

## 3. AJAX Exceptions

Risk:
Some POST routes return JSON and depend on frontend behavior.

Mitigation:
Document exceptions and avoid changing without frontend review.

## 4. Duplicate Parser Helpers

Risk:
`parse_post_data()` and `_parse_post_data()` may produce different data shapes.

Mitigation:
Consolidate carefully later, one route family at a time.

## 5. Cache-to-DB Handoff

Risk:
Draft data remains in cache after submission or DB data diverges from draft state.

Mitigation:
Explicit authority handoff on submit, then delete/ignore cache draft.

## 6. AI Drift

Risk:
AI-generated summaries include unsupported claims.

Mitigation:
Store AI output with evidence/quotes and render stored results only.