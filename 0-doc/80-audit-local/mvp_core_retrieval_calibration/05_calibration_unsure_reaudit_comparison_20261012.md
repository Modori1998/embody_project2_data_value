# Project 2 MVP Calibration UNSURE Re-audit Comparison Result

```text
DATE = 2026-10-12
STATUS = CALIBRATION_RUBRIC_CLARIFICATION_RESULT
SOURCE_FIRST_PASS = 01_calibration_human_audit_pairs_filled_20261011.csv
SOURCE_REAUDIT = 03_calibration_unsure_reaudit_filled_20261012.csv
SOURCE_REAUDIT_MANIFEST = 02_calibration_unsure_reaudit_manifest_20261012.csv
RECONCILED_OUTPUT = 04_calibration_human_audit_reconciled_20261012.csv
RETRIEVAL_RERUN = NO
FORMAL_CORE_RESULT = NO
```

## 1. Integrity checks

- First-pass audit items: **95**
- First-pass `UNSURE` items selected for re-audit: **31**
- Re-audit returned items: **31 / 31**
- Re-audit item IDs and Query/Candidate segment IDs match the frozen re-audit manifest: **PASS**
- Retrieval, Top-K, query selection, candidate population, and audit item order were not changed.
- Re-audit used the same existing temporal Human Audit evidence; it is a Calibration rubric-clarification pass only.

## 2. Label distribution

### Item level

| Stage | RELEVANT | PARTIAL | NOT_RELEVANT | UNSURE | BAD_SEGMENT |
|---|---:|---:|---:|---:|---:|
| First pass, 95 items | 43 | 7 | 14 | 31 | 0 |
| Re-audit subset, 31 items | 24 | 1 | 6 | 0 | 0 |
| Reconciled, 95 items | 67 | 8 | 20 | 0 | 0 |

The 31 first-pass `UNSURE` items were resolved to:

- **24 RELEVANT**
- **1 PARTIAL**
- **6 NOT_RELEVANT**
- **0 UNSURE**

Therefore the re-audit did not merely relabel uncertainty as positive: it separated ambiguous low-motion cases into both relevant and non-relevant outcomes.

### Unique Query-Candidate pair level

The 95 audit items contain 83 unique pairs plus 12 hidden repeat copies.

| Stage | Unique pairs | RELEVANT | PARTIAL | NOT_RELEVANT | UNSURE |
|---|---:|---:|---:|---:|---:|
| First pass | 83 | 39 | 4 | 13 | 27 |
| Reconciled | 83 | 60 | 5 | 18 | 0 |

Within the re-audited subset there are 28 unique pairs; using the first occurrence for descriptive counting gives 22 RELEVANT, 1 PARTIAL, and 5 NOT_RELEVANT.

## 3. Per-query change

Counts are `RELEVANT / PARTIAL / NOT_RELEVANT / UNSURE`.

| Query | First pass | Reconciled |
|---|---:|---:|
| `demo_200-S0009` | 4/1/0/5 | 6/1/3/0 |
| `demo_5-S0003` | 9/0/0/0 | 9/0/0/0 |
| `demo_189-S0004` | 8/0/0/0 | 8/0/0/0 |
| `demo_215-S0003` | 3/2/4/4 | 6/3/4/0 |
| `demo_65-S0004` | 2/0/2/7 | 9/0/2/0 |
| `demo_148-S0005` | 7/0/1/1 | 8/0/1/0 |
| `demo_249-S0001` | 0/0/1/11 | 9/0/3/0 |
| `demo_297-S0002` | 6/4/3/0 | 6/4/3/0 |
| `demo_294-S0003` | 4/0/3/3 | 6/0/4/0 |

The largest clarification effects are concentrated in the previously ambiguous low-motion/no-transition queries:

- `demo_249-S0001`: 0/0/1/11 → 9/0/3/0 at audit-item level.
- `demo_65-S0004`: 2/0/2/7 → 9/0/2/0.
- `demo_200-S0009`: 4/1/0/5 → 6/1/3/0.

This supports the diagnosis that the first-pass uncertainty was primarily an evidence/rubric interpretation problem for small-displacement local behavior, not a general inability to perform the audit.

