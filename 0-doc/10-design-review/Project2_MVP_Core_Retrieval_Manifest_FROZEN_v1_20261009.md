# Project 2 MVP Core Retrieval Manifest FROZEN v1

```text
DATE = 2026-10-09
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

DESIGN_OWNER_FREEZE_DECISION = APPROVED
MANIFEST_VERSION = MVP_CORE_RETRIEVAL_MANIFEST_v1

GIT_BASE_AT_OWNER_FREEZE =
68958ede4b33d841ef49d941fb904f8670b802b7

PROTOCOL =
MVP_CORE_RETRIEVAL_PROTOCOL_v1

PROTOCOL_DOC =
Project2_MVP_Core_Retrieval_Protocol_FROZEN_v1_20261008.md

PREPARATION_RESULT =
Project2_MVP_Core_Retrieval_Manifest_Preparation_Result_20261008.md

CORE_RETRIEVAL_MANIFEST =
FROZEN_v1

QUERY_SEGMENT_MANIFEST =
NOT_YET_MATERIALIZED

CORE_RETRIEVAL_INFERENCE =
BLOCKED_PENDING_RUNTIME_PREFLIGHT
```

## 1. Owner decision

The Design Owner accepts the deterministic Episode-level Retrieval Manifest produced under the frozen Core Retrieval Protocol.

This freeze locks the exact 63 Episode IDs below. They must not be replaced because later Motion-only or SigLIP2 retrieval results are favorable or unfavorable.

This freeze does **not** select concrete query segment IDs yet. Query segment selection remains governed by the already frozen deterministic protocol and occurs only after runtime preflight and M2 materialization of the frozen episodes.

## 2. Freeze evidence

Preparation result:

```text
TOTAL_DATASET_EPISODES = 300
HISTORICAL_G1_UNIQUE_EPISODES = 32
FROZEN_G1_EVALUATION_EPISODES = 24
HISTORICAL_VS_FROZEN_EVAL_OVERLAP = 0
ELIGIBLE_RETRIEVAL_POOL = 244
UNREADABLE_OR_SCHEMA_INVALID = 0

DURATION_STRATA:
SHORT = 81
MEDIUM = 81
LONG = 82

SELECTION_SALT =
MVP_CORE_RETRIEVAL_V1

RETRIEVAL_MANIFEST_DISJOINTNESS = PASS
LEAKAGE_AUDIT = PASS
DETERMINISTIC_REPLAY = PASS
TESTS = PASS_15_OF_15
```

Dataset identity:

```text
dataset_id = robomimic_v15_can_mh

raw_hdf5_sha256 =
6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b

low_dim_hdf5_sha256 =
c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7
```

## 3. Candidate Bank — 36 Episodes

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

Frozen count:

```text
CANDIDATE_BANK_COUNT = 36
SHORT = 12
MEDIUM = 12
LONG = 12
```

## 4. Calibration Query — 9 Episodes

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

Frozen count:

```text
CALIBRATION_QUERY_COUNT = 9
SHORT = 3
MEDIUM = 3
LONG = 3
```

## 5. Final Query — 18 Episodes

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

Frozen count:

```text
FINAL_QUERY_COUNT = 18
SHORT = 6
MEDIUM = 6
LONG = 6
```

## 6. Disjointness and leakage contract

```text
TOTAL_SELECTED_UNIQUE = 63

CANDIDATE_CALIBRATION_OVERLAP = 0
CANDIDATE_FINAL_OVERLAP = 0
CALIBRATION_FINAL_OVERLAP = 0

SELECTED_HISTORICAL_G1_OVERLAP = 0
SELECTED_FROZEN_G1_EVAL_OVERLAP = 0

MANUAL_EPISODE_CHERRY_PICK_USED = NO
HUMAN_LABEL_USED_FOR_SELECTION = NO
SIGLIP2_RESULT_USED_FOR_SELECTION = NO
MOTION_RETRIEVAL_RESULT_USED_FOR_SELECTION = NO
```

Any future substitution of an Episode requires a new Design Change Request and a new manifest version with explicit provenance.

## 7. What remains unfrozen

The following are not yet runtime-materialized:

```text
Concrete Query Segment IDs
63-Episode M2 materialization
Exact SigLIP2 repository revision SHA
SigLIP2 frame/segment embeddings
Motion representation runtime artifacts
FAISS indices
Top-5 neighbors
Human relevance labels
P@5 result
```

The rules governing these items are already frozen in the Core Retrieval Protocol.

## 8. Next gate

The next gate is:

```text
CORE_RETRIEVAL_RUNTIME_PREFLIGHT
```

It must, before Formal inference:

1. pull the latest GitHub main;
2. verify this Frozen Manifest and the Frozen Retrieval Protocol identities;
3. verify dataset and M2/RGB contract identities;
4. verify local runtime/dependencies for Motion and SigLIP2;
5. resolve and pin the exact SigLIP2 model revision SHA without running Formal retrieval;
6. confirm output immutability and provenance paths.

Only after preflight PASS may the frozen 63 episodes be M2-materialized and concrete query segments selected under the frozen deterministic rule.

```text
CORE_RETRIEVAL_MANIFEST = FROZEN_v1
CORE_RETRIEVAL_RUNTIME_PREFLIGHT = NOT_RUN
CORE_RETRIEVAL_INFERENCE = BLOCKED_PENDING_RUNTIME_PREFLIGHT
NEXT = CORE_RETRIEVAL_RUNTIME_PREFLIGHT
```
