# P2-G3 — Argus-inspired Semantic Curation | Output Design v1

> **2026-10-13 Owner Freeze overlay**: **The output architecture is now frozen** as [Controlled Enum JSON + short note + frame evidence + deterministic QC](P2_G3_Structured_JSON_and_Evidence_Contract_Owner_Freeze_20261013.md). The sample `P2_G3_LABEL_V1_DRAFT` in this document and enum proposals remain **draft / not yet frozen**; retain their purpose as examples. Program injects trusted segment/Episode provenance outside model-owned payload. Invalid references and context-as-target events must fail closed. `JSON parse_ok` is not visual correctness.  

> Date: 2026-10-12  
> Status: `SCHEMA_PROPOSAL_PENDING_MINIMAL_TAXONOMY_FREEZE`  
> Intended repo path: `0-doc/10-design-review/P2_G3_Argus_Output_Design_v1_20261012.md`  
> All data/examples are illustrative, not real VLM results. No experiment is declared complete by this document.

## 1. Invariants / negative guarantees

1. Frozen `source_episode_id/segment_id/start_frame/end_frame` are unchanged; robot time indices are traceable.
2. Original VLM answers are immutable and separate from parser results, check flags and human corrections.
3. `label_qc_status` / `review_action` **never equals** robot-trajectory `training_disposition`. `AUTO_ACCEPT` means annotation may be used for indexing, not that training data is good.
4. `PROCESSING_ERROR/INVALID_INPUT` represent pipeline faults, **not** bad robot observations or examples.
5. `failed_grasp_candidate` is not human-verified failure; rare or duplicate tags are not training-utility labels.
6. Task outcome is Episode-level; no full Episode success inferred from a single local Segment without appropriately sampled Episode evidence.
7. No privileged simulator object GT, rewards/dones or other forbidden features in model requests or inferred validation logic.
8. Version exact prompt/model/renderer/schema, source hashes, independent GT manifests and controlled experiment IDs.

## 2. Immutable run layout (proposed)

```text
outputs/p2_g3_argus/<run_id>/
  run_manifest.json                  # source SHA, Argus reference SHA, model/schema/prompt, run mode
  dataset_split_manifest.csv         # episode-level development/evaluation isolation
  source_integrity_report.json       # forbidden fields, alignment & provenance checks
  evidence_packs.jsonl               # each ordered frame with role, time, image digest
  model_requests.jsonl               # model input identity, no secrets
  raw_model_responses.jsonl          # response or explicit transport/parser error
  structured_segment_labels.jsonl    # versioned segment semantics, original prediction
  episode_outcomes.jsonl             # only when whole-task evidence is available
  event_candidates.jsonl             # attempt / candidate failure / recovery links
  label_qc_findings.jsonl            # structural / semantic conflict evidence
  annotation_review_queue.csv        # AUTO_ACCEPT / REVIEW_REQUIRED / UNRESOLVED / ERROR
  annotation_human_reference.csv     # created independently; not auto-filled
  annotation_human_corrections.csv   # append-only human correction history
  semantic_event_index.csv           # queryable data asset; no training DROP/UPWEIGHT
  abenchmark_A_vision_only.jsonl     # only for evaluation runs
  bbenchmark_B_multimodal.jsonl      # only for evaluation runs
  benchmark_metrics.json             # human supported results and uncertainty
  benchmark_report.md                # cohort, bad cases, limitations and cost
  casebook.md                        # manually validated examples only
```

`<run_id>` is an immutable identity; changes to prompt, evidence frames, model revision, cohort or checks require a new identity or an explicit append-only replay parent link. Raw model responses can be reparsed without spending more model calls. Do not copy secrets into run manifests.

## 3. Input evidence pack (representative example)

