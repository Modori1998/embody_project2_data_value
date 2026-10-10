# Project 2 MVP Core Retrieval Formal Stage 1 Calibration Result

Date: 2026-10-09

Task: `FORMAL_CORE_RETRIEVAL_STAGE1_CALIBRATION_EXECUTION`

Result: `PASS_READY_FOR_CALIBRATION_BLIND_HUMAN_AUDIT`

## Authority and runtime

- Git base: `8846649b9f121595595e61ed02590310d1decc1f`
- Frozen Core Retrieval Protocol identity: PASS
- Frozen Protocol Addendum identity: PASS
- Frozen 63-Episode Manifest identity: PASS
- Formal run ID: `mvp_core_retrieval_formal_stage1_20261009`
- Model: `google/siglip2-base-patch16-224`
- Exact revision: `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`
- Loader: config-driven `AutoModel` (`SiglipModel`)
- Processor: `SiglipProcessor`, `use_fast=false`
- Transformers: `4.56.2`
- Torch: `2.14.0+cpu`
- Device / dtype: CPU / `torch.float32`

Frozen Protocol, Addendum, Manifest, G1 configuration, M2 semantics, and RGB contract were not modified.

## Formal 63-Episode materialization

- Episodes: 63/63 PASS
- Candidate Bank Episodes: 36
- Calibration Query Episodes: 9
- Final Query Episodes: 18
- Total segments: 357
- Keyframe rows / unique lossless RGB files: 1071 / 1071
- Multi-role frames: 188
- Frozen G1 identity: PASS
- RGB contract identity: PASS
- M2 computed sanity: all checks PASS

## Formal representation and indices

- Motion version: `MVP_M4_MOTION_REP_V1`
- Motion dimension: 17
- Formal scaler role: `FORMAL_CANDIDATE_BANK_SCALER`
- Scaler fit source: Candidate Bank only
- Scaler fit Episodes / segments: 36 / 203
- Visual version: `MVP_M4_SIGLIP2_REP_V1`
- Visual dimension: 768
- Motion/Visual vectors finite: PASS
- Motion and Visual Candidate IDs aligned: PASS
- Candidate segment count: 203
- Motion `FAISS IndexFlatIP`: PASS
- Visual `FAISS IndexFlatIP`: PASS
- Calibration/Final Query segments in Candidate indices: NO

## Deterministic Query Segment Selection

Calibration realized balance: TRUE=4, FALSE=5.

Calibration Query Segment IDs:

```text
demo_189-S0004
demo_148-S0005
demo_5-S0003
demo_249-S0001
demo_215-S0003
demo_294-S0003
demo_297-S0002
demo_200-S0009
demo_65-S0004
```

Final realized balance: TRUE=9, FALSE=9.

Final Query Segment IDs were selected and recorded, but Final Retrieval was not executed:

```text
demo_139-S0001
demo_186-S0001
demo_104-S0001
demo_116-S0003
demo_45-S0005
demo_37-S0002
demo_115-S0002
demo_156-S0001
demo_149-S0001
demo_197-S0005
demo_118-S0004
demo_237-S0002
demo_88-S0006
demo_55-S0003
demo_281-S0004
demo_250-S0001
demo_279-S0002
demo_283-S0008
```

## Calibration Retrieval and blind package

- Motion Top-5: 9/9 PASS
- Visual Top-5: 9/9 PASS
- Cross-Episode rule: PASS
- Unique blind audit pairs after method union/dedup: 83
- Deterministically selected hidden repeat pairs: 12
- Reviewer-visible audit items including repeat copies: 95
- Blind pair deduplication: PASS
- Reviewer CSV hides method, similarity, method rank, copy index, and repeat status: PASS
- Minimal lossless-keyframe HTML audit asset: generated
- Interactive reviewer UI derived package: `outputs/mvp_core_retrieval_human_audit/calibration_blind_audit_ui_v1_20261010`
- Interactive controls: five relevance choices, automatic browser-local persistence, previous/next navigation, current/completed/remaining progress, and filled CSV export
- Human labels: NOT_STARTED

Retrieval scores are retained only in method-specific internal CSV files. No score or method identity is exposed in the reviewer-visible CSV or HTML.

## Tests

- Formal Stage1 targeted tests: 5/5 PASS
- Core Retrieval smoke regression: 4/4 PASS
- M2 targeted regression: 8/8 PASS
- RGB contract regression: 3/3 PASS

Covered deterministic TRUE/FALSE assignment, fallback, segment selection, 4/5 and 9/9 balance, hidden-repeat selection, blind ordering/method hiding, Candidate-only source isolation, and absence of Final Retrieval.

## Scope isolation and gate

- Final Retrieval executed: NO
- Human Audit executed: NO
- P@5 computed: NO
- VLM / DINOv2 / Late Fusion executed: NO
- GO / CONDITIONAL / STOP judgment: NOT_MADE

```text
CORE_RETRIEVAL_FORMAL_REPRESENTATION = PASS
FORMAL_63_EPISODE_MATERIALIZATION = PASS
CALIBRATION_RETRIEVAL = READY_FOR_HUMAN_AUDIT
HUMAN_RELEVANCE_CALIBRATION = NOT_STARTED
FINAL_RETRIEVAL = BLOCKED_PENDING_CALIBRATION_HUMAN_AUDIT
NEXT = CALIBRATION_BLIND_HUMAN_AUDIT
```
