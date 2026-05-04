# UTS AI Map

This document explains where AI enters the User Trial System, what data AI receives, what AI produces, where outputs are stored, and what guardrails keep AI from becoming hidden or untraceable system logic.

Purpose:
- Make AI usage explainable.
- Separate deterministic system logic from AI interpretation.
- Prevent AI from becoming shadow state.
- Clarify what AI is allowed to read and write.
- Support IT/security review by documenting AI boundaries.
- Reduce “magic app” risk by showing where AI is helpful versus authoritative.

This document complements:

- `README.md` — documentation entry point
- `route_map.md` — route-by-route request map
- `workflow_map.md` — user journey and workflow map
- `data_map.md` — source-of-truth and persistence map
- `changelog.md` — session-by-session engineering history

---

# Core AI Rule

AI is an assistant layer, not the system of record.

AI may help with:

- Summarizing
- Classifying
- Naming
- Structuring
- Theming
- Explaining
- Comparing
- Recommending

AI must not be the sole source of truth for:

- User identity
- User permissions
- Eligibility
- Trial status
- NDA status
- Survey completion status
- Approval status
- Participant selection state
- Legal version state
- Shipping state
- Notification read/dismissed state
- Any persisted workflow transition

The database owns state.

AI output becomes usable system data only after it is explicitly written to the database or stored report record.

---

# AI Architecture Pattern

AI should follow this lifecycle:

```text
Database / uploaded data
  → deterministic payload builder
  → AI prompt
  → AI response
  → validation / parsing
  → database write
  → GET route renders stored output
```

AI should not follow this pattern:

```text
GET route
  → call AI live
  → render whatever AI says
```

That is not resumable, not auditable, and not stable.

---

# Current AI Service Boundary

## Shared AI Service

Known AI calls should go through a shared service layer, currently expected to be centered around:

```text
app/services/ai_service.py
```

Expected role:

| Responsibility | Notes |
|---|---|
| Centralize AI calls | Avoid scattered direct API calls |
| Accept prompt/system prompt/model options | Keeps AI behavior explicit |
| Return raw or structured response | Caller owns validation/parsing |
| Use configured internal AI endpoint/token flow | Avoid hardcoded credentials in handlers |

## Token / Authentication Boundary

AI credentials and access tokens should be handled by service/config utilities, not route handlers.

Expected rule:

```text
main.py
  → should not know AI credentials

handlers/services
  → may request AI work through ai_service

ai_service/token_manager
  → handles endpoint/token mechanics
```

## Important Rule

Route handlers should not directly construct hidden AI behavior.

A route may trigger an AI workflow, but the workflow should be visible through named handlers/services.

---

# Where AI Should Live

| Layer | AI Allowed? | Notes |
|---|---:|---|
| `app/main.py` | No direct AI logic | Routing only |
| `app/handlers/*` | Limited orchestration | May call named AI services |
| `app/services/*` | Yes | Preferred place for AI workflow logic |
| `app/db/*` | No AI calls | DB access only |
| `app/templates/*` | No AI calls | Display only |
| `app/static/*` | No AI calls | Frontend behavior only |

---

# AI Workflow 1 — Bonus Survey Structure Generation

## Purpose

Help convert uploaded bonus survey questions into a usable structure for reporting.

AI may suggest:

- Section groupings
- Section names
- Which questions belong together
- Possible profile/demographic questions
- Questions that should be ignored

## Trigger

Likely route:

```text
POST /surveys/bonus/structure/generate
```

Main wrapper:

```text
handle_bonus_survey_structure_generate_post()
```

## Input Data

AI should receive only deterministic payloads derived from stored survey data.

Expected input:

| Input | Source |
|---|---|
| Bonus survey ID | Database / route POST data |
| Question text | Database |
| Question hash | Database |
| Question order | Database |
| Existing structure, if any | Database |
| Survey metadata | Database |

## Output Data

Expected AI output:

| Output | Stored? | Notes |
|---|---:|---|
| Section suggestions | Yes | Should become DB structure rows |
| Section names | Yes | Stored as section labels/keys |
| Question-to-section mapping | Yes | Stored in structure table |
| Profile/ignored recommendations | Yes/optional | Depending on current schema |

