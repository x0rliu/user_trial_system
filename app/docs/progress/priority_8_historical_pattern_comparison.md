# Priority 8 — Historical Pattern Comparison Design Checkpoint

## Scope

Priority 8 turns historical trial data into reusable comparison context.

The goal is not yet to generate recommendations. The goal is to define what the system can safely compare using existing DB-backed historical data.

This priority should answer:

- What past trials are comparable to this trial?
- What patterns appeared across similar trials?
- What metrics differ meaningfully?
- What themes or insights repeat?
- What historical questions should inform future survey/question design?

## Guardrails

### DB Is Source of Truth

Historical comparison must use persisted data from DB tables, not page HTML or inferred UI state.

Primary tables:

- `historical_trial_contexts`
- `historical_datasets`
- `historical_survey_answers`
- `historical_trial_metrics`
- `historical_insight_runs`
- `historical_trial_insights`
- `products`

### No Guessing

If a field is missing, null, or not reliable enough to compare, the comparison result should say so.

Examples:

- Unknown product type should not be inferred from product name.
- Missing survey 1 / survey 2 counts should stay null.
- Missing metrics should not be filled with estimated values.
- Weak historical matches should be labeled as weak.

### Comparison Is Not Recommendation Yet

Priority 8 is comparison and pattern retrieval.

Recommendation logic belongs later:

```text
Priority 10 — Recommendation layer

# Priority 8A — Product Taxonomy Foundation

## Why This Comes Before Historical Comparison

Historical comparison depends on knowing what each product actually is.

Before the system can say:

```text
Compare this trial against similar historical trials.