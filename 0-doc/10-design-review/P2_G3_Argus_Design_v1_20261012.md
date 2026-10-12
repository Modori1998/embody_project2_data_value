# P2-G3 — Argus-inspired Multimodal Semantic Annotation & Curation | Design v1

> Date: 2026-10-12  
> Decision: **OWNER_DIRECTION_APPROVED, IMPLEMENTATION_NOT_STARTED**  
> Repository: `Modori1998/embody_project2_data_value`  
> Intended location: `0-doc/10-design-review/P2_G3_Argus_Design_v1_20261012.md`  
> Governance: this proposal and its scope-change overlay take effect on `main` **only after review/merge**. `DRAFT` enumerations, sample sizes and numeric acceptance thresholds require a separate freeze before formal inference.  
> References: `0-doc/Project2_MVP_SSOT_20261008.md`, `0-doc/Project_2_Engineering_Design_Master_v1_20260914.md`, `0-doc/02_robot_demonstration_mining_autolabel_design.md`.

## 0. Executive decision and terminology

**Project name**: Multimodal Robot Demonstration Semantic Annotation & Curation (多模态机器人示范语义标注与数据筛选). The product-level output is a queryable, traceable annotation and review dataset, **not** a global episode quality score.

- **Argus-inspired**: use the public Argus architecture as a reference; implement a source-specific, independently owned P2 pipeline, with attribution and license compliance. Do not claim copied open-source code as wholly original.
- **VLM / Vision-Language Model**: 视觉语言模型；首版仅做推理，不微调。
- **Semantic event**: 语义事件；指可见的动作阶段、物体交互、尝试结果、失败/恢复候选。
- **Evidence-grounded**: 证据关联；每一条判断能回到时间、原图、合法机器人状态和任务来源。
- **QC of annotations**: 标签质量控制，不等于“原始轨迹应该被删除”。
- **Abstention**: 拒绝自动确认；证据不足时输出 `UNRESOLVED`，不能强猜。

### 0.1 Approved scope change (overrides execution priority, not frozen evidence)

| Topic | Previous SSOT | Owner v1 decision | Preservation boundary |
|---|---|---|---|
| P2 priority | Retrieval-first Core | **G3 Semantic Annotation is the new active line** | No retrospective reinterpretation of Retrieval |
| Retrieval v1 | 18 final queries ready | **HOLD_BY_OWNER, NOT_EXECUTED** | Freeze query/candidate/rubric/feature/inference inputs & results; no formal P@5 claim |
| G3 entry | Conditional after retrieval gate | **Independent authorized track after scope-change merge and G3 prerequisites** | Do not implicitly mark Retrieval GO or close old Gate |
| G3 goal | Minimal semantic labels | **Argus core capability reproduction on RoboMimic Can/MH** | Need honest coverage matrix: reproduced, adapted, excluded |
| Ablation | A/B/C/D full comparison | **A/B mandatory; C/event frames and D/checks evaluated only when material failure modes warrant them** | Check-system baseline still required to claim review-efficiency gain |
| Downstream ACT | Optional exploration | **Outside G3 v1** | No model utility or success-rate uplift claims |

**No forced Final Retrieval closeout is required before G3.** This is an explicit Owner change to the earlier sequence. Read-only preservation of the pre-HOLD state and a provenance record are required.

## 1. Differentiation against P1 and product value

| Stream | Evaluates | Primary signals | Output & downstream business meaning |
|---|---|---|---|
| P1-M07 | Motion execution efficiency/stability | EEF movement, duration, pause, oscillation, jerk, episode and frame-local QC | Kinematic QC scores/tags and candidate training weights |
| P1-M11 | Observation integrity under degradation | RGB quality/IQA, distortion type and severity | Visual corruption detection and policy-input quality |
| **P2-G3** | **Task semantics, observed object interaction, annotation trustworthiness** | **RGB + timestamp-aligned gripper/EEF/action + recorded task context** | **Semantic event index, label-error candidates, failure/recovery candidates and human review/export** |

**Negative controls:** Smooth motion ≠ successful grasp; clean image ≠ correct object interaction; VLM hallucination ≠ poor original data. Failed/recovered attempts can be valuable and are not automatically discarded. No `DROP`, `REJECT`, `UPWEIGHT` or claimed training utility in G3 v1.

