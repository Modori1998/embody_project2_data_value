# Project 2 G1-P3 Rule Family A Displacement Preparation Result

```text
DATE = 2026-09-18
DOCUMENT_STATUS = ANALYSIS_PREPARATION_RESULT
PREP_ID = g1_rule_family_a_prep_20260918_173501
A_PREP_EVIDENCE_STATUS = READY_FOR_RULE_FAMILY_A_REVIEW
DETECTOR_MODIFIED = NO
PARAMETER_SEARCH_EXECUTED = NO
THRESHOLD_SWEEP = NO
DISPLACEMENT_CUTOFF_SELECTED = NO
STAGE_A_EXECUTED = NO
```

## Input Identity

```text
baseline_run_id = g1_calibration_20260918_141032_781e5d8b
baseline_score_id = g1_baseline_score_20260918_155714_42295cc6
canonical_gt_snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
stage_a0_analysis_id = g1_stage_a0_20260918_162418_7cbf826e
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
```

## Displacement Semantics

`pre_displacement_m = ||sum(delta_xyz[t-8:t])||₂`; `post_displacement_m = ||sum(delta_xyz[t:t+8])||₂`。
`delta_xyz` 是 `obs/robot0_eef_pos` 的 backward difference，单位 meter；窗口在 Episode 边缘 clip 到 `[0,n)`。
这与 `direction_change_evidence` 使用相同左右窗口。字段为 `ANALYSIS_DERIVED_FIELD`，不写回 P1。

```text
SIGNAL_CONTRACT_CHANGE = NO
```

## Cohort

```text
VALID_DIRECTION = 17 (Seed=6, Fresh=11)
DIRECTION_FP = 9 (MODE_01=3, MODE_02=3, MODE_03=1, UNASSIGNED=2)
NON_DIRECTION_FP = 1 (outside Rule Family A scope)
```

## Marginal Distributions

### pre_displacement_m

- VALID: n=17, min=0.020009, q25=0.032586, median=0.040708, q75=0.047502, max=0.099797, mean=0.045525
- FP: n=9, min=0.010488, q25=0.017944, median=0.022661, q75=0.027872, max=0.057515, mean=0.025475
- Range overlap: `YES`; IQR overlap: `NO`

### post_displacement_m

- VALID: n=17, min=0.017244, q25=0.028948, median=0.034318, q75=0.046074, max=0.084162, mean=0.039010
- FP: n=9, min=0.006819, q25=0.011427, median=0.012475, q75=0.020726, max=0.039503, mean=0.018150
- Range overlap: `YES`; IQR overlap: `NO`

### min(pre, post)

- VALID: n=17, min=0.017244, q25=0.026288, median=0.031255, q75=0.042484, max=0.084162, mean=0.037125
- FP: n=9, min=0.006819, q25=0.010488, median=0.012475, q75=0.018023, max=0.039503, mean=0.017516
- Range overlap: `YES`; IQR overlap: `NO`

所有三个字段均为 range overlap，但 ALL cohort 的 IQR 不重叠。存在 FP 大位移反例和 VALID 低位移反例，不能由本报告推导 cutoff。

## MODE Facts

- `MODE_01`: demo_242@41 pre=0.057515, post=0.039503, min=0.039503; demo_242@60 pre=0.018023, post=0.020726, min=0.018023; demo_242@78 pre=0.027872, post=0.014685, min=0.014685
- `MODE_02`: demo_278@83 pre=0.022661, post=0.006819, min=0.006819; demo_278@105 pre=0.017944, post=0.012014, min=0.012014; demo_278@125 pre=0.013311, post=0.009448, min=0.009448
- `MODE_03`: demo_242@136 pre=0.027274, post=0.012475, min=0.012475
- `UNASSIGNED`: demo_162@211 pre=0.034185, post=0.036250, min=0.034185; demo_255@116 pre=0.010488, post=0.011427, min=0.010488

MODE_03 的 primary layer 保持 `CONSOLIDATION`；这里只记录其 displacement context。

## Lowest VALID Counterexamples

| rank | event | package | pre | post | min | evidence | run_length |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | demo_242@224 | SEED | 0.020009 | 0.017244 | 0.017244 | 2.295841 | 8 |
| 2 | demo_255@14 | FRESH | 0.047502 | 0.018559 | 0.018559 | 2.212344 | 7 |
| 3 | demo_260@75 | FRESH | 0.033963 | 0.019910 | 0.019910 | 1.623565 | 6 |
| 4 | demo_255@75 | FRESH | 0.024536 | 0.037290 | 0.024536 | 1.581201 | 7 |
| 5 | demo_278@52 | SEED | 0.026288 | 0.029863 | 0.026288 | 1.532755 | 6 |

## Seed / Fresh Preparation Finding

Seed 与 Fresh 中，三个 displacement 字段的 VALID median 均高于 FP median；但 Fresh FP 只有 2 条，且 `demo_162@211` 是较大 displacement FP。

```text
SEED_PATTERN = VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP
FRESH_PATTERN = VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP
CONSISTENCY = INSUFFICIENT
INSUFFICIENT_FRESH_NEGATIVE_EVIDENCE = YES
```

## Rule Shape Evidence

- `both-side requirement｜双侧要求`：pre/post 各自保留方向性，能解释“运动后停住”或“几乎从静止起步”的哪一侧不足，但需要两个条件。
- `min(pre,post) requirement｜较弱侧位移要求`：与“双侧都充分”等价地表达最弱运动侧，单变量、物理解释更紧凑；本报告不选择阈值。

## Robustness

定性 leave-one-event-out 只检查 `VALID median > FP median` 是否由单点驱动，不拟合 cutoff。结果记录在 `rule_family_a_meta.json`。

## Immutability

```text
BASELINE_RUN_UNCHANGED = PASS
BASELINE_SCORE_UNCHANGED = PASS
CANONICAL_GT_UNCHANGED = PASS
STAGE_A0_ARTIFACT_UNCHANGED = PASS
SEED_EXPORT_UNCHANGED = PASS
FRESH_EXPORT_UNCHANGED = PASS
OWNER_SQLITE_UNCHANGED = PASS
PROTOCOL_UNCHANGED = PASS
DATASET_UNCHANGED = PASS
```

## Status

```text
A_PREP_EVIDENCE_STATUS = READY_FOR_RULE_FAMILY_A_REVIEW
```

This result prepares evidence only. It does not freeze a rule family or displacement threshold.
