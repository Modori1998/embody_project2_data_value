# Project 2 MVP Core Retrieval Protocol FROZEN v1

```text
DATE = 2026-10-08
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

DESIGN_OWNER_FREEZE_DECISION = CONFIRMED
MVP_MODE = RETRIEVAL_FIRST

GIT_BASE_AT_FREEZE =
861594cce2626fd6b6622dbf245bfcc38253d0d9

UPSTREAM_GATES =
MVP_P0A_RGB_INPUT_CONTRACT = CLOSED_PASS
MVP_M2 = CLOSED_PASS
MVP_M2_PRE_RETRIEVAL_HARDENING = CLOSED_PASS

CORE_RETRIEVAL_PROTOCOL =
MVP_CORE_RETRIEVAL_PROTOCOL_v1

CORE_RETRIEVAL_PROTOCOL_FROZEN =
YES

CORE_RETRIEVAL_MANIFEST =
NOT_FROZEN

CORE_RETRIEVAL_INFERENCE =
NOT_ALLOWED_UNTIL_MANIFEST_FREEZE_AND_RUNTIME_PREFLIGHT
```

## 1. Core question

The Core MVP tests one falsifiable question:

> Given the same query segments, the same candidate bank, the same cross-episode exclusion rule, and the same independent Human relevance rubric, can Robot Motion Representation and SigLIP2 Visual Representation retrieve behaviorally relevant robot demonstration segments, and does vision provide independent or complementary value?

Formal Core v1 compares only:

```text
A. Motion-only Retrieval
B. SigLIP2-only Retrieval
```

```text
CORE_V1_LATE_FUSION = DISABLED
```

Late Fusion may be opened only as a separate extension after Core v1 if the frozen result is complementary rather than clearly dominated.

No VLM, DINOv2, Dedup, Long-tail, Coverage, or G3 taxonomy is required for Core v1.

## 2. Episode eligibility and cohort sizes

Retrieval data must exclude:

1. all historical G1 Exploratory / Calibration Seed / Calibration Fresh / Design Diagnostic episodes;
2. all 24 episodes in `G1_P4_EVAL_MANIFEST_v1`.

The exact eligible count must be recomputed from current authoritative artifacts. It must not be hard-coded from chat history.

Formal cohort sizes:

```text
CANDIDATE_BANK_EPISODES = 36
CALIBRATION_QUERY_EPISODES = 9
FINAL_QUERY_EPISODES = 18

TOTAL_SELECTED_EPISODES = 63
```

All three cohorts are episode-disjoint.

### Deterministic episode selection

Eligible episodes are stratified by episode frame count into three duration terciles:

```text
SHORT
MEDIUM
LONG
```

Within each tercile, order episodes by:

```text
SHA256("MVP_CORE_RETRIEVAL_V1|" + episode_id)
```

Select per tercile:

```text
Candidate Bank = 12
Calibration Query = 3
Final Query = 6
```

No episode may be manually substituted after retrieval results are observed.

The selected episode IDs are frozen separately in a Retrieval Manifest before any Formal inference.

## 3. Segment eligibility and query selection

Formal segments must satisfy:

```text
Frozen G1 identity = PASS
RGB contract identity = PASS
M2 motion feature contract = MVP_M2_MOTION_FEATURE_V1
required provenance = complete
review_required = false
```

`coarse_direction_change_rad = null` is a valid M2 state and does not make a segment ineligible.

### Query unit

Each Calibration or Final query episode contributes exactly one Formal query segment.

Query selection uses only already-frozen robot-side metadata and no VLM/Human semantic label.

Target balance:

```text
Final:
9 gripper_transition_present = TRUE
9 gripper_transition_present = FALSE

Calibration:
approximately 4/5 split
```

Within each class, select deterministically by:

```text
SHA256("MVP_CORE_RETRIEVAL_V1|QUERY|" + segment_id)
```

If exact balance is impossible from the selected episodes, use deterministic fallback and record the realized balance. Do not replace episodes to improve retrieval results.

## 4. Candidate population and isolation

The Formal candidate population is all eligible segments from the 36 Candidate Bank episodes.

The same Candidate Bank is used for Calibration and Final Query cohorts.

Because Candidate Bank episodes are disjoint from Query episodes:

```text
query.source_episode_id != candidate.source_episode_id
```

is guaranteed structurally.

Formal retrieval is therefore Cross-episode Retrieval.

No same-episode segment may enter Formal Top-5 evidence.

## 5. Motion-only representation

```text
MOTION_REPRESENTATION =
MVP_M4_MOTION_REP_V1
```