Primary user story: given thousands of robotic episodes, find *grasp attempts with uncertain object motion* or *human-verified failed-then-recovered manipulation*, inspect time/frame evidence, correct annotations and export event-level metadata. P2 adds semantic organization beyond pure embedding neighbors.

## 2. Implementation target: reproduce Argus's essential capabilities

Source: `https://github.com/Pantheon-Industries-Inc/argus` (Apache-2.0; respect LICENSE/THIRD_PARTY_NOTICES where relevant). Pin the specific upstream SHA at implementation. In v1 scope, **functional reproduction** means these seven vertical slices work on P2 source:

| Capability | Argus source inspiration | P2 deliverable | Scope |
|---|---|---|---|
| 1. Source ingest & provenance | `prepare/*`, `label/source_eligibility.py` | Reuse P2 RoboMimic reader; Episode/Segment/frame IDs, source identity and legal field roles | Must |
| 2. Evidence sampling | `label/episode.py`, `label/frames.py`, `label/route.py` | Clean keyframes, gripper event and ordered timestamps, visibility audit; optional event-adjacent frames | Base must; adaptive optional |
| 3. Structured semantic annotation | `label/prompts.py` | Controlled action phase, object relation, observed event/result, uncertain | Must |
| 4. Task goal and progress | `label/prompts.py` | Episode-level goal/outcome evidence when observable; segment-level local event; explicit missing/unclear | Must with evidence limits |
| 5. Error/recovery record | `label/prompts.py` | Event candidates and links between attempt/outcome/recovery across segments | Basic attempt must; robust recovery optional |
| 6. Validation and replay | `checks/label_consistency.py`, `checks/*`, labeling run records | Parser/time/provenance checks; raw responses, run identity, reparse without re-calling model | Must |
| 7. Review & export | `review/*`, `board/*` | Minimal episode timeline + evidence + label correction + JSONL/CSV export; reuse existing P2 audit assets | Must |

**Excluded in v1**: complete Argus UI parity, hosted deployments, multi-rig inference, multi-camera synchronization, depth/force/tactile, LeRobot/MCAP generic converter, exhaustive session/ego schema, full dataset-wide inference, joint policy/VLA training. No claim of those capabilities.

**Attribution**: `README` includes repo/revision/license, per-module reference map, which code is copied vs adapted vs independently written, and copyright notices for any copied elements. The outcome may fairly be called “independently implemented P2-specific Argus-inspired pipeline”, not “invented Argus”.

## 3. Input contract and information boundary

### 3.1 Source and strict alignment

Primary: RoboMimic v1.5 Can/MH (300 episodes nominal; actual eligibility must be audited). G1 Frozen Segments are **immutable units** with `segment_id`, `source_episode_id`, `start_frame`, `end_frame`, boundary provenance and version. M2 `START/MIDDLE/END/GRIPPER_EVENT` keyframes and movement summaries are reused, not recalculated under a new definition.

Clean RGB contract: P1 `RoboMimicStateRenderer`, `MODEL_RGB[t]=render(STATE_t)`, **no text overlay, no audit MP4 extraction, no lossy video roundtrip**. `RGB[t] ↔ Proprio[t] ↔ Action[t]` must use the same source frame/time index; do not derive labels from simulator privileged fields.

Permitted model features (subject to exact P1 contract): clean RGB, task/instruction text with source, EEF pose/derived deltas, gripper opening/state, recorded 7D action with correct `NORMALIZED_CONTROLLER_INPUT` meaning. **Do not interpret action magnitude as physical velocity/force.** Exclude `Can_pos`, `Can_to_EEF`, object-position GT, `reward`, `done`, `next_obs`, privileged simulator states; only `STATE_t` may be used internally by the renderer. Better/Okay/Worse source buckets are not semantic GT or success labels.

Record frame RGB hash, renderer/camera/resolution/version, action-state schema, timestamps/frame indices, task-description origin, model/prompt/schema hashes and coverage. If recorded natural-language instruction is absent, annotate `task_text_source=dataset_task_metadata`, never silently pass VLM-generated task descriptions as ground truth.

### 3.2 Context, granularity and temporal coverage

