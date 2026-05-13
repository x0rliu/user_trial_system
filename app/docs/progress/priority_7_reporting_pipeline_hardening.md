# Priority 7 — Reporting Pipeline Hardening Checkpoint

## Scope

Priority 7 focused on hardening the current wired reporting paths:

- Historical reporting
- BSC / Bonus Survey reporting

Product Trial reporting was intentionally not expanded in this pass. PT should follow the stable Historical + BSC patterns later, with PT-specific additions for participant attribution, survey completion credit, answer quality, and user points.

## Confirmed Current Meaning of "Verified"

For this project, "verified" means:

- Code compiled.
- Server/main smoke path did not immediately fail.
- The app was usable enough to continue.

It does **not** mean:

- Fully validated.
- All edge cases covered.
- Production-ready with no future failures possible.

If something fails later, pause at that point and fix it.

## Historical Hardening Completed

### Transaction Handling

Historical CSV ingestion now commits or rolls back the core dataset rebuild as one DB unit:

- Existing dataset reset
- New dataset row insert
- Historical survey answer inserts

This reduces the risk of partial historical states where the old dataset is removed but the replacement only partially inserts.

### Empty Upload Guards

Historical upload now rejects:

- Empty CSVs
- Header-only CSVs
- Uploads that produce no answer rows

This helps prevent accidental replacement of valid prior data with unusable uploads.

### Metrics Hardening

Historical metrics now:

- Uses dataset completion metadata where available.
- Computes Survey 1 / Survey 2 response counts when dataset naming supports it.
- Uses required datasets for completion/drop-off logic.
- Avoids counting malformed/blank values as strong signals.
- Uses generation version `v3`.

### AI Insight Persistence

Historical AI insight persistence now:

- Uses cursor-safe DB helpers.
- Replaces AI summary and AI insights together.
- Prevents old AI summaries from stacking up repeatedly.
- Preserves prior AI output if a new generation produces no usable saved insights.
- Closes DB connections consistently.

### Upload Handler Hardening

Historical upload handling now:

- Preserves `context_id` on upload error redirects when available.
- Uses one redirect helper for upload errors.
- Reads uploaded file bytes once and reuses them for validation and ingestion.
- Keeps duplicate dataset behavior unchanged for now.

## BSC / Bonus Survey Hardening Completed

### Feedback-first Result Ingestion

BSC / Bonus Survey result ingestion now supports feedback-first behavior:

- Token match = high-confidence attribution.
- Email match = medium-confidence attribution.
- Missing/unmatched identity still ingests valid feedback.
- Recruiting remains strict and is not part of this feedback-first behavior.

### Attribution Tracking

Result uploads now track attribution state:

- Matched by token
- Matched by email
- Anonymous
- Unmatched
- Needs review

This separates "is the feedback usable?" from "can we confidently attribute it to a known user?"

### Upload Transaction Handling

BSC / Bonus result upload rebuild now commits or rolls back as one DB unit:

- Reset completion state
- Delete old interpreted answers
- Mark participation attribution/completion
- Create upload-only participation rows
- Insert answer rows

This reduces the risk of split-brain report state.

### Empty Upload Guards

BSC / Bonus result upload now rejects:

- Header-only uploads
- Uploads with no respondent rows
- Uploads with no survey question columns

This helps prevent invalid uploads from wiping interpreted report data.

### Analysis Failure States

BSC / Bonus report generation now:

- Redirects with explicit analysis status or error codes.
- Avoids 500s for common generation failures.
- Does not replace existing saved report data when generation fails.
- Validates AI report shape before saving.
- Shows visible page feedback for generation success/failure.

### Payload Fallback Hardening

BSC / Bonus analysis payloads now:

- Return a consistent empty payload shape.
- Exclude fully blank uploaded responses from analysis-ready response counts.
- Avoid counting blank answer cells as valid question responses.
- Use safer attribution summary defaults.

### Saved Report Render Safety

BSC / Bonus saved report rendering now:

- Warns when saved report data cannot be loaded safely.
- Treats malformed saved report subfields as empty.
- Keeps regeneration available as a recovery path.
- Avoids page-level failure from corrupted saved report JSON.

## DB Schema / Dump Check

The refreshed DB dump includes the expected feedback-first attribution fields on:

- `bonus_survey_participation`
- `survey_distribution`
- `survey_upload_audit`

The refreshed DB dump also includes Historical tables used by the hardened reporting path:

- `historical_datasets`
- `historical_survey_answers`
- `historical_trial_metrics`
- `historical_insight_runs`
- `historical_trial_insights`

## What Was Not Fully Validated

The following still need normal usage/testing over time:

- Real BSC uploads across several real survey files.
- Real Historical uploads across several legacy survey files.
- AI report generation reliability across weak/odd datasets.
- Structure drift warnings on edited survey structures.
- Corrupted saved report warning behavior using intentionally damaged DB rows.
- Header-only upload failure behavior on test-only contexts/surveys.
- Duplicate historical dataset behavior, which is still intentionally blocked at the handler level.

## Known Deferred Cleanup

- Historical page HTML remains large and should eventually be split into smaller render helpers.
- Some Historical display logic still lives directly inside `app/handlers/historical.py`.
- PT reporting should not be independently patched yet; it should follow BSC + Historical patterns later.
- BSC and Historical display polish can wait until reporting behavior is stable.
- More formal automated tests do not exist yet.

## Recommended Next Priority

Move to:

```text
Priority 8 — Historical pattern comparison