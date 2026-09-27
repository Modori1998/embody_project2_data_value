# Project 2 / G1-P4 Evaluation Manifest Preparation Result

Date: 2026-09-27

Status: `READY_FOR_DESIGN_OWNER_EVALUATION_MANIFEST_REVIEW`

Git base: `45c439c6b33108ae045c1d84d5e47d48277a22b0`

Immutable preparation run: `g1_p4_eval_manifest_prep_20260927_203656_a262340e`

## 1. Scope

This task prepared candidate Evaluation manifests and audited historical-set disjointness only. It did not execute the Frozen Config, segmentation, scoring, Evaluation GT construction, Human Audit, or Audit Web.

```text
EVALUATION_MANIFEST_FROZEN = NO
FORMAL_EVALUATION_RUN_ALLOWED = NO
EVALUATION_EPISODE_COUNT = OWNER_DECISION_PENDING
```

## 2. Dataset Identity and Readability

```text
dataset_id = robomimic_v15_can_mh
total_dataset_episodes = 300
eligible_evaluation_pool = 268
unreadable_or_schema_invalid = 0
sample_hz = 20.0

demo_v15.hdf5 SHA256 = 6f5a0e96fc375468ae19ccac86a6dee3b4d3862ef0fe37ca2d02e93d9046fe6b
low_dim_v15.hdf5 SHA256 = c4a34c837913446d295c6ca38f2b31888d69812198478af470ecb84a99e9f7d7
```

The existing Project 1 Can/MH adapter and frozen Source Contract were reused. Every source episode was checked read-only for required formal fields, temporal alignment, minimum technical length, and compatible shapes. No detector outputs were generated.

## 3. Historical Episode Reconstruction

Historical identities were extracted automatically and cross-checked across official manifests, exports, and diagnostic artifacts.

| Cohort | Episodes |
|---|---:|
| Exploratory | 6 |
| Calibration Seed | 6 |
| Calibration Fresh | 6 |
| Calibration Combined | 12 |
| Design Diagnostic | 20 |
| Historical unique union | 32 |

The Exploratory and Calibration Seed sets are intentionally the same six episodes. Calibration Combined equals Seed union Fresh. The official 20-episode Diagnostic manifest, selection artifact, and review-history episode sets agree exactly. No historical provenance conflict was found.

All 32 historical episodes were deterministically excluded before candidate ranking and are recorded under `skipped_for_historical_overlap`.

## 4. Selection Algorithm

The primary proposal algorithm is:

```text
1. Exclude every historical Exploratory, Calibration, or Diagnostic episode.
2. Exclude only technically unreadable or schema-invalid episodes.
3. Sort eligible episodes by (frame_count ASC, episode_id ASC).
4. Divide rank order into SHORT / MEDIUM / LONG terciles.
5. Within each tercile, sort by:
   SHA256("G1P4_EVAL_MANIFEST_CANDIDATE_V1|<episode_id>") ASC,
   then episode_id ASC.
6. Round-robin SHORT, MEDIUM, LONG to form one deterministic nested ranking.
7. Take prefixes of 12, 24, and 36 as workload proposals only.
```

The rank terciles contain 89 SHORT, 89 MEDIUM, and 90 LONG episodes. SHORT ends at 146 frames and MEDIUM ends at 203 frames. A separate pure global episode-ID hash proposal is also emitted for Owner comparison.

The three option counts are not frozen. They provide concrete Small/Medium/Large workload choices while preserving one sampling rule and `Small ⊂ Medium ⊂ Large`.

## 5. Candidate Options

The manual workload estimate uses only episode count and duration:

```text
estimated minutes = 2 × video duration minutes + 2 minutes navigation/setup per episode
```

It does not use predicted boundary count, detector performance, difficulty, labels, FP/FN, or error modes.

### Option Small

```text
episode_count = 12
total_frames = 2196
total_duration = 109.8 seconds (1.83 minutes)
estimated_manual_audit_workload = 27.66 minutes
```

Episode IDs:

```text
data/demo_129
data/demo_176
data/demo_91
data/demo_18
data/demo_275
data/demo_234
data/demo_3
data/demo_178
data/demo_94
data/demo_10
data/demo_224
data/demo_58
```

### Option Medium

```text
episode_count = 24
total_frames = 4432
total_duration = 221.6 seconds (3.6933 minutes)
estimated_manual_audit_workload = 55.3867 minutes
```

It contains all Small episodes plus:

```text
data/demo_141
data/demo_161
data/demo_262
data/demo_121
data/demo_253
data/demo_284
data/demo_20
data/demo_207
data/demo_85
data/demo_46
data/demo_238
data/demo_282
```

### Option Large

```text
episode_count = 36
total_frames = 6622
total_duration = 331.1 seconds (5.5183 minutes)
estimated_manual_audit_workload = 83.0367 minutes
```

It contains all Medium episodes plus:

```text
data/demo_42
data/demo_156
data/demo_83
data/demo_181
data/demo_225
data/demo_98
data/demo_139
data/demo_274
data/demo_277
data/demo_188
data/demo_164
data/demo_250
```

## 6. Disjointness Audit

Each proposed option independently reports:

```text
OVERLAP_WITH_EXPLORATORY = 0
OVERLAP_WITH_CALIBRATION_SEED = 0
OVERLAP_WITH_CALIBRATION_FRESH = 0
OVERLAP_WITH_CALIBRATION_COMBINED = 0
OVERLAP_WITH_DESIGN_DIAGNOSTIC = 0
```

```text
DISJOINTNESS_AUDIT = PASS
SMALL_SUBSET_MEDIUM = YES
MEDIUM_SUBSET_LARGE = YES
```

## 7. Leakage Audit

```text
human_label_used = false
evaluation_gt_used = false
frozen_config_score_used = false
fp_fn_used = false
error_mode_used = false
result_based_cherry_pick_used = false
formal_evaluation_executed = false
human_audit_started = false
LEAKAGE_AUDIT = PASS
```

Historical Calibration and Diagnostic artifacts were read only to extract and cross-check episode identity for exclusion. Human decisions, labels, P12/C12 values, detector outcomes, boundary quality, FP/FN, and error modes did not participate in eligibility or ordering.

## 8. Owner Gate

The artifacts are reproducible manifest candidates, not a Frozen Evaluation Manifest. The Design Owner must still choose episode count, IDs, manifest version, and provenance before formal evaluation is allowed.

```text
EVALUATION_MANIFEST_FROZEN = NO
FORMAL_EVALUATION_RUN_ALLOWED = NO
READY_FOR_DESIGN_OWNER_EVALUATION_MANIFEST_REVIEW = YES
```