- **Segment**: primary `motion_phase`, local object relation and attempt evidence. Do not assign full task success solely from an isolated segment.
- **Episode**: task completion and attempt→recovery chronology, only when temporal input actually spans the required portions. A three-frame segment is insufficient to evaluate entire-episode success.
- **Neighbor context**: permitted as separately named contextual frames under a pre-registered rule; cannot silently modify frozen G1 boundaries.
- **Timestamp uncertainty**: sparse frames can support intervals or observation points but not fabricated millisecond contact times.
- **Missing object visibility**: return `insufficient` / `uncertain`, not `failed_grasp` by default.

### 3.3 VLM

Base model: `Qwen3-VL-8B-Instruct`, as nominated in current P2 SSOT; before inference pin model repository ID, exact revision/weights, service version, tokenizer/preprocessing, GPU/runtime, prompt SHA, temperature, token limit and retry policy. Keep **one VLM** for v1; no invisible second-model fallback. Model service/network failures remain `PROCESSING_ERROR`, never sample-quality defects. Raw model output always kept; parser must never rewrite an illegal class to a legal class silently.

## 4. Semantic taxonomy **proposal** — separate Owner freeze required

Avoid blindly lifting Argus's freeform ontology: P2 requires controlled categories and valid human GT.

| Field | Draft allowed values | Scope / interpretation |
|---|---|---|
| `motion_phase` | `approach`, `grasp`, `lift`, `transport`, `place`, `retract`, `idle`, `other`, `uncertain` | Segment dominant visible action; *recovery* is a cross-segment episode event, not automatically phase |
| `object_relation` | `approaching`, `gripper_around`, `moving_with_gripper`, `resting_after_release`, `separating`, `none_observed`, `uncertain` | Observed visual relationship; multi-label only where not contradictory |
| `event_type` | `grasp_attempt`, `release_attempt`, `object_motion`, `failed_grasp_candidate`, `slip_candidate`, `recovery_candidate`, `none_observed`, `uncertain` | Candidates; positive verified failure only after independent human audit |
| `event_outcome` | `observed_success`, `observed_failure`, `unclear`, `not_applicable` | Scoped to stated local event, not entire episode |
| `task_outcome` | `success`, `partial`, `failure`, `success_then_undone`, `unclear`, `not_evaluated` | Episode-level *only*; `not_evaluated` if insufficient coverage |
| `evidence_quality` | `sufficient`, `insufficient`, `occluded`, `out_of_frame`, `not_applicable` | Not a probability estimate |
| `label_source` | `vlm_auto`, `manual_review` | Each label record has a source & revision; human corrections stored separately |

**Draft conditions:** Only output an event when its timestamp is supported by sampled evidence; use multi-field response not a single super-class; include `object_id_or_description`, `evidence_frame_ids[]`, `observation_note`, `model_reported_confidence` nullable. VLM self-confidence is *not* calibrated probability. Unseen contact force/slip may not be asserted as physically measured.

### Example (schematic, not model result)

```json
{
  "motion_phase": "grasp",
  "object_relation": ["gripper_around"],
  "event_type": "grasp_attempt",
  "event_outcome": "unclear",
  "evidence_quality": "insufficient",
  "evidence_frame_ids": ["data/demo_0:t=46", "data/demo_0:t=51"],
  "observation_note": "Gripper closes; post-contact can motion is not visible"
}
```

## 5. Pipeline architecture and responsibilities

```text
RoboMimic Can/MH + frozen P1 source semantics
    │
    ├── G1 Frozen Segments (read-only)
    └── M2 Clean RGB + keyframes + Robot Motion Summary (read-only)
                     │
          [G3-01 Source/Time/Permission Audit]
                     │
          [G3-02 Evidence Pack: ordered frames + frame-role/time + permitted robot summary]
                     │
          [G3-03 Single VLM + versioned Prompt/JSON Schema]
                     │
          [G3-04 Raw Result + Structured Semantic Label + Candidate Events]
                     │
          [G3-05 Deterministic Consistency Flags + Review Routing]
                     │
          [G3-06 Human Timeline Audit + Manual Corrections]
                     │
          [G3-07 Event Index / Label-QC Findings / Candidate Manifest / Export]
```

No retrieval ranking, SigLIP2 embedding or FAISS in the formal G3 pipeline. G3 generated semantic labels must never be injected into preexisting frozen Retrieval v1 evaluation or relevance GT.

## 6. Verification: minimally necessary versus optional