The Formal motion vector has 17 dimensions and uses only `MVP_M2_MOTION_FEATURE_V1`.

### 5.1 Feature vector

```text
1  log1p(duration_sec)

2  log1p(eef_net_displacement_m)
3  log1p(eef_path_length_m)

4  eef_displacement_x
5  eef_displacement_y
6  eef_displacement_z

7  eef_main_direction_x
8  eef_main_direction_y
9  eef_main_direction_z

10 coarse_direction_change_rad
11 coarse_direction_missing

12 gripper_start_open
13 gripper_end_open
14 gripper_transition_present

15 action_magnitude_mean
16 action_magnitude_max
17 action_magnitude_std
```

Gripper states map:

```text
OPEN = 1
CLOSED = 0
```

If Frozen G1 gripper semantic state is not materialized, the segment is not eligible for Formal Motion-only retrieval.

`gripper_start_aperture` and `gripper_end_aperture` are not included in Core v1 to avoid duplicating the Frozen OPEN/CLOSED evidence and source-native scale.

### 5.2 Missing rule

If `coarse_direction_change_rad` is incomplete:

```text
coarse_direction_change_rad =
Candidate-Bank median over valid values

coarse_direction_missing = 1
```

Otherwise:

```text
coarse_direction_missing = 0
```

Missing must not be silently converted to zero.

### 5.3 Scaling

Continuous dimensions are Robust-scaled using Candidate Bank statistics only:

```text
z = (x - median) / IQR
```

Calibration and Final queries use transform-only.

Binary dimensions are not Robust-scaled.

If a continuous dimension has `IQR = 0`:

```text
scale_denominator = 1.0
constant_feature = recorded in provenance
```

No scaling parameter may be selected using Human relevance labels or Final Audit results.

### 5.4 Evidence-group weighting

Three groups are formed:

```text
Kinematics
Gripper
Action
```

Each group is L2-normalized independently.

Then concatenate:

```text
kinematics / sqrt(3)
gripper    / sqrt(3)
action     / sqrt(3)
```

and L2-normalize the final vector.

This freezes equal first-level weighting across the three evidence groups:

```text
MOTION_GROUP_WEIGHT =
1/3 Kinematics
1/3 Gripper
1/3 Action
```

A zero-norm subgroup remains zero. A zero-norm complete final vector is a fail-fast Formal eligibility error.

### 5.5 Similarity

```text
MOTION_SIMILARITY = COSINE
MOTION_SEARCH = FAISS IndexFlatIP
```

All Formal motion vectors are L2-normalized, so inner product is cosine-equivalent exact search.

No ANN / HNSW is used in Core v1.

## 6. SigLIP2-only representation

```text
VISUAL_REPRESENTATION =
MVP_M4_SIGLIP2_REP_V1

MODEL_ID =
google/siglip2-base-patch16-224

FORMAL_INPUT =
IMAGE_ONLY
```

The exact model repository revision SHA must be pinned and recorded in the Retrieval runtime manifest before the first inference. Floating `revision=main` is not permitted for a Formal run.

Changing the model ID requires a Design Change Request and a new protocol version.

### 6.1 Input contract

All images must come from:

```text
MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1
```

Forbidden:

```text
Audit MP4 decode
text overlay
frame-number overlay
Episode-ID overlay
lossy video roundtrip
G3-derived text
VLM-generated text
```

### 6.2 Preprocessing

Use the official processor associated with the pinned SigLIP2 checkpoint.

No custom augmentation is permitted:

```text
random crop = forbidden
color jitter = forbidden
training augmentation = forbidden
custom normalization = forbidden
```

The exact processor configuration and software versions must be recorded.

### 6.3 Frame and segment embedding

For each unique M2 keyframe:

```text
SigLIP2 image feature
→ frame-level L2 normalize
```

For a segment:

```text
unique frame embeddings
→ unweighted arithmetic mean
→ segment-level L2 normalize
```

A multi-role frame such as:

```text
START|GRIPPER_EVENT
```

is embedded exactly once.

No role-based visual weighting is used in Core v1.

### 6.4 Visual similarity

```text
VISUAL_SIMILARITY = COSINE
VISUAL_SEARCH = FAISS IndexFlatIP
```

The Formal output must retain frame-level and segment-level embedding provenance.

## 7. Retrieval engine and Top-K

```text
RETRIEVAL_ENGINE =
MVP_M5_FAISS_FLATIP_V1

TOP_K =
5
```

Motion-only and SigLIP2-only must use:

- the same query segments;
- the same Candidate Bank;
- the same `K=5`;
- the same cross-episode isolation;
- the same Human relevance labels.

