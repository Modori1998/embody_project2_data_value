# Project 2 MVP-M2 Keyframe and Robot Motion Summary Result

```text
DATE = 2026-10-08
DOCUMENT_STATUS = PASS
SOURCE_OF_TRUTH = GITHUB_MAIN

GIT_BASE_AFTER_PULL =
6b5ec7bda94d7a27f1957a8a8d89015cc34e23cc

REMOTE_MAIN_BEFORE_IMPLEMENTATION =
6b5ec7bda94d7a27f1957a8a8d89015cc34e23cc

FEATURE_VERSION =
MVP_M2_MOTION_FEATURE_V1

RGB_CONTRACT_VERSION =
MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1

OUTPUT_RUN =
outputs/mvp_m2/mvp_m2_20261008_final

DETERMINISTIC_REPLAY_RUN =
outputs/mvp_m2/mvp_m2_20261008_final_replay
```

## 1. Scope and isolation

This change implements only MVP-M2:

```text
Frozen G1 Segment
-> deterministic minimal keyframes
-> selected clean RGB PNGs
-> raw interpretable robot motion summary
```

The implementation adds code under `src/project2_mvp/` and does not modify
`src/project2_g1/`, the Frozen G1 configuration, calibration protocol,
evaluation manifest, historical calibration/evaluation evidence, or the
existing RGB contract.

No SigLIP2, DINOv2, VLM, FAISS, embedding, retrieval, Precision@5, late
fusion, dedup, long-tail, coverage, or G3 taxonomy work was executed.

## 2. Frozen G1 identity

The runtime imports and reuses the existing Frozen G1 execution path:

```text
STAGE_A_ACCEPTANCE_CONFIG = A1-007-C002
tau_P12 = 0.04758563666765155
tau_C12 = 0.690169167642685
boundary_consolidation_window = 8
P12 incomplete = FAIL_OPEN_KEEP
C12 incomplete = P12_ONLY_FALLBACK

FROZEN_G1_CONFIG_IDENTITY = PASS
```

G1 segment semantics were verified from the implementation:

```text
start_frame = inclusive
end_frame = inclusive
duration_frames = end_frame - start_frame + 1
Final Boundary frame = next segment start_frame
```

## 3. Keyframe policy

The first M2 version implements only:

```text
START = segment.start_frame
MIDDLE = floor((segment.start_frame + segment.end_frame) / 2)
END = segment.end_frame
GRIPPER_EVENT = segment.start_frame
                only when the segment left Final Boundary type is
                GRIPPER_TRANSITION
```

The right boundary at `end_frame + 1` is never inserted into the current
segment. Suppressed candidates are not consulted. Roles that resolve to the
same frame are joined in one manifest row and one PNG is written for that
segment/frame.

## 4. Motion feature contract

`MVP_M2_MOTION_FEATURE_V1` consumes only:

```text
obs/robot0_eef_pos
obs/robot0_gripper_qpos
recorded actions
Frozen G1 gripper_state
```

It rejects object state, `Can_pos`, `Can_quat`, reward, done, success,
`next_obs`, raw simulator states, and other unapproved fields.

The fixed zero-displacement epsilon is:

```text
MOTION_DIRECTION_EPSILON_M = 1e-9 meter
```

`coarse_direction_change_rad` compares deterministic non-overlapping first
and second halves. It is `null` with
`coarse_direction_context_complete=false` when either half has fewer than two
positions or displacement is at/below the fixed epsilon. Incomplete evidence
is not written as zero.

Gripper semantic state reuses the actual Frozen G1 runtime state; M2 adds no
OPEN/CLOSED threshold. `gripper_transition_present` includes a left
`GRIPPER_TRANSITION` Final Boundary because its frame is the segment start.

Action summaries are command-space statistics and retain the provenance:

```text
NORMALIZED_CONTROLLER_INPUT
```

They are not described as physical speed, m/s, rad/s, or EEF velocity. No
retrieval normalization or scaling is applied in M2.

