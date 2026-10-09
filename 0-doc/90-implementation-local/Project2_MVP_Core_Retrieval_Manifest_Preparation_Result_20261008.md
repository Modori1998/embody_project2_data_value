# Project 2 MVP Core Retrieval Manifest Preparation Result

```text
DATE = 2026-10-09
DOCUMENT_STATUS = READY_FOR_OWNER_REVIEW
SOURCE_OF_TRUTH = GITHUB_MAIN
TASK = PREPARE_CORE_RETRIEVAL_MANIFEST_FOR_OWNER_REVIEW

GIT_BASE_AFTER_PULL =
3dd3ad5558d736bb28b80db36be30a899e635beb

CORE_RETRIEVAL_PROTOCOL =
FROZEN_v1

PROTOCOL_DOCUMENT =
0-doc/10-design-review/Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md

MANIFEST_CANDIDATE_VERSION =
MVP_CORE_RETRIEVAL_MANIFEST_CANDIDATE_v1

OUTPUT_RUN =
outputs/mvp_core_retrieval_manifest_preparation/mvp_core_retrieval_manifest_prep_20261009_v2

DETERMINISTIC_REPLAY_RUN =
outputs/mvp_core_retrieval_manifest_preparation/mvp_core_retrieval_manifest_prep_20261009_v2_replay
```

## 1. Scope and authority

This task prepares an Episode-level Retrieval Manifest candidate under the
already frozen `MVP_CORE_RETRIEVAL_PROTOCOL_v1`. It does not freeze the
manifest and does not authorize inference.

```text
CORE_RETRIEVAL_MANIFEST = READY_FOR_OWNER_REVIEW
MANIFEST_FROZEN = NO
CORE_RETRIEVAL_INFERENCE =
BLOCKED_PENDING_RETRIEVAL_MANIFEST_FREEZE_AND_RUNTIME_PREFLIGHT
CORE_V1_LATE_FUSION = DISABLED
```

## 2. Dataset identity and technical scan

```text
dataset_id = robomimic_v15_can_mh
total_dataset_episodes = 300
sample_hz = 20.0

demo_v15.hdf5 SHA256 =
6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b

low_dim_v15.hdf5 SHA256 =
c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7

DATASET_IDENTITY = PASS
UNREADABLE_OR_SCHEMA_INVALID = 0
```

The existing formal Source Contract and G1 `scan_dataset(...)` helper were
reused. The scan checked episode identity, formal input readability, temporal
alignment, required shapes, frame count, and dataset provenance only.

## 3. Historical G1 exclusion

The existing G1 `load_historical_sets(...)` helper reconstructed and
cross-checked authoritative artifacts without copying or regenerating them.

| Historical source | Episode count |
|---|---:|
| Exploratory | 6 |
| Calibration Seed | 6 |
| Calibration Fresh | 6 |
| Calibration Combined | 12 |
| Design Diagnostic | 20 |
| Unique union | 32 |

Exploratory and Calibration Seed intentionally identify the same six
episodes. Calibration Combined equals Seed union Fresh. All redundant source
artifacts agreed; no provenance conflict occurred. Per-episode source artifact
provenance is retained in `historical_episode_usage.csv`.

## 4. Frozen G1 Evaluation exclusion

```text
SOURCE =
0-doc/10-design-review/Project2_G1_P4_Independent_Evaluation_Manifest_FROZEN_v1_20260929.csv

manifest_version = G1_P4_EVAL_MANIFEST_v1
episode_count = 24
historical_vs_frozen_eval_overlap = 0
```

The Frozen G1 Evaluation episodes remain excluded despite the deferred Human
Evaluation, preserving their held-out identity. No overlap was silently
resolved.

## 5. Eligible Retrieval pool

```text
TOTAL_DATASET_EPISODES = 300
HISTORICAL_G1_UNIQUE_EPISODES = 32
FROZEN_G1_EVALUATION_EPISODES = 24
HISTORICAL_VS_FROZEN_EVAL_OVERLAP = 0
UNREADABLE_OR_SCHEMA_INVALID = 0
ELIGIBLE_RETRIEVAL_POOL = 244
```

Eligibility was exactly:

```text
READABLE
AND schema valid
AND not historical G1 used
AND not Frozen G1 Evaluation
```

## 6. Duration terciles

Only the 244 eligible episodes were sorted by:

```text
(frame_count ASC, episode_id ASC)
```

With `n=244`:

```text
first_cut = floor(244 / 3) = 81
second_cut = floor(2 * 244 / 3) = 162

SHORT  = ranks [0, 81)   = 81 episodes
MEDIUM = ranks [81, 162) = 81 episodes
LONG   = remaining       = 82 episodes

SHORT max frame_count = 146
MEDIUM max frame_count = 203
```

No label, detector score, Human GT, FP/FN, error mode, or retrieval result was
used for strata.

## 7. Deterministic selection

```text
SELECTION_SALT = MVP_CORE_RETRIEVAL_V1

digest = SHA256("MVP_CORE_RETRIEVAL_V1|" + episode_id)

within each stratum:
sort by (digest ASC, episode_id ASC)

stratum ranks 1..12  -> CANDIDATE_BANK
stratum ranks 13..15 -> CALIBRATION_QUERY
stratum ranks 16..21 -> FINAL_QUERY
```

No independent resampling and no manual episode substitution occurred.

## 8. Candidate Bank — 36 Episodes