FAISS is an engineering component, not the evidence of retrieval quality.

## 8. Human relevance protocol

```text
HUMAN_RELEVANCE_SCHEMA =
MVP_RETRIEVAL_RELEVANCE_V1

RETRIEVAL_RELEVANCE_GT =
INDEPENDENT_HUMAN_JUDGMENT
```

Formal pair labels:

| Label | Definition |
|---|---|
| `RELEVANT` | Same local robot behavior / interaction pattern; reasonable as a same-behavior demonstration neighbor |
| `PARTIAL` | Shares some motion or visual state, but key behavior / interaction differs |
| `NOT_RELEVANT` | Clearly different behavior |
| `BAD_SEGMENT` | Query or candidate segmentation prevents reliable behavior comparison |
| `UNSURE` | Reviewer cannot make a stable judgment |

For strict Formal Precision@5:

```text
RELEVANT = 1

PARTIAL = 0
NOT_RELEVANT = 0
BAD_SEGMENT(candidate) = 0
UNSURE = 0
```

A query whose query segment itself is judged unusable is marked:

```text
QUERY_BAD_SEGMENT = YES
```

Such a query is excluded from P@5 computation but remains in the audit record and counts against the experiment-validity gate.

Formal scoring requires at least:

```text
VALID_FINAL_QUERIES >= 15 / 18
```

### 8.1 Blind audit

For each query:

```text
Motion Top-5
+
SigLIP2 Top-5
→ union
→ deduplicate identical candidate segment
→ deterministic shuffle
→ Human review
```

The reviewer must not see:

```text
retrieval method
method-specific score
which method returned the candidate
```

The reviewer may see:

- Query keyframes;
- Candidate keyframes;
- segment duration;
- gripper start/end/transition;
- coarse robot-motion summary.

After labels are frozen, pair labels are mapped back to each method's Top-5.

Same VLM-predicted label is never accepted as relevance GT.

## 9. Calibration and Final Audit separation

### 9.1 Calibration Human Audit

Use the 9 Calibration Query episodes.

Purpose:

- validate rubric wording;
- validate audit UI;
- identify implementation bugs;
- check Human judgment stability.

Calibration labels are not Formal Core results.

After Calibration begins, the following may not be changed because one method performs poorly:

```text
model ID
motion feature vector
motion group weights
candidate bank
episode cohorts
query sampling rule
Top-K
```

Rubric wording may be clarified before Final Freeze only if the semantic meaning is not changed.

Implementation bugs may be fixed with explicit provenance.

### 9.2 Intra-rater repeat QC

Calibration audit includes 12 hidden repeated pairs.

Binary repeat mapping:

```text
RELEVANT
vs
NON_RELEVANT = all other pair labels
```

Required agreement:

```text
>= 10 / 12
```

Otherwise:

```text
RUBRIC_NOT_STABLE
FINAL_AUDIT_NOT_ALLOWED
```

### 9.3 Final Human Audit

After Calibration rubric freeze, run the 18 Final Query episodes.

The Final audit also includes 12 hidden repeated pairs.

Required Final repeat agreement:

```text
>= 10 / 12
```

If lower:

```text
FINAL_RESULT = INCONCLUSIVE_HUMAN_RELEVANCE_UNSTABLE
```

Final reviewed pairs must not be used to modify representation, sampling, thresholds, weights, or relevance semantics and then be re-reported as the same Formal result.

## 10. Formal metrics

Primary metric:

```text
STRICT_BINARY_MACRO_PRECISION_AT_5
```

Per valid query:

```text
P@5 =
number of RELEVANT candidates in Top-5 / 5
```

Formal method score:

```text
Macro P@5 =
mean of query-level P@5 over valid Final queries
```

Also report:

```text
query-level P@5
Visual - Motion paired P@5 delta
Visual strict wins
Motion strict wins
ties
QUERY_BAD_SEGMENT count
candidate BAD_SEGMENT slot rate
PARTIAL / UNSURE distribution
representative success and failure cases
```

No metric may replace P@5 as the primary success criterion in Core v1.

## 11. Frozen decision gate

### 11.1 GO — Visual Increment

```text
SigLIP2 Macro P@5 >= 0.50

AND

SigLIP2 Macro P@5
- Motion Macro P@5
>= +0.10

AND

Visual strict-win queries >= 6
```

Experiment-validity prerequisites:

```text
Final repeat agreement >= 10 / 12
VALID_FINAL_QUERIES >= 15 / 18
```

Result:

```text
CORE_RETRIEVAL_GATE = GO_VISUAL_INCREMENT
```

### 11.2 CONDITIONAL — Complementary

