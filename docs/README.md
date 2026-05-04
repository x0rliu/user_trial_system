# UTS Documentation

This folder documents the architecture, workflows, data ownership, AI boundaries, and engineering history of the User Trial System.

The purpose of these documents is to make UTS explainable.

They are not meant to replace the code. They are meant to help a reviewer, future developer, IT partner, or future maintainer understand what the system does, how requests move through it, where state lives, and where AI is used.

---

# Documentation Index

## `route_map.md`

Explains the HTTP route structure.

Use this file to answer:

```text
What URL exists?
Is it GET or POST?
Which wrapper in app/main.py handles it?
Does it render, mutate, redirect, or return JSON?
Are there known routing exceptions?
```

This is the first file to read when debugging request flow.

---

## `workflow_map.md`

Explains the major user journeys.

Use this file to answer:

```text
How does a user move through registration?
How does Product Team request a trial?
How does Admin approval work?
How do bonus surveys move from draft to report?
How does historical ingestion work?
```

This is the first file to read when trying to understand the system as a product.

---

## `data_map.md`

Explains where state lives.

Use this file to answer:

```text
What is the source of truth for this workflow?
Is this data in the database, cache, uploaded file, session, or AI output?
When does draft state become database state?
Which areas still need schema verification?
```

This is the first file to read when debugging persistence or resumability.

---

## `ai_map.md`

Explains where AI enters the system.

Use this file to answer:

```text
Which workflows use AI?
What data does AI receive?
What does AI write?
Where is AI output stored?
What guardrails prevent hallucinated evidence?
```

This is the first file to read when reviewing AI risk, report generation, or insight quality.

---

## `changelog.md`

Records session-by-session engineering history.

Use this file to answer:

```text
What changed during a coding session?
Why was it changed?
What was confirmed working?
What remains untested?
What known exceptions were accepted?
What should be picked up next?
```

This is not a replacement for Git history. Git records file-level changes. The changelog records engineering intent and context.

---

# System Architecture Summary

UTS is a database-driven User Trial System built with plain Python and explicit routing.

The current architecture follows this shape:

```text
Browser
  → app/main.py
  → GET route calls _render_<feature>()
  → POST route calls handle_<feature>_post()
  → app/handlers/*
  → app/services/*
  → app/db/*
  → database / cache / uploaded data / stored report output
```

The system intentionally favors clarity and traceability over framework magic.

---

# Core Rules

## 1. Database is the Source of Truth

Persistent workflow state should live in the database.

Examples:

- User identity
- Onboarding state
- NDA signatures
- Profile answers
- Trial applications
- Product requests
- Project rounds
- Participant assignments
- Notifications
- Survey uploads
- Bonus survey structures
- Historical trial data
- Stored AI outputs

Temporary cache may exist for draft flows, but submitted workflows must become database-backed.

---

## 2. GET / POST Separation

GET routes render only.

```text
GET
  → _render_<feature>()
  → read data
  → render page
```

POST routes mutate state or trigger actions.

```text
POST
  → handle_<feature>_post()
  → validate input
  → update state
  → redirect
```

Known deferred AJAX/JSON exceptions are documented in `route_map.md`.

---

## 3. No Shadow State

Important state should not exist only in:

- Browser memory
- HTML
- URL parameters
- Session-only state
- AI memory
- Temporary local variables
- Hidden frontend logic

If the user needs to resume later, the state must be recoverable from the database or an explicitly documented cache-to-database flow.

---

## 4. AI Is Not the Source of Truth

AI can assist with:

- Survey structure
- Section naming
- Qualitative summaries
- Historical insights
- Pattern comparison
- Future recommendation logic

AI does not own state.

AI output becomes usable only after it is stored and rendered from stored records.

---

# Current Documentation Status

| File | Status | Notes |
|---|---|---|
| `route_map.md` | Created | Maps GET/POST routes and deferred exceptions |
| `workflow_map.md` | Created | Maps major system workflows |
| `data_map.md` | Created | Maps state ownership and data risks |
| `ai_map.md` | Created | Maps AI boundaries and guardrails |
| `changelog.md` | Template planned/created | Used when wrapping coding sessions |

---

# Known Deferred Areas

These are intentionally documented rather than hidden.

| Area | Reason Deferred |
|---|---|
| Legal save/publish AJAX behavior | Working legal versioning should not be casually broken |
| Admin permission AJAX update | Needs frontend review before PRG conversion |
| Settings demographics inline save | Needs frontend review before PRG conversion |
| Bonus upload/analyze/close fallback retest | Needs dummy data to safely verify |
| Exact DB schema alignment | Planned for Priority 5 |
| Duplicate render methods in `main.py` | Cleanup candidate, not immediate blocker |
| Parser helper consolidation | Needs careful route-family testing |

---

# How to Read These Docs

For a quick architecture review, read in this order:

```text
1. README.md
2. workflow_map.md
3. route_map.md
4. data_map.md
5. ai_map.md
6. changelog.md
```

For debugging a route, read:

```text
1. route_map.md
2. workflow_map.md
3. data_map.md
```

For reviewing AI/reporting behavior, read:

```text
1. ai_map.md
2. data_map.md
3. workflow_map.md
```

For understanding what changed recently, read:

```text
1. changelog.md
2. Git history
```

---

# Project Philosophy

UTS is not meant to be a magic system.

The goal is that every major behavior can be traced:

```text
Request
  → route
  → handler
  → service
  → database/cache
  → redirect/render
```

And every major insight can be traced:

```text
Uploaded/stored data
  → deterministic preparation
  → AI analysis if needed
  → stored output
  → rendered report
```

The system should be understandable, resumable, auditable, and maintainable.