## 5. RGB identity

All selected images use the existing formal path:

```text
source STATE_t
-> P1 RoboMimicStateRenderer
-> direct RGB uint8
-> lossless PNG
```

```text
RGB_CONTRACT_IDENTITY = PASS
AUDIT_MP4_USED = NO
TEXT_OVERLAY = NO
LOSSY_VIDEO_ROUNDTRIP = NO
```

The runtime used the previously audited
`project1_robomimic_audit_v150` environment. The renderer emitted the known
dataset/runtime version warning (dataset 1.5.1, installed environment 1.5.0),
the same environment class already used for Project 1 / RGB materialization;
rendering completed successfully for every selected frame.

## 6. Runtime sample and counts

```text
EPISODES_PROCESSED = 3
EPISODES =
data/demo_0
data/demo_1
data/demo_2

SEGMENTS_PROCESSED = 13
KEYFRAME_ROWS = 39
UNIQUE_RGB_FILES = 39
MULTI_ROLE_FRAME_COUNT = 9
GRIPPER_EVENT_SEGMENTS = 9
GRIPPER_TRANSITION_PRESENT_TRUE = 9
```

The sample covers both gripper-event and non-gripper segment starts. The
runtime materialized selected keyframes only, not all episode RGB frames.

## 7. Validation

Unit and regression tests:

```text
MVP_M2_TESTS = PASS_6_OF_6
MVP_RGB_CONTRACT_TESTS = PASS_3_OF_3
G1_BOUNDARY_ENGINE_REGRESSION = PASS_15_OF_15
PYTHON_COMPILE = PASS
TOTAL = PASS_24_OF_24
```

The M2 tests cover single-frame role deduplication, two-frame segments, odd
and even middle selection, left/right GRIPPER boundary semantics, in-segment
keyframes, deterministic selection, EEF net displacement/path length,
zero-displacement direction, incomplete coarse direction context, action
magnitude, duration identity, and privileged-field rejection.

Two complete real-data materializations were compared. The following files
were byte-identical:

```text
segment_input_manifest.csv
keyframe_manifest.csv
robot_motion_summary.csv
rgb_provenance.json
motion_feature_contract.json
sanity_summary.json
```

All 39 PNG relative paths and file SHA256 values were also identical.
`run_meta.json` was excluded from byte comparison because `run_id` and
`created_at` are intentionally run-specific.

A broader repository discovery run was also attempted:

```text
FULL_REPOSITORY_DISCOVERY = 457 tests
RESULT = 3 failures, 11 errors, 17 skipped
```

This is not reported as a repository-wide PASS. The observed errors include
tests that require historical official `outputs/g1_*` artifacts which are
intentionally ignored by Git and are absent from this isolated worktree.
Those Frozen historical artifacts were not reconstructed, copied, or modified
to make unrelated tests pass. The M2 gate relies on the targeted M2, RGB
contract, and G1 boundary regression suites listed above plus the two real-data
runtime replays.

## 8. PASS gate

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
DETERMINISTIC_REPLAY = PASS
PROTECTED_ARTIFACT_CHECK = PASS
```

Protected artifacts pass means this implementation has no Git diff in the
Frozen G1 config/protocol, Frozen Evaluation material, historical G1 evidence,
or the existing RGB contract implementation.

## 9. Gate result

```text
MVP_M2_IMPLEMENTED = YES
MVP_M2_RUNTIME_VALIDATION = PASS
READY_FOR_CORE_RETRIEVAL = YES

SIGLIP2_EXECUTED = NO
DINO_EXECUTED = NO
VLM_EXECUTED = NO
FAISS_EXECUTED = NO

FINAL_STATUS = PASS_READY_FOR_CORE_RETRIEVAL
```

This result opens only the next Core Retrieval design gate. It does not freeze
motion scaling/similarity, SigLIP2 preprocessing, query/candidate sampling,
human relevance rubric, evaluation split, P@5 protocol, or late-fusion rules.
