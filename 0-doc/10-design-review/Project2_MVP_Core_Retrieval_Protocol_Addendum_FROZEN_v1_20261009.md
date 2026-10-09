# Project 2 MVP Core Retrieval Protocol Addendum FROZEN v1

```text
DATE = 2026-10-09
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

DESIGN_OWNER_DECISION = APPROVED
PARENT_PROTOCOL = MVP_CORE_RETRIEVAL_PROTOCOL_v1
PARENT_PROTOCOL_DOC =
Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md

ADDENDUM_SCOPE =
QUERY_SEGMENT_SELECTION_DETERMINISM
BLIND_AUDIT_ORDERING
HIDDEN_REPEAT_SELECTION

GIT_BASE_AT_FREEZE =
d360f9d53f70f968aa35421bea77fa5049a643fb
```

## 1. Purpose

This addendum resolves implementation ambiguity discovered before Formal Retrieval execution.

It does not change the scientific intent, representation definitions, Episode Manifest, Top-K, relevance rubric, or success criteria of the parent Frozen Protocol.

The local runtime correctly fail-fast stopped before any Formal M2 materialization, SigLIP2 inference, FAISS retrieval, Human Audit, or P@5 scoring. Therefore no Formal result has been contaminated.

## 2. Query Episode type assignment

For each frozen Calibration or Final Query Episode, first enumerate all eligible Formal segments after M2 materialization.

Partition the Episode's eligible segments into:

```text
TRUE_SET =
segments where gripper_transition_present = TRUE

FALSE_SET =
segments where gripper_transition_present = FALSE
```

If both sets are empty:

```text
STOP_QUERY_EPISODE_HAS_NO_ELIGIBLE_SEGMENT
```

Episode type availability:

```text
TRUE_ONLY  = TRUE_SET non-empty and FALSE_SET empty
FALSE_ONLY = FALSE_SET non-empty and TRUE_SET empty
FLEXIBLE   = both TRUE_SET and FALSE_SET non-empty
```

## 3. Cohort-level balance target

Frozen targets remain:

```text
CALIBRATION_QUERY:
N = 9
TARGET_TRUE = 4
TARGET_FALSE = 5

FINAL_QUERY:
N = 18
TARGET_TRUE = 9
TARGET_FALSE = 9
```

For each cohort compute:

```text
forced_true  = count(TRUE_ONLY)
forced_false = count(FALSE_ONLY)
flexible     = count(FLEXIBLE)
```

The feasible number of TRUE-assigned Episodes is:

```text
TRUE_MIN = forced_true
TRUE_MAX = N - forced_false
```

Choose the realized TRUE count deterministically:

```text
REALIZED_TRUE =
clamp(TARGET_TRUE, TRUE_MIN, TRUE_MAX)

REALIZED_FALSE =
N - REALIZED_TRUE
```

where:

```text
clamp(x, lo, hi) = min(max(x, lo), hi)
```

This is the deterministic fallback when the exact target is not feasible.

No frozen Episode may be substituted to improve the realized balance.

## 4. FLEXIBLE Episode assignment

All FLEXIBLE Episodes in the cohort are ordered by:

```text
SHA256(
  "MVP_CORE_RETRIEVAL_V1|QUERY_EPISODE_ASSIGN|" + episode_id
) ASC,
then episode_id ASC
```

Let:

```text
FLEX_TRUE_N =
REALIZED_TRUE - forced_true
```

Assign:

```text
first FLEX_TRUE_N FLEXIBLE Episodes
→ TRUE

remaining FLEXIBLE Episodes
→ FALSE
```

TRUE_ONLY and FALSE_ONLY Episodes retain their forced assignment.

This fully determines each Query Episode's assigned gripper-transition class.

## 5. Segment selection inside an assigned Episode

After the Episode class is assigned:

```text
assigned TRUE
→ candidate segments = TRUE_SET

assigned FALSE
→ candidate segments = FALSE_SET
```

Select exactly one Formal Query Segment by sorting the assigned candidate segments by:

```text
SHA256(
  "MVP_CORE_RETRIEVAL_V1|QUERY|" + segment_id
) ASC,
then segment_id ASC
```

Select the first segment.

No Motion similarity, Visual similarity, Retrieval outcome, Human label, VLM label, or manual preference may participate.

## 6. Blind pair union

For each Calibration or Final Query Segment:

```text
Motion Top-5
+
SigLIP2 Top-5
→ union by (query_segment_id, candidate_segment_id)
→ remove duplicate pair identity
```

The same pair returned by both methods is reviewed exactly once.

Retrieval method, method-specific rank, and similarity score remain hidden from the reviewer.

## 7. Hidden repeat pair selection

For each audit cohort independently, define:

```text
COHORT =
CALIBRATION
or
FINAL
```

From all unique blind audit pairs in that cohort, rank pairs by:

```text
SHA256(
  "MVP_CORE_RETRIEVAL_V1|HIDDEN_REPEAT|" +
  COHORT + "|" +
  query_segment_id + "|" +
  candidate_segment_id
) ASC,
then query_segment_id ASC,
then candidate_segment_id ASC
```

Take the first:

```text
HIDDEN_REPEAT_N = 12
```

pairs.

If fewer than 12 unique blind pairs exist:

```text
STOP_INSUFFICIENT_UNIQUE_AUDIT_PAIRS_FOR_REPEAT_QC
```

Each selected hidden-repeat pair appears exactly twice in the reviewer package:

```text
copy_index = 0
copy_index = 1
```

All other pairs appear once with:

```text
copy_index = 0
```

The reviewer-visible package must not reveal whether an item is repeated.

## 8. Deterministic blind audit ordering

For each audit item, including repeat copies, compute:

```text
SHA256(
  "MVP_CORE_RETRIEVAL_V1|BLIND_AUDIT_ORDER|" +
  COHORT + "|" +
  query_segment_id + "|" +
  candidate_segment_id + "|" +
  copy_index
)
```

Sort by:

```text
digest ASC,
query_segment_id ASC,
candidate_segment_id ASC,
copy_index ASC
```

This is the complete deterministic shuffle rule.

No runtime randomness is permitted for Formal Human Audit ordering.

## 9. Authority and protected boundaries

This addendum has Frozen authority only for the ambiguity it resolves.

It does not modify:

```text
Frozen 63-Episode Manifest
Motion representation
Visual representation
SigLIP2 checkpoint family
Top-K = 5
Candidate Bank definition
Cross-Episode rule
Human relevance labels
P@5 definition
GO / CONDITIONAL / STOP criteria
Late Fusion = DISABLED in Core v1
```

If this addendum conflicts with an underspecified phrase such as "deterministic fallback" in the parent protocol, this addendum supplies the controlling implementation rule.

Any later change requires a new Design Change Request and a new addendum/protocol version.

## 10. Execution status

```text
CORE_RETRIEVAL_PROTOCOL = FROZEN_v1
CORE_RETRIEVAL_PROTOCOL_ADDENDUM = FROZEN_v1
CORE_RETRIEVAL_MANIFEST = FROZEN_v1
CORE_RETRIEVAL_RUNTIME_PREFLIGHT = PASS

FORMAL_RETRIEVAL_EXECUTED = NO
FORMAL_HUMAN_AUDIT_EXECUTED = NO
P5_COMPUTED = NO

CORE_RETRIEVAL_INFERENCE =
READY_FOR_FORMAL_CORE_RETRIEVAL_EXECUTION

NEXT =
FORMAL_63_EPISODE_MATERIALIZATION_AND_CALIBRATION_RETRIEVAL
```
