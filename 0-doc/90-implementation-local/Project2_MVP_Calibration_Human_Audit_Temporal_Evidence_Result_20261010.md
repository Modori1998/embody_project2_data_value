# Project 2 MVP Calibration Human Audit Temporal Evidence Result

Date: 2026-10-10

Task: `ADD_TEMPORAL_CONTEXT_TO_CALIBRATION_HUMAN_AUDIT`

Result: `PASS_READY_FOR_CALIBRATION_BLIND_HUMAN_AUDIT`

> Recovery note: this task was executed across an interrupted run. The original
> MuJoCo segment-GIF render process was still alive at recovery start and was
> allowed to finish in place (no second render was started). Validation below was
> performed on the completed output.

## Authority and inputs

- Git base at execution: `8f7d362b3dea8acd9ea53c128d675ff1755fe236`
- Frozen temporal-evidence addendum: `Project2_MVP_Human_Audit_Temporal_Evidence_Addendum_FROZEN_v1_20261010.md` (`FROZEN_v1`)
- Formal Stage 1 run: `outputs/mvp_core_retrieval_formal/mvp_core_retrieval_formal_stage1_20261009`
- New temporal audit run ID: `calibration_blind_audit_temporal_v1_20261010`
- Output package: `outputs/mvp_core_retrieval_human_audit/calibration_blind_audit_temporal_v1_20261010`
- Renderer: P1 `RoboMimicStateRenderer` direct `STATE_t` render (`MUJOCO_GL=wgl`)
- RGB contract: `MVP_RGB_SOURCE_AND_ALIGNMENT_CONTRACT_v1`

The Frozen Core Retrieval Protocol, manifest, G1 configuration, M2 semantics, and
RGB contract were not modified.

## Segment GIF materialization

- Required unique segments (audit pairs): 71
- Generated and validated segment GIFs: 71 / 71 PASS
- Source episodes involved: 41
- Sampling: uniform downsample to `target_fps = 10.0` (`frame_duration_ms = 100`),
  inclusive `[start_frame, end_frame]`, first and last frames always retained
- Frames per segment: min 3, max 69, mean 14.9; total sampled frames: 1060
- GIF sizes: 43.1 KB – 999.0 KB
- Per-GIF checks: file present, size > 0, valid `GIF` format, decodable, frame count
  equals `sampled_frame_count`, sampled indices match `segment_input_manifest.csv`,
  `sha256` matches `segment_gif_manifest.json`
- GIFs contain no text overlay and are never used as a retrieval input
  (`overlay_applied = false`, `retrieval_input = false`)

## Reviewer-visible package

- Interactive page: `index.html` (derived from the Stage 1 blind audit package)
- Reviewer-visible audit items: 95
- Unique audit pairs: 83
- Hidden repeats: 12
- Query GIF references: 190 (2 per item); 9 unique query segments, 62 unique candidate segments
- Five relevance options preserved: `RELEVANT`, `PARTIAL`, `NOT_RELEVANT`, `BAD_SEGMENT`, `UNSURE`
- Existing `START / MIDDLE / END / GRIPPER_EVENT` keyframes remain visible alongside each GIF
- Blind order identical to the Stage 1 audit order (`audit_order_unchanged = true`)
- Retrieval method, similarity score, method rank, copy index, and hidden-repeat status
  are not present in the reviewer payload or page (`blind_fields_exposed = false`)

## Frozen Retrieval integrity

Protected Frozen Retrieval artifacts were re-hashed after page assembly and are unchanged:

| File | SHA256 |
|---|---|
| `calibration_motion_top5.csv` | `31275fc41dbf5477746f4b4e6c5ce2693527f270fdb5bff38ddf989ff538723b` |
| `calibration_visual_top5.csv` | `b3fdb38b85d6033e9ef50a4a51618e6e8d7262e144087d277a2346ccd3c1cad0` |
| `calibration_query_manifest.csv` | `bbd00574d269c5b350dd17809a39643c5dd15b464cbd4ee30f227bbc37f4c8ed` |
| `final_query_manifest.csv` | `987802e4b84ccf665b652a30f03aaa06f0c12b25916d4cb85d7842a812944631` |

No Formal M2, SigLIP2, Motion embedding, FAISS, or Calibration Retrieval step was re-run.

## Tests

- Temporal audit targeted tests: 2/2 PASS
- Related MVP regression (temporal audit, audit UI, core retrieval formal, RGB contract,
  core retrieval smoke, M2): 23/23 PASS

## Scope isolation and gate

- Retrieval rerun: NO
- Human relevance labels started: NO
- Final Retrieval executed: NO
- P@5 computed: NO
- GO / CONDITIONAL / STOP judgment: NOT_MADE

```text
TEMPORAL_EVIDENCE_ADDENDUM = FROZEN_v1
EXPECTED_SEGMENT_GIFS = 71
GENERATED_SEGMENT_GIFS = 71
MISSING_SEGMENT_GIFS = []
AUDIT_HTML = PASS
CALIBRATION_AUDIT_ITEMS = 95
AUDIT_ORDER_UNCHANGED = YES
METHOD_SCORE_RANK_HIDDEN = YES
HIDDEN_REPEAT_STATUS_HIDDEN = YES
RETRIEVAL_RERUN = NO
HUMAN_LABELS_STARTED = NO
CALIBRATION_HUMAN_AUDIT_EVIDENCE = TEMPORAL_CONTEXT_READY
NEXT = CALIBRATION_BLIND_HUMAN_AUDIT
```
