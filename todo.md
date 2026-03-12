— Define approval states (pending_approval / needs_changes / approved / rejected)
— Admin pending-approval list view
— Admin survey review page (read-only)
— Admin approve action
— Admin reject action (with reason)
— Admin request-changes action
— Persist approval decision (status, reviewer, timestamp)
— Notify creator on approval decision
— Unlock draft on needs_changes
— Move survey to Active on approval

— Active surveys left-rail section
— Active survey read-only detail view

— Wire approval → Active state transition
— Wire approval → notification delivery

— Normalize empty-state UI across Drafting / Pending / Active
— Improve submitted confirmation messaging
— Disable submit buttons post-submit (visual lock)

— Consolidate left-rail rendering logic
— Remove duplicated bonus survey handlers
— Normalize targeting field names (JS ↔ cache ↔ summary)
— Remove legacy / dead bonus survey code paths

— Define Direct Invite distribution model
— UI for Direct Invite email input
— Persist distribution config

— Admin audit trail (future)
— Re-approval flow after edits (future)
— Improve dropdown positioning so menus align to the trigger by default and only clamp to the right viewport edge when they would overflow.