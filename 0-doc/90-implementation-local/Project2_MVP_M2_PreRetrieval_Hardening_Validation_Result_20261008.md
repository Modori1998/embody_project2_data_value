# Project 2 MVP-M2 Pre-Retrieval Hardening Validation Result

```text
DATE = 2026-10-08
DOCUMENT_STATUS = PASS
SOURCE_OF_TRUTH = GITHUB_MAIN
TASK = VALIDATE_M2_PRE_RETRIEVAL_HARDENING

GIT_BASE_AFTER_PULL =
b9c1cf00fbacc735e66d40cbcdf6bd192ecb5793

HARDENING_COMMIT =
b9c1cf00fbacc735e66d40cbcdf6bd192ecb5793
Harden M2 pre-retrieval runtime gates

RUNTIME_RUN_ID =
mvp_m2_hardening_validation_20261008

OUTPUT_RUN =
outputs/mvp_m2/mvp_m2_hardening_validation_20261008
```

## 1. Validation scope

This task validates the already committed MVP-M2 pre-retrieval hardening. It
does not implement or execute Core Retrieval.

```text
SIGLIP2_EXECUTED = NO
DINO_EXECUTED = NO
FAISS_EXECUTED = NO
EMBEDDING_EXECUTED = NO
RETRIEVAL_EXECUTED = NO
P5_EXECUTED = NO
LATE_FUSION_EXECUTED = NO
VLM_EXECUTED = NO
DEDUP_EXECUTED = NO
LONG_TAIL_EXECUTED = NO
COVERAGE_EXECUTED = NO
RETRIEVAL_PROTOCOL_MODIFIED = NO
```

## 2. Tests

```text
M2_HARDENING_UNIT_TESTS = PASS_8_OF_8
RGB_CONTRACT_TESTS = PASS_3_OF_3
G1_BOUNDARY_TARGETED_REGRESSION = PASS_15_OF_15
TOTAL_TARGETED_TESTS = PASS_26_OF_26
```

The M2 suite includes and passed:

```text
test_frozen_g1_identity_is_explicit_and_detects_drift
test_runtime_sanity_is_computed_and_detects_corruption
```

Negative-test interpretation:

```text
tau_C12 artificial drift -> identity checker rejects input
out-of-segment keyframe corruption -> sanity checker rejects input

FROZEN_IDENTITY_NEGATIVE_TEST = PASS
SANITY_CORRUPTION_NEGATIVE_TEST = PASS
```

No ignored historical outputs were reconstructed to pursue a full-repository
green result.

## 3. Frozen G1 identity gate

The runtime called `assert_frozen_g1_identity()` before materialization. The
checker compares runtime imports against an explicit independent expected
identity and also verifies required literals in the Frozen config document.

Expected identity:

```text
stage_a_acceptance_config = A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
boundary_consolidation_window = 8
p12_incomplete = FAIL_OPEN_KEEP
c12_incomplete = P12_ONLY_FALLBACK
```

Runtime identity:

```text
stage_a_acceptance_config = A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
boundary_consolidation_window = 8
p12_incomplete = FAIL_OPEN_KEEP
c12_incomplete = P12_ONLY_FALLBACK
```

```text
FROZEN_G1_EXPECTED_IDENTITY = PASS
FROZEN_G1_RUNTIME_IDENTITY = PASS
```

Frozen document identity:

```text
PATH =
0-doc/10-design-review/Project2_G1_P3_Final_Calibration_Config_FROZEN_v1_20260927.md

RECORDED_SHA256 =
27e0101d0bfef98fd3340cd9f0ea00738eaf74e549d545325822ae667bb002dd

INDEPENDENTLY_RECOMPUTED_SHA256 =
27e0101d0bfef98fd3340cd9f0ea00738eaf74e549d545325822ae667bb002dd

FROZEN_G1_CONFIG_DOC_IDENTITY = PASS
```

## 4. Fresh real-data materialization

The new immutable run used the current hardening checkout and did not reuse a
previous worktree output.

```text
EPISODES = data/demo_0, data/demo_1, data/demo_2
EPISODES_PROCESSED = 3
SEGMENTS_PROCESSED = 13
KEYFRAME_ROWS = 39
UNIQUE_RGB_FILES = 39
MULTI_ROLE_FRAME_COUNT = 9
GRIPPER_EVENT_SEGMENTS = 9
```

The runtime used the existing audited
`project1_robomimic_audit_v150` rendering environment. The known RoboMimic
dataset/runtime version warning was emitted; all requested episodes and frames
materialized successfully.

## 5. Computed runtime sanity

`sanity_summary.json` was produced from `compute_m2_sanity_checks(...)` and
accepted by `assert_m2_sanity(...)`. These values were computed from the
materialized segment, keyframe, motion, and RGB provenance rows; they were not
written as unconditional PASS strings.

```text
FROZEN_G1_CONFIG_IDENTITY = PASS
RGB_CONTRACT_IDENTITY = PASS
KEYFRAME_FRAME_IN_SEGMENT = PASS
START_FRAME_EXACT = PASS
END_FRAME_EXACT = PASS
MIDDLE_DETERMINISTIC = PASS
NO_DUPLICATE_RGB_MATERIALIZATION = PASS
MULTI_ROLE_FRAME_PRESERVED = PASS
GRIPPER_EVENT_SEMANTICS = PASS
MOTION_FEATURE_FINITE = PASS
NO_PRIVILEGED_INPUT = PASS
SEGMENT_DURATION_IDENTITY = PASS

COMPUTED_SANITY_CHECKS = PASS
```

## 6. Protected artifacts and isolation

```text
FROZEN_G1_CONFIG_MODIFIED = NO
FROZEN_CALIBRATION_DOCS_MODIFIED = NO
FROZEN_EVALUATION_MANIFEST_MODIFIED = NO
HISTORICAL_G1_ARTIFACTS_MODIFIED = NO
PRODUCTION_CODE_MODIFIED_BY_VALIDATION = NO
TEST_CODE_MODIFIED_BY_VALIDATION = NO
PROTECTED_ARTIFACT_CHECK = PASS
```

Only this validation result and the two authorized MVP SSOT status fields are
changed by the validation task.

## 7. Gate result

```text
MVP_M2_PRE_RETRIEVAL_HARDENING = PASS
CORE_RETRIEVAL_INFERENCE_BLOCKER = CLEARED
READY_FOR_CORE_RETRIEVAL_PROTOCOL_FREEZE = YES

CORE_RETRIEVAL_INFERENCE =
BLOCKED_PENDING_CORE_RETRIEVAL_PROTOCOL_FREEZE

FINAL_STATUS =
PASS_READY_FOR_CORE_RETRIEVAL_PROTOCOL_FREEZE
```

Clearing the M2 engineering blocker does not authorize inference. Core
Retrieval inference remains blocked until the separate Retrieval Protocol is
formally frozen.