```text
data/demo_15
data/demo_157
data/demo_36
data/demo_34
data/demo_31
data/demo_147
data/demo_1
data/demo_26
data/demo_16
data/demo_246
data/demo_109
data/demo_188
data/demo_225
data/demo_103
data/demo_187
data/demo_272
data/demo_131
data/demo_164
data/demo_268
data/demo_142
data/demo_261
data/demo_158
data/demo_163
data/demo_287
data/demo_82
data/demo_67
data/demo_95
data/demo_50
data/demo_228
data/demo_59
data/demo_293
data/demo_257
data/demo_54
data/demo_171
data/demo_243
data/demo_56
```

Stratum counts: `SHORT=12`, `MEDIUM=12`, `LONG=12`.

## 9. Calibration Query — 9 Episodes

```text
data/demo_189
data/demo_148
data/demo_5
data/demo_249
data/demo_215
data/demo_294
data/demo_297
data/demo_200
data/demo_65
```

Stratum counts: `SHORT=3`, `MEDIUM=3`, `LONG=3`.

## 10. Final Query — 18 Episodes

```text
data/demo_139
data/demo_186
data/demo_104
data/demo_116
data/demo_45
data/demo_37
data/demo_115
data/demo_156
data/demo_149
data/demo_197
data/demo_118
data/demo_237
data/demo_88
data/demo_55
data/demo_281
data/demo_250
data/demo_279
data/demo_283
```

Stratum counts: `SHORT=6`, `MEDIUM=6`, `LONG=6`.

## 11. Disjointness audit

```text
CANDIDATE_COUNT = 36
CALIBRATION_QUERY_COUNT = 9
FINAL_QUERY_COUNT = 18
TOTAL_SELECTED_UNIQUE = 63

CANDIDATE_CALIBRATION_OVERLAP = 0
CANDIDATE_FINAL_OVERLAP = 0
CALIBRATION_FINAL_OVERLAP = 0
SELECTED_HISTORICAL_G1_OVERLAP = 0
SELECTED_FROZEN_G1_EVAL_OVERLAP = 0

STRATUM_BALANCE = PASS
RETRIEVAL_MANIFEST_DISJOINTNESS = PASS
```

## 12. Leakage audit

```text
human_label_used = false
G1_human_GT_used_for_selection = false
G1_detector_score_used = false
FP_FN_used = false
error_mode_used = false
VLM_label_used = false
SigLIP2_embedding_used = false
motion_retrieval_similarity_used = false
retrieval_result_used = false
manual_episode_cherry_pick_used = false
formal_retrieval_executed = false
human_retrieval_audit_started = false

LEAKAGE_AUDIT = PASS
```

Only episode identity, frame count, technical readability/schema, historical
membership, Frozen G1 Evaluation membership, and deterministic SHA256 were
used.

## 13. Determinism and tests

The unit test compared forward, reversed, and fixed-random input order. A
second complete real-data run independently reproduced byte-identical outputs
for all CSV, audit, provenance, and summary files. `run_meta.json` was excluded
because its `run_id` and `created_at` are intentionally run-specific.

```text
NEW_MANIFEST_TESTS = PASS_15_OF_15
PYTHON_COMPILE = PASS
DETERMINISTIC_REPLAY = PASS
```

Tests cover historical exclusion, Frozen Eval 24 validation, exclusion-set
overlap rejection, deterministic duration terciles, SHA ranking, 36/9/18
counts, cohort disjointness, 12/3/6 balance, frozen stratum-rank ranges, input
order independence, forbidden import isolation, immutable output, leakage
fields, dataset identity failure, and insufficient-pool failure.

## 14. Query segment feasibility note

```text
QUERY_SEGMENT_SELECTION_EXECUTED = NO
QUERY_SEGMENT_BALANCE = PENDING_POST_MANIFEST_M2_MATERIALIZATION
QUERY_SELECTION_RULE = FROZEN_BY_PROTOCOL
```

No concrete `segment_id` was produced. After Owner Manifest Freeze and runtime
preflight, M2 may be materialized for the frozen 63 episodes and the already
frozen deterministic segment-selection rule applied. Episodes must not be
replaced to improve gripper balance.

## 15. Scope isolation

```text
G1_SEGMENTATION_EXECUTED = NO
M2_MATERIALIZATION_EXECUTED = NO
SIGLIP2_EXECUTED = NO
DINO_EXECUTED = NO
FAISS_EXECUTED = NO
EMBEDDING_EXECUTED = NO
RETRIEVAL_EXECUTED = NO
TOP5_EXECUTED = NO
HUMAN_AUDIT_STARTED = NO
P5_COMPUTED = NO
VLM_EXECUTED = NO
LATE_FUSION_EXECUTED = NO
DEDUP_EXECUTED = NO
LONG_TAIL_EXECUTED = NO
COVERAGE_EXECUTED = NO
```

## 16. Owner gate

```text
CORE_RETRIEVAL_MANIFEST = READY_FOR_OWNER_REVIEW
CORE_RETRIEVAL_MANIFEST_FROZEN = NO
CORE_RETRIEVAL_INFERENCE =
BLOCKED_PENDING_RETRIEVAL_MANIFEST_FREEZE_AND_RUNTIME_PREFLIGHT
NEXT = OWNER_REVIEW_RETRIEVAL_MANIFEST

FINAL_STATUS = PASS_READY_FOR_OWNER_RETRIEVAL_MANIFEST_REVIEW
```

The Owner must review and separately freeze the exact 63 Episode IDs and
provenance before runtime preflight or any Formal Core Retrieval inference.