## Source of Truth After AI

The stored structure is the source of truth.

AI should not need to rerun for the structure page to render.

## Guardrails

- Repeated question text must be disambiguated by question hash and order.
- AI should not rely on question text alone.
- AI should not invent sections unrelated to the uploaded questions.
- Manual user edits should override AI suggestions.
- Locked structure rows should not be silently overwritten.

---

# AI Workflow 2 — Bonus Survey Profile Classification

## Purpose

Help identify which uploaded survey questions are profile or demographic questions instead of survey-result questions.

Examples:

```text
Age
Gender
Country
Product usage frequency
Product ownership
Support type
```

## Trigger

Likely route:

```text
POST /surveys/bonus/structure/classify-profile
```

Main wrapper:

```text
handle_bonus_survey_structure_classify_profile_post()
```

## Input Data

| Input | Source |
|---|---|
| Uploaded question list | Database |
| Question hash/order | Database |
| Existing structure | Database |
| Survey context | Database |

## Output Data

| Output | Stored? | Notes |
|---|---:|---|
| Profile question classification | Yes | Stored in survey structure |
| Ignored/non-analysis classification | Yes/optional | Stored if supported |
| Section question classification | Yes | Stored if question remains analytical |

## Guardrails

- Profile classification must not expose UTS database PII to untrusted survey viewers.
- BSC-facing views should use survey-provided demographic/profile data, not internal user database PII.
- AI should only classify questions; it should not infer participant demographics from unrelated answers.

---

# AI Workflow 3 — Bonus Survey Analysis

## Purpose

Generate structured insights from uploaded bonus survey results.

AI may assist with:

- Summarizing qualitative feedback
- Identifying recurring themes
- Highlighting positive/negative signals
- Extracting representative quotes
- Explaining section-level findings
- Producing segment-level observations

## Trigger

Likely route:

```text
POST /surveys/bonus/analyze...
```

Main wrapper:

```text
handle_bonus_survey_analyze_post()
```

## Input Data

AI should receive a structured payload built from database records.

Expected input:

| Input | Source |
|---|---|
| Bonus survey metadata | Database |
| Saved question structure | Database |
| Uploaded answers | Database |
| Quantitative scores | Deterministic calculation |
| Qualitative responses | Database |
| Segment views | Deterministic segment builder |
| Survey-only demographics | Uploaded survey data |

## Output Data

Expected AI output:

| Output | Stored? | Notes |
|---|---:|---|
| Section summaries | Yes | Stored report/insight output |
| Themes | Yes | Stored in report JSON or insight table |
| Quotes/evidence | Yes | Must come from actual uploaded answers |
| Cross-segment observations | Yes | Should use deterministic segment payload |
| Overall insight narrative | Yes | Stored, not regenerated on GET |

## Source of Truth After AI

Stored report output is the source of truth for rendering.

GET pages should render the stored report instead of calling AI live.

## Guardrails

AI must not invent evidence.

Every insight should be supportable by:

- Stored survey answer rows
- Quantitative result calculations
- Actual user quotes
- Explicit segment payloads

AI should not create participant segments independently. Segments should be built by deterministic system logic and passed to AI.

## BSC Privacy Rule

BSC is not a trusted internal actor.

For BSC-facing bonus survey analysis:

| Allowed | Not Allowed |
|---|---|
| Survey-provided demographic/profile answers | Internal UTS user database PII |
| Aggregated participant counts | Full user identity records |
| Survey response quotes without internal identity | User table joins exposing private profile data |

---

# AI Workflow 4 — Historical Section Naming

## Purpose

Generate readable section names for historical survey data.

Historical surveys may have repeated generic follow-up questions such as:

```text
Can you elaborate?
```

AI can help name sections based on nearby quantitative/categorical questions and qualitative follow-ups.

## Trigger

Route:

```text
POST /historical/generate-section-names
```

Main wrapper:

```text
handle_generate_section_names_post()
```