## 4. Hidden-repeat stability

Frozen Calibration QC uses a binary mapping:

```text
RELEVANT
vs
NON_RELEVANT = PARTIAL / NOT_RELEVANT / BAD_SEGMENT / UNSURE
```

Protocol threshold: **>= 10 / 12** binary repeat agreement.

First pass:

- Exact five-class agreement: **7 / 12**
- Frozen binary agreement: **10 / 12 = PASS**

Reconciled labels after targeted UNSURE re-audit:

- Exact five-class agreement: **8 / 12**
- Binary consistency: **11 / 12**

The reconciled binary consistency is supportive evidence only, not a new independent repeat-QC experiment, because the re-audit subset was selected from first-pass `UNSURE` items rather than re-running all 95 items.

Remaining reconciled label disagreements:

- `demo_215-S0003||demo_142-S0002`: CAL-0005 vs CAL-0023 = NOT_RELEVANT vs PARTIAL (NON_RELEVANT vs NON_RELEVANT)
- `demo_215-S0003||demo_142-S0003`: CAL-0017 vs CAL-0025 = PARTIAL vs RELEVANT (NON_RELEVANT vs RELEVANT)
- `demo_297-S0002||demo_59-S0001`: CAL-0027 vs CAL-0035 = NOT_RELEVANT vs PARTIAL (NON_RELEVANT vs NON_RELEVANT)
- `demo_215-S0003||demo_34-S0002`: CAL-0060 vs CAL-0063 = PARTIAL vs NOT_RELEVANT (NON_RELEVANT vs NON_RELEVANT)

Only one remaining disagreement crosses the frozen binary relevance boundary: `demo_215-S0003 || demo_142-S0003` (`PARTIAL` vs `RELEVANT`).

## 5. Interpretation

### Conclusion A — Temporal evidence resolved the original uncertainty

The first pass had **31 / 95 UNSURE (32.6%)**. After the focused re-audit with the already-approved full-segment GIF evidence, the reconciled set has **0 / 95 UNSURE**.

For the 28 unique pairs represented in the re-audit subset, 22/28 were judged RELEVANT, 5/28 NOT_RELEVANT, and 1/28 PARTIAL. This means the temporal evidence made previously visually ambiguous micro-motion segments distinguishable rather than simply forcing one default label.

### Conclusion B — Three/few keyframes remain a valid model-input constraint, but are insufficient as the sole Human GT evidence

The re-audit result reinforces the intended separation:

- SigLIP2 Retrieval remains restricted to the frozen few-keyframe representation.
- Human relevance GT may use the complete within-segment temporal GIF.
- A pair that looks similar in sparse keyframes but differs in full temporal behavior should be labeled non-relevant by the Human reviewer.

Therefore a model failure on such a pair is a real representation/retrieval failure, not a Human-audit defect.

### Conclusion C — Some apparently “wrong Candidate” cases are expected Retrieval false positives, not re-audit-page corruption

The re-audit item IDs and Query/Candidate IDs exactly match the first-pass rows and the frozen re-audit manifest. The focused page did not substitute candidates.

The 6 item-level NOT_RELEVANT outcomes (5 unique pairs) show that some candidates that looked suspicious during re-audit are legitimately behaviorally wrong neighbors returned by Retrieval. They should remain negative Human GT rather than be corrected or removed from the audit package.

### Conclusion D — Calibration rubric stability is sufficient to proceed to an owner rubric-freeze decision

The original frozen repeat gate already passed at **10/12**. The targeted clarification resolves all first-pass uncertainty, and reconciled binary consistency is **11/12**.

No representation, Retrieval, Top-K, query cohort, or candidate cohort changed. Calibration labels remain non-Formal evidence.

Recommended next state:

```text
HUMAN_RELEVANCE_CALIBRATION = READY_FOR_RUBRIC_FREEZE
FINAL_RETRIEVAL = STILL_BLOCKED
NEXT = OWNER_REVIEW_AND_FREEZE_CALIBRATION_RUBRIC
```

Do not compute Formal P@5 or run Final Retrieval until the clarified Human relevance rubric is explicitly frozen.