```json
{
  "schema_version": "P2_G3_EVIDENCE_V1_DRAFT",
  "source_episode_id": "data/demo_0",
  "segment_id": "<frozen_actual_segment_id>",
  "segment_interval_frames": [40, 55],
  "segmentation_version": "<frozen_g1_version>",
  "task_text": "pick and place the can",
  "task_text_source": "dataset_task_metadata",
  "frames": [
    {"frame_index": 40, "timestamp_s": 2.0, "frame_role": "START", "image_sha256": "<digest>"},
    {"frame_index": 48, "timestamp_s": 2.4, "frame_role": "MIDDLE", "image_sha256": "<digest>"},
    {"frame_index": 55, "timestamp_s": 2.75, "frame_role": "END", "image_sha256": "<digest>"}
  ],
  "motion_summary": {
    "eef_path_length_m": 0.12,
    "gripper_transition_present": true,
    "action_magnitude_mean": 0.25,
    "action_semantics": "NORMALIZED_CONTROLLER_INPUT"
  },
  "allowed_input_fields_audit": "PASS",
  "rgb_provenance": {"renderer": "P1-RoboMimicStateRenderer", "overlay": false, "lossy_roundtrip": false},
  "evidence_pack_sha256": "<digest>"
}
```

Numeric fields, time samples and text above are **schematic** and MUST be replaced by verified source values. Vision-only A omits `motion_summary` in the actual model request; it may exist in the provenance store but must not leak into Prompt or image overlays.

## 4. VLM label, episode record, event candidates

### 4.1 Segment model prediction

```json
{
  "schema_version": "P2_G3_LABEL_V1_DRAFT",
  "run_id": "<run_id>",
  "source_episode_id": "data/demo_0",
  "segment_id": "<frozen_actual_segment_id>",
  "motion_phase": "grasp",
  "object_relation": ["gripper_around"],
  "object_description": "can",
  "events": [
    {
      "event_type": "grasp_attempt",
      "event_time_evidence": {"frame_indices": [48, 55], "time_resolution": "bounded_interval"},
      "event_outcome": "unclear",
      "evidence_quality": "insufficient"
    }
  ],
  "model_reported_confidence": null,
  "label_source": "vlm_auto",
  "model_revision": "<pin_exact_revision>",
  "prompt_sha256": "<digest>",
  "evidence_pack_sha256": "<digest>"
}
```

`grasp` here means the chosen segment behavior class, **not** a verified successful grasp. Raw response stored separately. No inference of force/contact GT from gripper state. Every output label must have allowed-enum/type validation; invalid labels go to explicit error/review.

### 4.2 Episode outcome

```json
{
  "source_episode_id": "data/demo_0",
  "task_outcome": "not_evaluated",
  "episode_evidence_coverage": "insufficient",
  "reason": "Only one local segment was evaluated"
}
```

### 4.3 Candidate event index

| Field | Value type | Semantics |
|---|---|---|
| `event_id`, `episode_id`, `segment_id` | string | Immutable provenance |
| `event_type` | enum | VLM-inferred attempt / event candidate |
| `event_start_frame`, `event_end_frame` | nullable integers | Evidence-bounded interval, not guessed exact contact time |
| `evidence_frame_ids` | array | Verified source frame indices |
| `event_outcome` | enum | Local success/failure/unclear; no promotion to episode outcome |
| `verification_status` | enum | `CANDIDATE_ONLY`, `HUMAN_VERIFIED`, `HUMAN_REJECTED`, `HUMAN_UNSURE` |
| `related_event_ids` | array | Attempt → recovery links when supported by later episode evidence |
| `visual_observability` | enum | `SUFFICIENT`, `OCCLUDED`, `OUT_OF_FRAME`, `INSUFFICIENT` |

## 5. Quality findings and review triage — different types

### 5.1 Check findings

```json
{
  "segment_id": "<frozen_actual_segment_id>",
  "check_id": "LABEL_LOGIC_V1",
  "severity": "REVIEW",
  "triggered": true,
  "finding": "Claimed full success without post-grasp object state evidence",
  "evidence_frame_ids": [48, 55],
  "deterministic_scope": "EVIDENCE_SUFFICIENCY_CANDIDATE",
  "raw_prediction_modified": false
}
```

The example finding is an **insufficient-evidence candidate** rather than a proven contradiction. Absolute rules such as time out of bounds and invalid source identity must be distinguished from probabilistic semantic heuristics. Checks do not mutate the VLM prediction.

### 5.2 Annotation review queue

