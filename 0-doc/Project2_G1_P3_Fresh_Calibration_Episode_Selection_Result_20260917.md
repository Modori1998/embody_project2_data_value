# Project 2 G1-P3 Fresh Calibration Episode Selection Result

```text
DATE = 2026-09-17
TASK = FRESH_CALIBRATION_EPISODE_SELECTION
SELECTION_METHOD = COVERAGE_BASED / NO_WEIGHTED_SCORE
HUMAN_VIDEO_USED_FOR_SELECTION = NO
HUMAN_GT_USED_FOR_SELECTION = NO
PRIVILEGED_GT_USED = NO
EVALUATION_SELECTED = NO
PARAMETER_SEARCH_EXECUTED = NO
AUDIT_RUN_GENERATED = NO
```

## 1. Authority

```text
CALIBRATION_PROTOCOL = FROZEN_v1.0
CALIBRATION_TARGET_N = 12
CALIBRATION_SEED_N = 6
CALIBRATION_FRESH_N = 6
SEARCH_GATE = CLOSED
```

Local Frozen Protocol and Google Drive Frozen Protocol are identical after newline normalization.

## 2. Dataset

- `SOURCE_DATASET_ID = robomimic_v15_can_mh`
- `SOURCE_HDF5_PATH = raw=C:\Users\95611\embody\1-dataset\robomimic\demo_v15.hdf5; low_dim=C:\Users\95611\embody\1-dataset\robomimic\low_dim_v15.hdf5`
- `TOTAL_EPISODE_COUNT = 300`
- `screening_config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630`
- `signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d`

Dataset HDF5 files were opened read-only through the existing Project 1 adapter.

## 3. Candidate Pool QA

```text
TOTAL_DATASET_EPISODES = 300
EXCLUDED_SEED = 6
EXCLUDED_EXISTING_EVALUATION_HOLD = 0
SCREENING_SUCCESS = 294
SCREENING_FAILED = 0
ELIGIBLE_FRESH_POOL = 294
SEED_OVERLAP = 0
```

Selection-only tertile thresholds were derived from the eligible pool:

- Length q33/q67: `151` / `216` frames
- Final-count q33/q67: `4` / `5`

## 4. Shortlist

| Episode | Length | Final | Gripper | Direction | Merged | G+D Merged | Short | Bucket | Reason |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `data/demo_150` | 236 | 6 | 3 | 3 | 3 | 3 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (236 frames), HIGH Final count (6), Gripper Primary=3, Direction Primary=3, Gripper+Direction merged=3, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_162` | 235 | 4 | 3 | 1 | 3 | 3 | 2 | PRESERVATION_CANDIDATE|DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (235 frames), LOW Final count (4), Gripper Primary=3, Direction Primary=1, Gripper+Direction merged=3, short segments=2; selected to preserve stable hard/merged behavior, and cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_213` | 149 | 3 | 3 | 0 | 3 | 3 | 2 | PRESERVATION_CANDIDATE | SHORT length (149 frames), LOW Final count (3), Gripper Primary=3, Direction Primary=0, Gripper+Direction merged=3, short segments=2; selected to preserve stable hard/merged behavior. |
| `data/demo_255` | 218 | 8 | 3 | 4 | 2 | 2 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (218 frames), HIGH Final count (8), Gripper Primary=3, Direction Primary=4, Gripper+Direction merged=2, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_260` | 230 | 9 | 3 | 4 | 3 | 1 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (230 frames), HIGH Final count (9), Gripper Primary=3, Direction Primary=4, Gripper+Direction merged=1, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_265` | 250 | 11 | 3 | 6 | 5 | 2 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (250 frames), HIGH Final count (11), Gripper Primary=3, Direction Primary=6, Gripper+Direction merged=2, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_269` | 233 | 7 | 3 | 3 | 3 | 2 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (233 frames), HIGH Final count (7), Gripper Primary=3, Direction Primary=3, Gripper+Direction merged=2, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_270` | 210 | 5 | 3 | 1 | 0 | 0 | 2 | PRESERVATION_CANDIDATE|DIRECTION_COVERAGE | MEDIUM length (210 frames), MEDIUM Final count (5), Gripper Primary=3, Direction Primary=1, Gripper+Direction merged=0, short segments=2; selected to preserve stable hard/merged behavior, and cover independent Direction behavior for later blind Human Review. |
| `data/demo_273` | 398 | 12 | 5 | 5 | 4 | 3 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (398 frames), HIGH Final count (12), Gripper Primary=5, Direction Primary=5, Gripper+Direction merged=3, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_280` | 259 | 7 | 3 | 3 | 2 | 0 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (259 frames), HIGH Final count (7), Gripper Primary=3, Direction Primary=3, Gripper+Direction merged=0, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_291` | 223 | 7 | 3 | 3 | 2 | 2 | 2 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (223 frames), HIGH Final count (7), Gripper Primary=3, Direction Primary=3, Gripper+Direction merged=2, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |
| `data/demo_293` | 217 | 7 | 3 | 3 | 2 | 2 | 1 | DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE | LONG length (217 frames), HIGH Final count (7), Gripper Primary=3, Direction Primary=3, Gripper+Direction merged=2, short segments=1; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity. |

## 5. Final Fresh 6

### `data/demo_150`

`selection_bucket = DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE`

LONG length (236 frames), HIGH Final count (6), Gripper Primary=3, Direction Primary=3, Gripper+Direction merged=3, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity.