## Input Data

| Input | Source |
|---|---|
| Historical context ID | Database |
| Dataset ID | Database |
| Ordered question rows | Database |
| Question positions | Database |
| Question hashes | Database |
| Existing generated names | Database if present |

## Output Data

| Output | Stored? | Notes |
|---|---:|---|
| Section names | Yes | Stored for report rendering |
| Section grouping labels | Yes | Stored or associated with section rows |

## Guardrails

- Preserve question order.
- Do not merge repeated follow-up questions across unrelated sections.
- Do not name sections based on unsupported assumptions.
- User should be able to override/lock generated names later if supported.

---

# AI Workflow 5 — Historical Section Summaries

## Purpose

Summarize qualitative historical feedback by section.

## Trigger

Route:

```text
POST /historical/generate-section-summaries
```

Main wrapper:

```text
handle_generate_section_summaries_post()
```

## Input Data

| Input | Source |
|---|---|
| Historical context | Database |
| Historical dataset | Database |
| Section structure/names | Database |
| Survey answers | Database |
| Qualitative responses | Database |
| Quantitative/categorical context | Database-derived |

## Output Data

| Output | Stored? | Notes |
|---|---:|---|
| Section summary | Yes | Stored summary text |
| Key themes | Yes/optional | Stored in insight/report structure |
| Supporting examples | Yes/optional | Should come from actual responses |

## Guardrails

- Summaries must be grounded in stored historical answers.
- AI should not overstate one-off comments as broad trends.
- Repeated question text requires position/hash context.
- Generated summaries should be stored and reused.

---

# AI Workflow 6 — Historical Insights

## Purpose

Generate broader insights from historical trial data.

This may include:

- Strengths
- Weaknesses
- Opportunities
- Threats
- Recurring patterns
- Product/category observations
- Possible implications for future trials

## Trigger

Route:

```text
POST /historical/generate-insights
```

Main wrapper:

```text
handle_generate_insights_post()
```

## Input Data

| Input | Source |
|---|---|
| Historical context | Database |
| Dataset metadata | Database |
| Stored answers | Database |
| Generated section names | Database |
| Generated summaries | Database |
| Quantitative aggregates | Deterministic calculations |
| Product metadata | Database |

## Output Data

| Output | Stored? | Notes |
|---|---:|---|
| Insight records | Yes | Stored in historical insight tables |
| Insight run metadata | Yes | Used for audit/rerun tracking |
| SWOT-style summaries | Yes/optional | Stored report output |
| Evidence/quotes | Yes/optional | Must come from stored answers |

## Guardrails

- AI should distinguish repeated signals from isolated comments.
- AI should not treat old historical data as current product truth without context.
- AI should not invent product outcomes not present in the dataset.
- Generated insight should be tied to an insight run or context record.

---

# AI Workflow 7 — Future Historical Pattern Comparison

## Purpose

Compare newly uploaded or current UTS trial results against prior historical trials.

This is planned/future work.

Potential AI role:

- Identify recurring issues across products
- Compare product type patterns
- Highlight whether a new issue is novel or previously observed
- Explain whether a current trial validates or contradicts past findings

## Expected Input Data

| Input | Source |
|---|---|
| Current trial structured results | Database |
| Historical trial structured results | Database |
| Product metadata | Database |
| Product type/category | Database |
| Business group | Database |
| Survey section mappings | Database |
| Quantitative metrics | Deterministic calculation |

## Expected Output Data

| Output | Stored? | Notes |
|---|---:|---|
| Pattern comparison | Yes | Should be stored as report artifact |
| Similar historical findings | Yes | Should reference source trial/context |
| Difference/novelty assessment | Yes | Must be evidence-backed |
| Recommendation signals | Yes/optional | Should be constraint-aware |

## Guardrails

- AI must cite which internal dataset/trial supports a comparison.
- AI should not compare unlike products without stating limitations.
- AI should separate observed pattern from recommendation.
- AI should not become the source of raw historical truth.

---

# AI Workflow 8 — Future Constraint Capture

## Purpose