| Field | Enum or contract |
|---|---|
| `annotation_review_status` | `AUTO_ACCEPT`, `REVIEW_REQUIRED`, `UNRESOLVED`, `PROCESSING_ERROR`, `INVALID_INPUT` |
| `annotation_review_reason[]` | `TIME_OUT_OF_RANGE`, `LABEL_LOGIC`, `MOTION_VISION_CONFLICT_CANDIDATE`, `EVIDENCE_INSUFFICIENT`, `MODEL_PARSE_ERROR`, etc. |
| `label_validation_status` | `VALID`, `INVALID_MODEL_OUTPUT`, `CONFLICT_CANDIDATE` |
| `review_priority` | optional ranking generated from *pre-registered* rules |
| `human_corrected_label` | never overwritten by model |
| `human_reviewed_at` | optional audit metadata |
| `training_disposition` | **`NOT_EVALUATED` throughout G3 v1** |

There is **no** `AUTO_ACCEPT → KEEP` mapping. Current Retrieval/curation manifest `triage_action KEEP/REVIEW` is not reused for this semantic annotation decision. Semantic candidate flag ≠ training disposal decision.

## 6. Independent human review and evaluation outputs

Human annotation reference must be collected in a blind run with independent labels: `human_phase`, `human_relation[]`, `human_event`, `human_event_outcome`, `human_evidence_quality`, `human_confidence_or_unsure`, `adjudication_status`, `source_episode_id`, `segment_id`, `reviewer_id` (pseudonymous). Record raw first pass, second pass subset, reconciliation and reason without looking at model predictions.

### 6.1 Metrics and denominator rules

| Metric | Purpose | Minimum reporting |
|---|---|---|
| `phase_accuracy_A/B`, `phase_macro_f1_A/B` | Paired effect of robot evidence | # Episodes/# Segments, per-class supports, confusion, paired difference with uncertainty |
| `relation_precision/recall` | Object relation semantics | human-positive counts and unsupported classes |
| `event_precision/recall`, localization tolerance | Failure/attempt/event candidate extraction | Mark `NOT_ESTIMABLE` if positives insufficient |
| `human_unsure_rate` | Observability and rubric stability | total, excluded and sensitivity accounting |
| `label_validity_rate` | Output validity | percent JSON/schema valid; excludes model transport failures by clear role |
| `auto_accept_coverage` | Proportion auto-indexed | paired with accepted-label accuracy |
| `accepted_label_accuracy` | Accuracy among accepted | report count and denominator, not only percentage |
| `review_error_yield_at_B` | Human-error discovery at fixed review budget B | compare random/simple baseline if triage uplift claimed |
| `additional_images`, `tokens`, `latency`, `cost` | Engineering trade-off | by exact experiment variant |
| `processing_failure_count` | Operational reliability | separate model/API/source failure from model semantic wrong |

Main v1 result can be A/B + valid semantic event index. Do not fabricate `C`, `D`, downstream ACT or multi-task generalization data.

## 7. Reviewable casebook and export contract

Each verified case has episode/segment/time identity, source clean images (no overlay for VLM), extra human-only temporal replay evidence clearly marked, robot EEF/gripper summary, original task source, original A/B responses, human reference/correction, label/check status, classification of errors (`G1_BOUNDARY`, `TEMPORAL_GAP`, `OBJECT_OCCLUSION`, `VLM_SEMANTIC`, `ACTION_ROLE`, `HUMAN_DISAGREEMENT`) and material revision/hash. Only label a failure as `HUMAN_VERIFIED` after an independent human annotation, not merely a VLM candidate.

**Deliverable CLI features**: query by episode/phase/related object/attempt/candidate/review status; export JSONL/CSV with provenance and no data deletion. A README should clearly state which Argus patterns were referenced, which modules were adapted or copied, the pinned upstream SHA/license, and the proven versus unproven outcomes.

## 8. Downstream hand-off (future, not present G3 training action)

`semantic_event_index` may later feed P3 or a separate policy-data experiment **only after** defining a lawful training intervention (e.g., review-conditioned sampling/annotation text). That separate experiment must perform a tiny clean-policy baseline to determine sufficient training steps and evaluation reliability before full paired ACT/VLA runs. G3 v1 **stops at independently evaluated annotation and curation candidates**.
