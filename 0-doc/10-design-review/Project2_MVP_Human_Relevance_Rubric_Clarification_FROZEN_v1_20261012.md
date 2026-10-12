# Project 2 MVP Human Relevance Rubric Clarification FROZEN v1

```text
DATE = 2026-10-12
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

DESIGN_OWNER_DECISION = APPROVED
PARENT_PROTOCOL = MVP_CORE_RETRIEVAL_PROTOCOL_v1
PARENT_TEMPORAL_EVIDENCE_ADDENDUM =
Project2_MVP_Human_Audit_Temporal_Evidence_Addendum_FROZEN_v1_20261010.md

HUMAN_RELEVANCE_SCHEMA =
MVP_RETRIEVAL_RELEVANCE_V1

SEMANTIC_CHANGE =
NO

CALIBRATION_FIRST_PASS_BINARY_REPEAT_QC =
10 / 12 PASS

CALIBRATION_RECONCILED_BINARY_REPEAT_CONSISTENCY =
11 / 12 SUPPORTIVE_ONLY
```

## 1. Purpose

This document freezes the operational wording used to apply the already-frozen Human relevance semantics after Calibration exposed ambiguity in low-displacement and near-static segments.

It does **not** change:

- the five Human relevance labels;
- the Formal binary mapping;
- the Query or Candidate cohorts;
- Top-K;
- Motion representation;
- SigLIP2 representation;
- Retrieval outputs;
- any Final metric or decision gate.

The clarification exists only to make the original meaning of:

> same local robot behavior / interaction pattern

operationally consistent for Final Human Audit.

## 2. Evidence available to the Human reviewer

The Human reviewer may use:

- complete within-segment temporal GIF evidence;
- START / MIDDLE / END / GRIPPER_EVENT keyframes;
- segment duration;
- gripper start/end/transition;
- coarse robot-motion summary.

The reviewer must not see:

- Retrieval method;
- method-specific similarity;
- method-specific rank;
- hidden-repeat identity.

The complete temporal GIF is **Human Audit evidence only**.

It remains forbidden as input to:

- SigLIP2;
- Motion representation;
- FAISS;
- VLM;
- any other Retrieval representation.

Therefore:

```text
MODEL REPRESENTATION EVIDENCE
!=
HUMAN GT EVIDENCE
```

Human GT may intentionally use richer temporal evidence than the model representation.

## 3. Primary relevance principle

The primary question is:

> Do Query and Candidate express the same local robot behavior / interaction pattern, such that the Candidate is a reasonable same-behavior demonstration neighbor for the Query?

The reviewer should prioritize:

1. **Interaction phase** — whether the two segments occupy the same local phase of the manipulation.
2. **Gripper interaction state** — OPEN/CLOSED state, transition behavior, and whether grasp/release interaction differs.
3. **Temporal motion pattern** — approach, retreat, lift, lower, lateral reposition, near-static hold, or micro-adjustment behavior.
4. **Absolute spatial / visual proximity** — supporting evidence only.

Absolute pose or scene-location similarity is **not sufficient** for `RELEVANT`.

Low displacement is **not sufficient** for `UNSURE`.

## 4. Frozen operational label rules

### 4.1 RELEVANT

Use `RELEVANT` when Query and Candidate express the same local behavior / interaction pattern.

Examples include:

- both are the same kind of pre-grasp micro-adjustment;
- both are the same kind of near-static hold at the same interaction phase;
- both share the same grasp/lift/reposition behavior even if exact displacement magnitude differs;
- both are behaviorally compatible demonstration neighbors when viewed over the full segment.

For low-motion segments, small displacement does not prevent `RELEVANT` if the temporal interaction pattern is still the same.

### 4.2 PARTIAL

Use `PARTIAL` when some motion or visual state is shared, but a key behavior / interaction component differs.

Typical cases:

- similar spatial position but different manipulation phase;
- one segment is approach / micro-adjustment while the other has entered grasp interaction;
- similar local motion but materially different gripper interaction;
- partial temporal overlap without same-behavior equivalence.

`PARTIAL` remains NON_RELEVANT for strict Formal P@5.

### 4.3 NOT_RELEVANT

Use `NOT_RELEVANT` when the local behaviors are clearly different.

Typical cases:

- approach versus retreat;
- pre-grasp versus post-grasp lift / departure;
- grasp versus release;
- different interaction phase despite similar absolute position;
- temporally incompatible local behavior.

### 4.4 UNSURE

Use `UNSURE` only when the reviewer cannot make a stable judgment **after using all allowed Human Audit evidence**, including the full within-segment GIF.

Do not use `UNSURE` merely because:

- displacement is small;
- START/MIDDLE/END keyframes look similar;
- the robot is near the same object location.

If the full temporal evidence resolves the interaction pattern, choose `RELEVANT`, `PARTIAL`, or `NOT_RELEVANT`.

### 4.5 BAD_SEGMENT

Use `BAD_SEGMENT` only when Query or Candidate segmentation itself prevents reliable behavior comparison.

Examples:

- the segment cuts through the critical behavior so the local action cannot be interpreted;
- the segment boundaries leave no coherent behavior unit;
- segmentation artifact, rather than genuine ambiguity, prevents judgment.

Do not use `BAD_SEGMENT` simply because the behavior is difficult to classify semantically.

## 5. Micro-motion clarification

For near-static / low-displacement segments:

```text
same interaction phase
AND
compatible gripper interaction
AND
same local temporal motion pattern
→ RELEVANT
```

If only the spatial / visual state is shared but the key interaction behavior differs:

```text
→ PARTIAL
```

If the full temporal behavior is clearly different:

```text
→ NOT_RELEVANT
```

If all allowed evidence still cannot support a stable judgment:

```text
→ UNSURE
```

## 6. Formal mapping remains unchanged

For strict Formal Precision@5:

```text
RELEVANT = 1

PARTIAL = 0
NOT_RELEVANT = 0
BAD_SEGMENT(candidate) = 0
UNSURE = 0
```

A query segment that is itself unusable remains:

```text
QUERY_BAD_SEGMENT = YES
```

No metric or decision threshold is changed by this clarification.

## 7. Calibration evidence supporting the freeze

Calibration first pass:

```text
95 audit items
31 UNSURE
binary hidden-repeat agreement = 10 / 12 PASS
```

Focused re-audit of the 31 first-pass UNSURE items using the already-approved full-segment temporal evidence:

```text
24 RELEVANT
1 PARTIAL
6 NOT_RELEVANT
0 UNSURE
```

Reconciled descriptive consistency:

```text
67 RELEVANT
8 PARTIAL
20 NOT_RELEVANT
0 UNSURE
binary repeat consistency = 11 / 12
```

The reconciled 11/12 value is supportive only because the re-audit was targeted to first-pass UNSURE items. The Formal Calibration repeat gate remains the original 10/12 PASS.

## 8. Final freeze boundary

From this point forward, Final Human Audit must use this wording without further performance-driven modification.

After Final labels are observed, do not change:

- relevance semantics;
- operational wording;
- model representation;
- Retrieval settings;
- Top-K;
- Query/Candidate cohorts;

and then reuse the same Final labels as if they were untouched Formal evidence.

```text
HUMAN_RELEVANCE_RUBRIC =
FROZEN_v1

CALIBRATION_RUBRIC_STABILITY =
PASS

FINAL_RETRIEVAL_AUTHORIZED =
YES

FINAL_HUMAN_AUDIT_RUBRIC =
LOCKED_TO_FROZEN_v1
```