### `data/demo_162`

`selection_bucket = PRESERVATION_CANDIDATE|DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE`

LONG length (235 frames), LOW Final count (4), Gripper Primary=3, Direction Primary=1, Gripper+Direction merged=3, short segments=2; selected to preserve stable hard/merged behavior, and cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity.

### `data/demo_213`

`selection_bucket = PRESERVATION_CANDIDATE`

SHORT length (149 frames), LOW Final count (3), Gripper Primary=3, Direction Primary=0, Gripper+Direction merged=3, short segments=2; selected to preserve stable hard/merged behavior.

### `data/demo_255`

`selection_bucket = DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE`

LONG length (218 frames), HIGH Final count (8), Gripper Primary=3, Direction Primary=4, Gripper+Direction merged=2, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity.

### `data/demo_260`

`selection_bucket = DIRECTION_COVERAGE|COMPLEXITY_CANDIDATE`

LONG length (230 frames), HIGH Final count (9), Gripper Primary=3, Direction Primary=4, Gripper+Direction merged=1, short segments=2; selected to cover independent Direction behavior for later blind Human Review, and cover long/high-boundary structural complexity.

### `data/demo_270`

`selection_bucket = PRESERVATION_CANDIDATE|DIRECTION_COVERAGE`

MEDIUM length (210 frames), MEDIUM Final count (5), Gripper Primary=3, Direction Primary=1, Gripper+Direction merged=0, short segments=2; selected to preserve stable hard/merged behavior, and cover independent Direction behavior for later blind Human Review.

## 6. Coverage Check

```text
PRESERVATION_CANDIDATE = 3
DIRECTION_COVERAGE = 5
COMPLEXITY_CANDIDATE = 4
length buckets covered = ['LONG', 'MEDIUM', 'SHORT']
boundary-count buckets covered = ['HIGH', 'LOW', 'MEDIUM']
quality buckets covered = ['BETTER', 'OKAY', 'WORSE']
gripper coverage = 6 episodes
merged coverage = 5 episodes with Gripper+Direction merged
```

## 7. Manifest

- Full screening: `C:\Users\95611\embody\4-Project2_data_value\outputs\g1_p3_calibration_selection\fresh_calibration_screening_v1_20260917.csv`
- Shortlist/selection CSV: `C:\Users\95611\embody\4-Project2_data_value\outputs\g1_p3_calibration_selection\fresh_calibration_selection_v1_20260917.csv`
- Frozen identity manifest: `C:\Users\95611\embody\4-Project2_data_value\outputs\g1_p3_calibration_selection\fresh_calibration_manifest_v1.json`

## 8. Leakage / Scope Check

```text
HUMAN_VIDEO_USED_FOR_SELECTION = NO
HUMAN_GT_USED_FOR_SELECTION = NO
PRIVILEGED_GT_USED = NO
EVALUATION_SELECTED = NO
PARAMETER_SEARCH_EXECUTED = NO
HUMAN_REVIEW_STARTED = NO
CANONICAL_GT_GENERATED = NO
AUDIT_RUN_GENERATED = NO
```

## 9. Tests

```text
selection tests = 5 PASS / 0 FAIL
audit web regression = 49 PASS / 0 FAIL
final semantics regression = 13 PASS / 0 FAIL
G1-P2 regression = 16 PASS / 0 FAIL
TOTAL = 83 PASS / 0 FAIL
```

Selection tests cover Seed exclusion, exactly-six/no-duplicate Fresh IDs, coverage constraints, deterministic selection, forbidden-field exclusion, Evaluation role unassigned, fixed config hash, and manifest round-trip validation.

The default Python runtime lacked `h5py`; screening was therefore executed with the existing audited `project1_robomimic_audit` environment required by the Project 1 adapter. No dependency was installed and the failed default-runtime attempt wrote no selection artifact.

## 10. Source Immutability

```text
SEED_EXPORT_UNCHANGED = PASS
  before/after = 8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7

OWNER_SQLITE_UNCHANGED = PASS
  before/after = 2b262a201fedba71d37366aa58f228a3d98903f29cf3cd1adc3870f7c9b51502

EXISTING_AUDIT_RUNS_UNCHANGED = PASS
  before/after = cb35e8d7138657ce2d0387e3f39e1139bc77e70489c38ef73bf4f0df2479f8aa

DATASET_RAW_HDF5_UNCHANGED = PASS
  before/after = 6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b

DATASET_LOW_DIM_HDF5_UNCHANGED = PASS
  before/after = c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7

FROZEN_PROTOCOL_UNCHANGED = PASS
  before/after = d75c05d7a0cad0ba2298225745314af7a313ad70e19d331b3b49205fb7e81c1a
```

## 11. Search Gate

```text
CALIBRATION_EPISODE_IDS = ['data/demo_0', 'data/demo_179', 'data/demo_230', 'data/demo_242', 'data/demo_278', 'data/demo_32', 'data/demo_150', 'data/demo_162', 'data/demo_213', 'data/demo_255', 'data/demo_260', 'data/demo_270']
12 selected total = YES
6 reviewed seed = YES
6 fresh unreviewed = YES
COMBINED_CANONICAL_GT = NOT_READY
SEARCH_GATE = CLOSED
```

## 12. Final Status

```text
G1_FRESH_CALIBRATION_EPISODE_SELECTION =
PASS_READY_FOR_BASELINE_AUDIT_RUN
MANDATORY_STOP = YES
```