Capture constraints that shape recommendations.

This is planned/future work.

Examples:

- Budget constraints
- Timeline constraints
- Region/country constraints
- Target user constraints
- Manufacturing constraints
- Feature priority constraints
- Product tier/price band constraints

## Expected AI Role

AI may help translate freeform constraints into structured fields.

Example:

```text
"We only have budget for 10 users but need confidence before mass-market launch."
```

AI may help structure this as:

```text
Budget: low
Target confidence need: high
Trial size constraint: 10 users
Recommendation mode: maximize learning per participant
```

## Expected Output

| Output | Stored? | Notes |
|---|---:|---|
| Structured constraints | Yes | Database should own final constraint state |
| Constraint summary | Yes/optional | Human-readable explanation |
| Missing constraint questions | Yes/optional | Suggested follow-up questions |

## Guardrails

- AI may suggest structured constraints, but user/system confirmation should decide what persists.
- Constraints should become explicit database fields or records.
- Recommendations should reference stored constraints, not hidden prompt context.

---

# AI Workflow 9 — Future Recommendation Layer

## Purpose

Suggest what Product Teams should do based on trial evidence, historical comparisons, and constraints.

This is planned/future work and is one of the highest-value areas of UTS.

Potential recommendation shape:

```text
Given your constraints, this option is likely better because...
If you do X, you are likely to get Y.
If you do not fix Z, the likely risk is...
```

## Expected Input Data

| Input | Source |
|---|---|
| Current trial findings | Database |
| Historical trial patterns | Database |
| Product metadata | Database |
| Constraints | Database |
| Quantitative results | Deterministic calculation |
| Qualitative evidence | Database |
| Target segment/profile data | Database/survey data depending on audience |
| Business context | Database or explicit user input |

## Expected Output Data

| Output | Stored? | Notes |
|---|---:|---|
| Recommendation | Yes | Should be stored |
| Confidence level | Yes | Should be explainable |
| Evidence list | Yes | Must cite internal findings |
| Trade-off explanation | Yes | Should reference constraints |
| Alternative options | Yes/optional | Useful for decision support |

## Guardrails

AI recommendations must distinguish:

| Type | Meaning |
|---|---|
| Observation | What users said/did |
| Pattern | What appears repeatedly |
| Interpretation | What the pattern likely means |
| Recommendation | What action may be best |
| Risk | What may happen if ignored |

AI should never present recommendation as certainty.

---

# Prompting Guardrails

All AI prompts should enforce:

## Evidence Grounding

AI should only use supplied data.

Suggested prompt language:

```text
Use only the data provided in this payload.
Do not invent facts, quotes, participants, segments, products, or conclusions.
If evidence is insufficient, say so.
```

## Quote Integrity

When using quotes:

```text
Only quote text that appears in the provided responses.
Do not paraphrase as quotation.
Do not combine multiple users into one quote.
```

## Frequency Awareness

AI should avoid treating one-off comments as broad trends.

Suggested distinction:

| Signal Type | Meaning |
|---|---|
| Repeated theme | Multiple users mention similar issue |
| Minority signal | Some users mention issue |
| One-off | Single isolated comment |
| Strong outlier | Rare but potentially high-impact comment |

## Uncertainty

AI should explicitly state when:

- Sample size is low
- Evidence is mixed
- Feedback is anecdotal
- Segments are too small
- Data is missing
- The question wording may have biased responses

## No Hidden Segmentation

AI should not invent user segments.

Segments must be created by deterministic system logic and passed to AI explicitly.

---

# AI Output Storage Rules

## AI Output Must Be Stored

If AI output affects reporting, it should be stored.

Examples:

| Output | Store? |
|---|---:|
| Bonus survey report summary | Yes |
| Bonus section insight | Yes |
| Historical section name | Yes |
| Historical section summary | Yes |
| Historical insight | Yes |
| Future recommendation | Yes |
| Temporary chat explanation | Optional/no |

## GET Routes Should Render Stored AI Output

Correct:

```text
GET report page
  → read stored report/insights from database
  → render HTML
```

Incorrect:

```text
GET report page
  → call AI
  → render live AI response
```

## Regeneration Should Be Explicit

If AI output needs to be updated, use an explicit POST action:

```text
POST regenerate insights
  → call AI
  → store new output
  → redirect to GET report page
```

---

# AI Output Review Status

Some AI output may need review/approval before being treated as final.

Potential statuses:

| Status | Meaning |
|---|---|
| generated | AI created output |
| reviewed | Human reviewed output |
| approved | Human accepted output |
| stale | Underlying data changed after generation |
| superseded | Newer AI run replaced this output |
| failed | AI generation failed |

This may be useful for future report publishing workflows.

---

# Staleness Rules

AI output may become stale when underlying data changes.

Examples:

| Data Change | Stale Output |
|---|---|
| New survey upload | Existing survey analysis |
| Changed question structure | Existing section summaries |
| Deleted/renamed section | Existing report structure |
| New historical dataset | Aggregate/historical comparison |
| Updated constraints | Recommendation output |
| New trial data added | Product type / brand-level report |

Future system behavior should mark generated reports as stale instead of silently treating them as current.

---

# AI Failure Handling

AI workflows should fail safely.

If an AI call fails:

| Workflow | Safe Behavior |
|---|---|
| Structure generation | Redirect back with error; preserve existing structure |
| Bonus analysis | Do not overwrite existing report |
| Historical section names | Preserve existing names |
| Historical summaries | Preserve existing summaries |
| Historical insights | Preserve existing insights |
| Recommendations | Do not publish incomplete recommendation |

Important rule:

```text
Failed AI generation should not destroy previous valid output.
```

---

# AI and Privacy

## Internal vs External Data

AI payloads should be scoped to the user/viewer’s permission level.

| Audience | AI Should Receive |
|---|---|
| Admin / UT Lead | System-internal trial data as permitted |
| Product Team | Product/trial data relevant to their product |
| BSC / Bonus Survey Creator | Survey-provided data, not internal PII |
| Participant | Only their own permitted data |

## BSC Privacy Boundary

BSC-facing bonus survey analysis must not expose internal UTS user database PII.

Allowed:

- Survey-provided country/gender/age answers
- Aggregated profile counts
- De-identified quotes
- Survey completion counts

Not allowed:

- Internal `user_pool` identity data
- Internal private profile records
- Email addresses
- Full names
- User IDs unless explicitly safe/internal
- Any hidden system demographic data not collected by the survey

---

# AI and Security

AI prompts should not include:

- API keys
- Access tokens
- Passwords
- Session IDs
- Raw cookies
- Unnecessary PII
- Internal secrets
- Legal private data unless required and authorized

AI responses should not be trusted as executable code.

AI should not generate database mutations directly. The application should parse/validate AI output before storing.

---

# AI and Deterministic Logic

AI should not replace deterministic logic where rules are clear.

Use deterministic logic for:

| Area | Why |
|---|---|
| Eligibility checks | Must be predictable |
| Permission checks | Security-sensitive |
| NDA gating | Legal/compliance-sensitive |
| Survey completion status | DB-derived |
| Notification unread count | DB-derived |
| Routing decisions | Must be traceable |
| Data parsing | Should be reproducible |
| Quantitative averages | Math, not AI |
| User selection final state | Must be auditable |

Use AI for:

| Area | Why |
|---|---|
| Summarizing open-ended comments | Language-heavy |
| Naming sections | Judgment/interpretation |
| Finding themes | Pattern recognition |
| Explaining trade-offs | Decision support |
| Drafting recommendations | Synthesis |
| Comparing qualitative findings | Interpretation |

---

# AI Input / Output Contract

Every AI workflow should eventually be documentable in this form:

```text
Workflow:
Route:
Handler/service:
Trigger:
Input source:
Prompt owner:
Model/service:
Output format:
Validation:
Storage destination:
Rendered by:
Failure behavior:
Staleness behavior:
```

## Example Contract — Bonus Survey Analysis

