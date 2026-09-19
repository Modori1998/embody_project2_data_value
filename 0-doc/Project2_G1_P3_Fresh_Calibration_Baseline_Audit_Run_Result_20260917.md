# Project 2 G1-P3 Fresh Calibration Baseline Audit Run Result

```text
DATE = 2026-09-17
TASK = FRESH_CALIBRATION_BASELINE_AUDIT_RUN
RESULT = PASS_READY_FOR_HUMAN_REVIEW
```

## 1. Authority

```text
CALIBRATION_PROTOCOL = FROZEN_v1.0
DRIVE_LOCAL_FROZEN_PROTOCOL_MATCH = PASS
FRESH_MANIFEST_ID = g1_fresh_calibration_manifest_2aa5cfe05295
FRESH_EPISODE_COUNT = 6
RUN_PURPOSE = FRESH_CALIBRATION_BASELINE_HUMAN_AUDIT
PARAMETER_SEARCH_ALLOWED = NO
SEARCH_GATE = CLOSED
```

Authority was read from Drive and local sources before generation. The Drive and local Frozen Protocol text matched after newline normalization. Fresh IDs were read from the immutable manifest rather than copied from the task prompt.

## 2. Run Identity

```text
run_id = g1_calibration_20260917_222604_d4425fc3
parent_run_id = g1_exploratory_audit_20260917_141541_fe251439
run_stage = CALIBRATION
set_role = CALIBRATION
calibration_role = BASELINE_HUMAN_AUDIT
calibration_config_role = BASELINE_UNMODIFIED
human_review_status = NOT_STARTED
```

The parent is the formal Seed source run. It has the same signal contract, Detector config, and MATERIALIZED_V1 Final semantics; the child changes only the frozen Episode set and its run role.

## 3. Episode Set

```text
episode_count = 6
episodes =
  data/demo_150
  data/demo_162
  data/demo_213
  data/demo_255
  data/demo_260
  data/demo_270
MANIFEST_EXACT_MATCH = PASS
MISSING_FROM_RUN = 0
EXTRA_IN_RUN = 0
SEED_OVERLAP = 0
```

## 4. Baseline Identity

```text
config_version = g1_p2_exploratory_segmentation.v0
segmentation_version = G1-P2-EXPLORATORY-v0
signal_contract_version = g1_p1_signal_contract.v0
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
CONFIG_HASH_SAME_AS_BASELINE = YES
SIGNAL_CONTRACT_HASH_SAME_AS_BASELINE = YES
PARAMETER_DIFF_COUNT = 0
```

No threshold, persistence, debounce, consolidation, pause bridge, segment length, support, or Direction evidence parameter changed.

## 5. Generated Artifacts

Each Episode owns a complete formal package:

```text
Candidate = 6 candidate_boundaries.csv
Decision = 6 boundary_decisions.csv
Final = 6 final_boundaries.csv
Segment = 6 segment_manifest.csv
Media = 6 browser-proxied video.mp4
Plots = 6 signal_plot.png + 6 signal_boundary_plot.png
Final semantics = MATERIALIZED_V1
```

Final tables retain `representative_candidate_id`, aligned member ID/type/frame pipes, `member_candidate_count`, representative `candidate_type`, and one Final frame.

## 6. Formal Run Summary

| Episode | Length | Candidate | Final | Gripper Primary | Direction Primary | Merged | Short Segment |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/demo_150` | 236 | 10 | 6 | 3 | 3 | 3 | 2 |
| `data/demo_162` | 235 | 11 | 4 | 3 | 1 | 3 | 2 |
| `data/demo_213` | 149 | 6 | 3 | 3 | 0 | 3 | 2 |
| `data/demo_255` | 218 | 10 | 8 | 3 | 4 | 2 | 2 |
| `data/demo_260` | 230 | 13 | 9 | 3 | 4 | 3 | 2 |
| `data/demo_270` | 210 | 7 | 5 | 3 | 1 | 0 | 2 |

## 7. Screening Consistency

```text
SCREENING_FORMAL_RUN_CONSISTENCY = PASS
differences = NONE
```

For every Episode, length, Candidate count, Final count, Gripper Primary count, Direction Primary count, merged count, and short-segment count exactly match selection screening.

## 8. Human Review Initial State

```text
P1:
  PASS = 0
  FAIL = 0
  UNCERTAIN = 0
  NOT_REVIEWED = 36

P2:
  Final Total = 35
  VALID = 0
  REDUNDANT = 0
  MISALIGNED = 0
  NOT_REVIEWED = 35

Human Added = 0
HISTORICAL_P1_REUSE = 0
```

No owner review row was written during generation or smoke testing.

## 9. Web

```text
Registry = PASS (AUTO_REGISTERED)
Home visible = PASS
6 Episode HTTP smoke = PASS
Browser UI smoke = PASS
```

Home simultaneously displays the new Calibration run and both existing Exploratory runs. All six Episode pages returned successfully using a temp review DB. Their browser-compatible proxy video, P1 plot, P2 plot, review controls, and initial NOT_REVIEWED state were verified. The real browser check confirmed the Calibration banner and read-only Merged Evidence; no review or export action was submitted.

## 10. Tests

```text
total = 88
PASS = 88
FAIL = 0
```

Coverage includes Fresh exact-set, stage/role, fixed hashes, parameter diff zero, count six, Seed exclusion, MATERIALIZED_V1 semantics, validator, registry, screening consistency, Web load/media, initial review state, no export/GT artifacts, plus existing Audit Web, P2 engine, Final semantics, and selection regressions. A FastAPI/Starlette deprecation warning is non-functional.

## 11. Immutability

Pre/post SHA-256 or deterministic tree fingerprints:

```text
DATASET_UNCHANGED = PASS
  raw = 6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b
  low_dim = c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7
FRESH_MANIFEST_UNCHANGED = PASS
  90044584b64dff0c21d1d17af3c51f98b279b4053ba1bcb42ef399da641a873c
FROZEN_PROTOCOL_UNCHANGED = PASS
  d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a
SEED_EXPORT_UNCHANGED = PASS
  8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7
EXISTING_RUNS_UNCHANGED = PASS
  20260916 = da1bc0abee824c0ae63b053fbceea53996373ba87e2d063fd8e223cac2e3c4d6
  20260917 = 4ec155960e70187a89948e1fa9193d0dc4837eb6c1d36dc96016be54df3db4fe
OWNER_SQLITE_UNCHANGED = PASS
  2b262a201fedba71d37366aa58f228a3d98903f29cf3cd1adc3870f7c9b51502
```

## 12. Explicit Non-Scope

```text
PARAMETER_SEARCH_EXECUTED = NO
CANONICAL_GT_GENERATED = NO
MATCHING_EXECUTED = NO
CALIBRATION_EXPORT_GENERATED = NO
STAGE_A0_EXECUTED = NO
EVALUATION_SELECTED = NO
```

## 13. Search Gate

```text
SEARCH_GATE = CLOSED
reason = Fresh 6 Human Review not complete
```

## 14. Final Status

```text
G1_FRESH_CALIBRATION_BASELINE_AUDIT_RUN =
PASS_READY_FOR_HUMAN_REVIEW
```