### 6.1 Mandatory safeguards

| Check | Failure interpretation | Action |
|---|---|---|
| `INPUT_IDENTITY` | Wrong episode/frame, renderer mismatch, privileged field | `INVALID_INPUT`, stop call, preserve reason |
| `TIME_RANGE` | Predicted event outside input/episode, impossible ordering | `LABEL_INVALID`, review; do not auto-correct |
| `SCHEMA` | Missing/illegal enum, invalid JSON | `PROCESSING_ERROR` or `INVALID_MODEL_OUTPUT`, retry within recorded budget, never mark data bad |
| `LABEL_LOGIC` | Unambiguously contradictory outcome/progress/labels | `REVIEW_REQUIRED` |
| `EVIDENCE_COVERAGE` | Required post-event frame absent, occlusion, too few samples | `UNRESOLVED` when label cannot be supported |
| `SENSOR_ROLE` | Action passed off as speed/force, state origin missing | `INVALID_INPUT` or review |

Crucial distinction: Argus `checks/label_consistency.py` tests **within-label contradictions**. P2's evidence-versus-state assessment is new source-specific logic. Neither proves physical grasp success if vision does not show object follow-through. Check failures **flag for review; never mutate the underlying model judgment**.

### 6.2 Scope decisions

- **Event-specific extra RGB frames**: optional P1, triggered by **human-observed calibration bad cases** and a preregistered, source-signal-only sampling policy; not mandatory to start v1.
- **Cross-modal semantic verification**: mandatory *minimal evidence audit* and optional richer semantic contradiction heuristics. To claim algorithmic uplift, compare to a no-check baseline at matched manual review budget.
- **Human review**: mandatory independent quality benchmark; minimal viewer + correction CSV sufficient; full Argus frontend not required.
- **Task progress and recovery**: basic schema/index required, but performance claims only where observable and ground-truth positives sufficient.

### 6.3 Annotation confidence versus data curation decision

Keep separate: `semantic_prediction`, `label_qc_status`, `event_candidate`, `review_status`, `curation_candidate_tags`, `training_disposition`. **Do not map `AUTO_ACCEPT` → dataset `KEEP`**: a correct label does not prove the demonstration is useful for training. In v1 `training_disposition = NOT_EVALUATED` for all; outputs are annotation-review actions only, not training-data filtering instructions.

## 7. Experimental protocol: industrial-minimum validation

### 7.1 Baseline, development and evaluation

Before full VLM batch, run: (i) no-call contracts/mocks; (ii) **8–12 episode observability audit** on clean RGB; (iii) **8–12 segment baseline inference pilot** to prove service/json/frame contract. No model training; no training steps to tune.

Proposed **calibration**: ~20–30 segments; **held-out**: ~60–80 segments from non-overlapping episodes. Sample sizes remain candidate budgets and should be revised after measuring actual observable event counts; keep source operator/scenario composition audited. Freeze split by **Episode before inference** and do not select eval data by VLM errors. Calibration, formal G3 human audit and frozen Retrieval audit have distinct roles, though an Episode may appear in both independent projects only with documented no-leakage rules.

Human evaluation uses a blind rubric: `motion_phase`, `object_relation`, event observable/outcome, `evidence_quality`, event time-window. Humans can use richer full temporal replay than VLM, but record that advantage and do not feed private oracle/performance metadata to VLM. Two-pass disagreement on an audit subset; reconcile without consulting model predictions. Unsupported/ambiguous examples remain `UNSURE` and are reported, not opportunistically excluded.

### 7.2 Mandatory paired comparison

| Version | Input | Required evidence | Goal |
|---|---|---|---|
| **A — Vision-only** | Frozen START/MIDDLE/END/GRIPPER_EVENT clean RGB + sourced task text | Human semantic GT | Establish single-VLM baseline |
| **B — Multi-modal** | Same images, same model/schema + approved M2 EEF/Gripper/Action summary | Same held-out GT & identity | Quantify independent effect of robot state/action |

Same segment IDs, model revision/preprocessing, prompts aside from permitted evidence, sample order randomized/controlled, no answer-based re-selection. Assess paired changes in phase accuracy/Macro-F1; event and relation metrics only where enough labeled positives and clear definitions exist. Report per-episode clustered uncertainty for small populations and provide error analyses, not unsupported improvement claims.