| Field | Value |
|---|---|
| Workflow | Bonus survey analysis |
| Route | `POST /surveys/bonus/analyze...` |
| Handler/service | Bonus survey analysis handler/service |
| Trigger | User clicks analyze/regenerate |
| Input source | Stored bonus survey answers and structure |
| Prompt owner | Analysis service |
| Model/service | Shared AI service |
| Output format | Structured JSON/text report |
| Validation | Must include supported section summaries/evidence |
| Storage destination | Bonus survey report/insight table |
| Rendered by | Bonus survey active/report GET route |
| Failure behavior | Redirect with error; do not overwrite valid report |
| Staleness behavior | Mark stale when answers/structure changes |

---

# Known AI-Adjacent Files / Areas to Verify

These should be verified during future code/schema review.

| Area | What to Confirm |
|---|---|
| `app/services/ai_service.py` | Shared AI call behavior |
| Token manager / AI auth | How access tokens are generated and cached |
| Bonus survey structure handler | Exact AI trigger and storage destination |
| Bonus survey analysis handler | Exact report table/JSON structure |
| Historical handlers | Exact generation functions and storage tables |
| Segment builder | Ensure AI consumes deterministic segments |
| Report rendering | Confirm GET pages render stored output only |
| Prompt templates | Confirm prompts include evidence constraints |
| Failure handling | Confirm failed AI does not overwrite valid output |

---

# Current Known AI Risks

## 1. Hallucinated Evidence

Risk:
AI invents quotes, themes, or participant sentiment.

Mitigation:
Require AI to use only provided responses and store evidence with output.

## 2. Segment Drift

Risk:
AI invents demographic or behavioral segments.

Mitigation:
Build segments deterministically and pass them to AI.

## 3. Live GET AI Calls

Risk:
Pages become non-deterministic and slow.

Mitigation:
Only POST should trigger AI generation. GET should render stored output.

## 4. Stale Reports

Risk:
New data enters but old AI report still appears current.

Mitigation:
Mark reports stale when underlying data changes.

## 5. Overweighting Rare Feedback

Risk:
AI makes a dramatic one-off sound like a common issue.

Mitigation:
Require frequency labels and evidence counts.

## 6. Privacy Leakage

Risk:
AI payload includes internal user data for an audience that should not see it.

Mitigation:
Build audience-specific payloads and enforce BSC privacy boundary.

## 7. Prompt Sprawl

Risk:
Prompts are scattered across handlers and become inconsistent.

Mitigation:
Centralize prompts/services by workflow.

---

# Recommended Future Improvements

## 1. AI Run Log

Create a durable AI run log for generated outputs.

Possible fields:

| Field | Purpose |
|---|---|
| run_id | Unique AI generation run |
| workflow_type | Bonus analysis, historical summary, etc. |
| source_object_type | Survey, dataset, report, etc. |
| source_object_id | ID of analyzed object |
| prompt_version | Tracks prompt changes |
| model | Tracks model used |
| input_hash | Detects stale output |
| output_status | generated/failed/stale/etc. |
| created_by | User who triggered generation |
| created_at | Timestamp |
| error_message | Failure audit |

## 2. Prompt Versioning

Prompts should have versions so generated reports can be traced back to the rules used at the time.

Example:

```text
bonus_survey_analysis_prompt_v3
historical_section_summary_prompt_v2
recommendation_layer_prompt_v1
```

## 3. Evidence Schema

Reports should store evidence separately from prose.

Example:

```text
insight
  summary
  confidence
  frequency_label
  supporting_quotes[]
  supporting_question_ids[]
  segment_context
```

## 4. Staleness Detection

Generated outputs should be marked stale when source data changes.

Example:

```text
Survey answers uploaded after report generated
  → report status = stale
```

## 5. Human Review Status

Important AI-generated reports or recommendations may need human approval before publication.

Possible flow:

```text
generated
  → reviewed
  → approved
  → published
```

---

# AI Documentation Status

This file is intentionally high-level.

It does not yet confirm every exact table, prompt, model, or handler name.

Future Priority 5 and Priority 6 work should align this document with the live DB schema and current survey/reporting pipeline.