```text
Motion Macro P@5 >= 0.40
AND
SigLIP2 Macro P@5 >= 0.40
AND
abs(SigLIP2 - Motion) < 0.10
AND
Visual strict-win queries >= 4
AND
Motion strict-win queries >= 4
```

with the same experiment-validity prerequisites.

Result:

```text
CORE_RETRIEVAL_GATE = CONDITIONAL_COMPLEMENTARY
```

This may open a separately versioned Late Fusion extension.

### 11.3 STOP

If:

```text
Motion Macro P@5 < 0.30
AND
SigLIP2 Macro P@5 < 0.30
```

with a valid Human audit:

```text
CORE_RETRIEVAL_GATE = STOP_REPRESENTATION_NOT_SUPPORTED
```

Do not continue into VLM / Dedup / Long-tail / Coverage merely to enlarge the pipeline.

### 11.4 INCONCLUSIVE

Return INCONCLUSIVE rather than forcing GO/STOP if:

```text
Final repeat agreement < 10 / 12
OR
VALID_FINAL_QUERIES < 15 / 18
OR
no frozen GO / CONDITIONAL / STOP rule is satisfied
OR
Formal evidence is invalidated by leakage / implementation defect
```

## 12. Late Fusion

```text
CORE_V1_LATE_FUSION = DISABLED
```

No fusion weight may be tuned in Core v1.

A future Fusion Extension requires:

- separate version;
- explicit rule;
- frozen calibration/final separation;
- no reuse of Final labels for tuning.

## 13. Required provenance and outputs

Formal Core v1 must be able to reproduce every Top-K result.

Minimum required artifacts:

```text
retrieval_manifest.json
episode_split_manifest.csv

motion_feature_schema.json
motion_scaler.json
motion_segment_embeddings
motion_embedding_manifest.csv

siglip2_model_identity.json
siglip2_frame_embeddings
siglip2_segment_embeddings
visual_embedding_manifest.csv

faiss_motion.index
faiss_visual.index

calibration_query_manifest.csv
final_query_manifest.csv

motion_top5.csv
visual_top5.csv

human_audit_pairs
human_relevance_immutable_export

retrieval_evaluation_summary.json
query_level_metrics.csv
representative_cases/
```

Model provenance must record at least:

```text
model_id
exact model revision SHA
processor configuration
transformers version
torch version
device
dtype
```

## 14. Protected boundaries

Core Retrieval v1 must not modify:

- Frozen G1 Config;
- Frozen G1 Calibration evidence;
- Frozen G1 Evaluation Manifest;
- M2 motion feature definitions;
- RGB Source and Alignment Contract;
- G3 taxonomy;
- historical G1 artifacts.

No privileged object GT / reward / done / success / next_obs is allowed in Formal Core representation or relevance scoring.

## 15. Execution sequence

```text
Protocol Freeze
→ Retrieval Manifest Preparation
→ Owner Manifest Freeze
→ Runtime Preflight + exact SigLIP2 revision pin
→ M2 materialization for frozen 63 episodes
→ Motion representation
→ SigLIP2 representation
→ FAISS exact indices
→ Calibration Retrieval
→ Calibration blind Human Audit
→ rubric stability gate
→ Final Retrieval
→ Final blind Human Audit
→ freeze Human labels
→ Formal P@5 scoring
→ GO / CONDITIONAL / STOP / INCONCLUSIVE
```

No Formal SigLIP2 or FAISS retrieval inference is authorized before the Retrieval Manifest is frozen and runtime preflight passes.

## 16. Freeze status

```text
CORE_RETRIEVAL_PROTOCOL =
FROZEN_v1

MOTION_REPRESENTATION =
MVP_M4_MOTION_REP_V1

VISUAL_REPRESENTATION =
MVP_M4_SIGLIP2_REP_V1

RETRIEVAL_ENGINE =
MVP_M5_FAISS_FLATIP_V1

HUMAN_RELEVANCE_SCHEMA =
MVP_RETRIEVAL_RELEVANCE_V1

CORE_V1_LATE_FUSION =
DISABLED

CORE_RETRIEVAL_MANIFEST =
NOT_FROZEN

CORE_RETRIEVAL_INFERENCE =
BLOCKED_PENDING_RETRIEVAL_MANIFEST_FREEZE_AND_RUNTIME_PREFLIGHT

NEXT =
RETRIEVAL_MANIFEST_PREPARATION_AND_OWNER_FREEZE
```

Any change to the frozen representation definition, data split rule, Human relevance semantics, primary metric, or decision gate requires:

```text
DESIGN_CHANGE_REQUEST
→ new protocol version
→ new provenance
```