### 7.3 Conditional engineering comparisons

- **C**: B + pre-registered event-window additional renderer RGB, **only if** missing temporal evidence dominates calibration errors and frame observability is adequate. Compare C vs B under same held-out human GT, record added image/token cost.
- **D**: B (or C if authorized) + deterministic consistency checks/abstention. D is **post-processing on identical raw predictions**, not a new model. Compare **error catch precision + accepted-label accuracy/coverage + review yield at equal review budgets**, versus no-check or random/simple-baseline triage. Mandatory only if declaring the check improves annotation reliability or review efficiency.

Industry requirement is **evidence-backed validation**, not exhaustive publication-style factorial ablation. Where only A/B is run, do not assert C/D gains.

### 7.4 Core measured outputs and guardrails

1. Semantic: `phase_accuracy`, supported-class `phase_macro_f1` with per-class supports/confusion, `relation_precision/recall` when defined.
2. Events: localization tolerance, event precision/recall only when sufficient event positives/negatives; otherwise `NOT_ESTIMABLE`.
3. Review: `accepted_label_accuracy` **with** `auto_accept_coverage`; flagged-label error yield at a **fixed** human review budget against random or simple heuristic; count false flags and ambiguity.
4. Reliability: `invalid_input`, `parse_error`, `timeout`, `missing_frames` **separately** from true annotation defects; cost/latency per annotated segment.
5. Evidence coverage: share of cases for which task/interactions were visually decidable; measure missing object visibility.

**Proposed G3 Gate**: `GO` when independent human evaluation supports useful controlled labels, reproducible end-to-end export and a decision-relevant A/B or review-budget improvement (if claimed); `LIMITED` when annotation works but incremental gain unsupported; `INCONCLUSIVE` when too few positive/observable examples; `STOP/PIVOT` when visible semantics cannot be reliably determined or error/review cost is unacceptable. Exact numerical thresholds and minimum per-class support must be frozen *after pilot and before final*, not chosen from held-out results.

## 8. Failure handling and stop/pivot conditions

- Source alignment, schema and renderer provenance fail: **STOP execution** until repaired, not lower quality label.
- 128×128 RGB or camera angle cannot support core objects/interaction: restrict to visible coarse phase or seek a separately approved richer data source; do not invent failures.
- Actual failed-grasp/slip/recovery positive counts too low: report candidate-only examples; do not claim failure detector F1.
- B adds no reliable gain over A: still valid reproducible annotation/data-index system, but no multi-modal *algorithm improvement* claim.
- Triage flags too many correct samples or saves no human time: keep only structural safety checks; do not advertise review efficiency gains.
- Only one task/rig and limited variation: no generalization claim to multi-task, real robots, new robots/operators or object sets.
- No independent human GT: software demo only, not label-QC evidence.

## 9. Acceptance checklist and interview evidence

**Engineering**: source-to-export CLI, safe resume/reparse, immutable run records, controlled schema, trusted frame identity and sample/error separation, minimal reviewer timeline and correctable labels, event query capability, unit/fixture tests.

**Evaluation**: locked human rubric, Episode-isolated manifest, A/B fair comparison, positive-support disclosure, uncertainty and failure cases, conditional validation for any C/D gains. Provide 3–5 *actual* inspectable examples **only if data supports them**.

**Claim boundary**: independently reproduced Argus-inspired capabilities *for RoboMimic Can/MH*, added P2 source-specific RGB/state/action alignment and validation; do not advertise a new multimodal foundational model or policy improvement.

## 10. Decision ledger

| Item | Decision status |
|---|---|
| Retrieval HOLD and G3 priority | OWNER_APPROVED_DIRECTION; needs SSOT merge |
| Core Argus functionality on one supported data format | OWNER_APPROVED |
| Minimal human evaluation; no ACT v1 | OWNER_APPROVED |
| Full A/B comparison | APPROVED_DEFINITION; final cohort thresholds to freeze |
| Dynamic event frames as required feature | NOT APPROVED; conditional |
| Full Argus UI and many data adapters | OUT_OF_SCOPE |
| Exact taxonomy/schema values and formal eval pool | PROPOSED_PENDING_FREEZE |
| Exact Qwen checkpoint/service identity | PIN_BEFORE_RUN |
