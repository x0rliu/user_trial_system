# Bonus Surveys – TODO Details

This document expands on `todo.md` with intent, rules, and design notes.
Nothing here is binding unless explicitly marked **LOCKED**.

---

## 1. Core Flow (Blocking)

### Submit Bonus Survey for Approval
**Intent**
- Convert a completed draft into an approval request.
- Freeze all editable fields immediately.

**Rules**
- Submission must be user-initiated.
- Submission must be recorded by the system.
- Submission must be reversible only by admin action.

**Open Questions**
- Should submission validate *all* steps explicitly, or rely on wizard gating?

---

### Replace “Submit for Approval” Button State
**Intent**
- Provide immediate, unambiguous feedback.

**Behavior**
- Button changes to:
  - “Successfully submitted”
  - Disabled
- No page reload required (optional enhancement).

---

### Draft → Pending Approval Transition
**Intent**
- Visually and functionally separate editable vs locked states.

**Rules**
- Draft disappears from Drafting list.
- Appears under Pending Approval.
- Clicking opens Review page in read-only mode.

---

### Cache → Database Persistence (Approval Only)
**Intent**
- Draft cache remains volatile.
- Database remains canonical for approved surveys.

**Rules**
- No DB writes before approval.
- Approval is the only promotion path.
- Cache snapshot at approval time is what gets persisted.

**LOCKED**
- Cache is the source of truth until approval.

---

## 2. Approval & Status Lifecycle

### Approval States
- Request received
- Admin viewed
- Admin has questions
- Admin approved
- Admin denied
- Admin requires backend access

**Rules**
- Each transition must be logged.
- Admin actions require attribution.

---

### Admin Questions
**Intent**
- Allow clarification without rejection.

**Behavior**
- Survey remains locked.
- User can respond but not edit content.
- Admin can return to Drafting if needed.

---

### Denial
**Intent**
- Clear failure state with explanation.

**Rules**
- Denial requires reason.
- Survey returns to Drafting.
- Edit buttons reappear.

---

## 3. Notifications & Admin Actions

### In-System Notification
**Audience**
- Admins only.

**Content**
- Survey name
- Requesting user
- Submission timestamp
- Quick action links

---

### Email Notification
**Intent**
- Allow lightweight approval when busy.

**Rules**
- Email contains:
  - Summary snapshot
  - Survey link
  - Approve / Deny / Question buttons
- Email actions must route back into system.

**Open Question**
- Should email actions require login confirmation?

---

## 4. Targeting (Functional Gaps)

### Distribution Modes
**Options**
- Open invitation
- Direct invite
- Both

**Rules**
- Open = anyone matching targeting
- Direct = explicit email list
- Both = open + explicit emails

---

### Direct Invite Email Entry
**Behavior**
- One email per line.
- Validation on save.
- Duplicates removed silently.

---

### Review Targeting Summary
**Must Show**
- Parsed targeting description
- Email stats:
  - X / N already in system
  - Y / N will receive invites

---

## 5. Wizard & Navigation

### Wizard Integrity
**Rules**
- Current step always highlighted correctly.
- Future steps inaccessible until prerequisites met.
- Left rail links always preserve `draft_id`.

---

### Read-Only Views
**Intent**
- One render path, multiple modes.

**Rules**
- Edit buttons hidden when:
  - Pending Approval
  - Active
- Same template, different permissions.

---

## 6. Summary & Rendering Bugs

### Summary Rail
**Rules**
- Always reflects latest cached data.
- Never independently derived.
- No duplicated logic.

---

### Review Page Rendering
**Failure Modes to Prevent**
- Empty sections when data exists
- Partial hydration
- Mismatch with summary rail

---

## 7. UI / Cosmetic (Non-Blocking)

### Alignment & Consistency
- Left rail spacing
- Empty state messaging
- Section headers

---

### Edit Button Visibility
**Rules**
- Visible only when survey is editable.
- Hidden everywhere else.

---

## 8. Technical Hygiene

### Duplicate Functions
**Action**
- Remove duplicated `render_bonus_survey_targeting_get`.

---

### Field Normalization
**Problem**
- Targeting fields differ across:
  - JS
  - Cache
  - Summary

**Action**
- Define canonical targeting schema.

---

### Defensive Logging
**Intent**
- Catch silent cache failures early.

---

### Intentional TODO Markers
**Rule**
- Any deferred logic must be explicitly marked.

---

## Notes

This system prioritizes:
- Auditability
- Predictable state transitions
- Admin trust
- Minimal “magic”

When in doubt:
> Make the system boring, explicit, and honest.
