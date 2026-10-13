# P2-G3 — Evidence Rubric v0.2 + Micro-Experiment Plan | Owner Freeze 2026-10-13

> **Status**: `V0_2_EVIDENCE_RUBRIC_AND_TEST_PLAN=OWNER_APPROVED_FROZEN_FOR_LOCAL_EXPERIMENT`. These are future-study definitions, not validated outcomes. See companion Taxonomy v0.2 Design and v0.2 JSON Output Design.

## 1. Baseline motivation and non-goals

The real Qwen3-VL-4B Q4 v0.1 development run (10 target-only G1 segments; source branch `p2-g3-json-prompt-baseline-20261013` @ `331d9afcc3ed9bbc7897f2a70da13699e915f4b8`) yielded:
- 10/10 JSON parse, 9/10 schema-valid, 10/10 referenced frame identities legal, 0 truncations; **engineering gate only**.
- `events=[]` 9/10; all 10 `evidence_quality=sufficient`; phase `grasp` perfectly coincided with closed gripper; no semantic human GT.
- `demo_33-S0001` and `demo_75-S0001` were Phase1C A=`CANNOT` by Owner, vs VLM `approach + sufficient`. These are **different tasks**, so do not auto-correct model or count wrong predictions.
- `demo_47-S0003` was structurally invalid (missing nested event evidence), with a note/outcome conflict candidate. Previous v0.1 report remains intact and is **not rerun as if unseen**.

## 2. Evidence Rubric — `evidence_quality` is scoped to `motion_phase`

**Only three values**; separate assessment of event occurrence uses `event_assessment`.

| Value | Decision rule | Example |
| --- | --- | --- |
| `sufficient` | Ordered, comparable **target-segment images** visibly support the selected `motion_phase`, including relevant direction/change when the phase requires motion. An asserted definite **event outcome** additionally needs its own supported pre/post event images. | A fixed-view series visibly shows a carried item moving with the gripper |
| `partial` | Some properties/states are readable, **but the main motion phase is not reliable** owing to incomplete temporal coverage, overlap, ambiguous visual geometry or incomplete occlusion. The corresponding phase should usually be `uncertain`; do not silently declare a precise phase solely because the gripper state is clear. | Last frame clearly shows jaws closed, but acquisition-vs-transport is unclear |
| `insufficient` | Key object/jaws or temporal references are missing/occluded, or sampling cannot support even a reliable coarse phase. Use `motion_phase=uncertain` and state what is missing; simple visible state fields can remain populated only when individually supported. | Sparse images don't establish movement or relevant object visibility |

**Practical consistency**: a model may emit `motion_phase=uncertain` with `evidence_quality=partial` or `insufficient`. Conversely, `motion_phase=approach/grasp/transport` together with `evidence_quality=partial/insufficient` is a **review candidate** unless a specific aspect can be explained; do not silently rewrite. `motion_phase=uncertain` with `evidence_quality=sufficient` is also a review candidate for inconsistent support. These are defaults pending evidence, not physical truths.

Do **not**:
- force `insufficient` because a Segment has length <=4 frames or because a person couldn't infer the goal;
- require visible contact force to tag a **visible** movement;
- elevate `evidence_frame_indices` membership to proof that label semantics are correct;
- treat `evidence_quality` as calibrated probability, human confidence, or overall episode accuracy.

### 2.1 Programmatic checks vs human visual judgment

**Deterministic / hard-invalid** (trusted source IDs/roles are checkable): malformed/missing fields and types, unsupported enums, nonexistent or out-of-target event citations, context frame as target event, incomplete/truncated JSON, forbidden caller-owned fields.

**Semantic review CANDIDATE** (do not mutate model prediction):
- `PHASE_NOTE_MOTION_CONFLICT_CANDIDATE`: specific event/motion phase is asserted but text unambiguously claims *no corresponding movement*; short phrase matching may produce false positives, so restrict patterns and disclose errors.
- `EVIDENCE_PHASE_QUALITY_CONFLICT_CANDIDATE`: quality and phase clearly at odds under Rubric.
- `EVENT_ASSESSMENT_CONFLICT`: structural combinations that contradict v0.2 event_assessment consistency; wrong cardinality is deterministic invalid (see Output Design), narrative conflicts are review candidates.
- `EVENT_OUTCOME_UNSUPPORTED_CANDIDATE`: definite result with missing/not-comparable before-and-after **visual samples**, not proof of a failed event.
- `LABEL_NOTE_CONFLICT_CANDIDATE`: model's note vs categorical fields disagree where vocabulary explicitly supports the rule.
- Detect `gripper_state=closed` alone used to support `grasp` only as candidate without human semantic video evidence; model cannot prove the internal shortcut solely by JSON.

**Target-only in base experiment**: Context Window remains optional and separate. A single neighbor A/B regression using `demo_47-S0003` can test the deterministic boundary guard, but cannot establish context accuracy or semantic correctness.

## 3. Locked experiment sequence / controls

### Phase 0 — read-only environment and SSOT
1. `git fetch origin --prune`; **pull latest main with `git pull --ff-only origin main`** in healthy clean main worktree. If main is dirty, do not touch; report/choose safe dedicated clean worktree, preserve others.
2. Read this plan, Taxonomy Design, JSON Output Design, current main Output-Architecture Owner Freeze and v0.1 baseline evidence. Work in an isolated branch from latest main; **targetedly restore** only needed v0.1 runtime modules/tests from `p2-g3-json-prompt-baseline-20261013`, without merging that entire experimental branch or modifying its evidence.
3. Inspect local Qwen3-VL-4B llama.cpp runtime; reuse installed weights/model exact revision; no auto downloads/install/8B.

### Phase 1 — no-call implementation and tests
- Implement `event_assessment` field, supporting enum, event structural rules and amended temporal Action/State descriptions.
- Implement `evidence_quality` Rubric and note/phase candidate checks. Include explicit `motion_phase` vs `gripper_state` separation. Preserve v0.1 schema and Prompt byte-for-byte and run IDs.
- `gripper_state` refers to last target-frame appearance. Do not secretly pass robot-state signals into vision-only A.
- Write **synthetic unit tests** first: positive event / absent event / insufficient; each legal and contradictory event_assessment combination; valid and missing event evidence, phase-gripper shortcut, phase-note contradiction, sufficient/uncertain tension; three rubrics; invalid context citation; v0.1 compatibility. Test idempotent/reparse/non-mutation and complete response (`finish_reason=stop`).
- Version the actual Prompt v0.2, schema, validators, checks; compute complete SHA256; output versions shouldn't mutate v0.1 snapshots.
- Mark `PROMPT_V0_2=PENDING_RUNTIME_VALIDATION` until actual tests run.

### Phase 2 — historical known-bad diagnosis, NOT new test
- Use ONLY these known issue cases: `demo_33-S0001` (4 frames), `demo_75-S0001` (4 frames), `demo_47-S0003` (41 frames).
- They are **Development diagnostics** and may be analyzed but **must not** contribute to unseen-v0.2 generalization or claimed accuracy. Capture before/after predictions and whether v0.2 rubric respects uncertainty and event presence. Any changes **after inspecting outputs** require a v0.3 run, not silent redefinition of the v0.2 run.

### Phase 3 — NEW independent development micro-set (8–12 segments)
- Before either v0.1/v0.2 inference, freeze sample IDs/episode IDs, G1 boundary/source hash, target RGB hashes, source/selection rules, model/runtime, prompts/schema versions, QC definitions, an **engineering** gate and semantic reporting denominators. Distinct from the prior 10 development episodes, exclude formal G3 Held-out and all known independent frozen evaluation episodes. Episode-disjoint vs diagnostic set.
- Selected from structurally documented **Development** pool, not by VLM output. Include **potential** visible motion, candidate events, quiet, unclear and short examples. If seeking event positive reference, human independent readback identifies positives **before seeing model answers**. Structural stratification isn't proof of events; report actual human-positive count.
- Minimal **human reference**: simple 4 judgments per Segment, using visually readable clean target frames plus clearly marked human-only optional replay evidence, blind to v0.1/v0.2 model predictions: `phase_ref` (one of v0.2 enums or `uncertain`); `event_assessment_ref` (visible/none/insufficient); `event_type_ref` (specific event or none/uncertain); `evidence_quality_ref` (sufficient/partial/insufficient); optional explanation and reviewer/revision. If independent human reference unavailable, skip semantic accuracy claims and report only qualitative side-by-side differences.
- Paired **v0.1 vs v0.2** on the same new samples and identical target RGB/model revision/processor/quantization/random seed/temperature/output limit; source text and evidence identity unchanged except v0.2's amended instructions and schema. Explicitly distinguish `v0.1` has **no** `event_assessment` and cannot be compared on that metric as though identical.
- Freeze v0.2 Prompt and Schema before requesting *any* new v0.2 outputs. Run no dynamic retries or prompt fixes based on answers. Preserve all full raw responses and hashes; generate only a privacy-safe shareable evidence subset in Git.
- Report `JSON parse/schema validity`, frame provenance, cross-boundary flags, truncations, completion/latency/VRAM, event_empty rate, event_assessment distribution, `evidence_quality` distribution, phase-gripper coincidence, note contradictions and human-reference matching (only if actually labeled).
- Do not celebrate an increased abstention rate by itself. Evaluate whether **supported decisive cases remain decisive** and **ambiguous cases appropriately abstain**. Keep label coverage alongside correctness and denominators.

### Phase 4 — closeout without downstream authorization
- An independent Development pilot can expose possible improvement, not demonstrate formal semantic accuracy. No claims of 4B superiority, 8B uplift, formal Held-out validity or dataset training utility.
- If no human-confirmed event positives, report `EVENT_METRIC=NOT_ESTIMABLE`, rather than implying `events=[]` is wrong or right.
- Pin exact target-only vs optional-neighbor axis separately from future `Vision-only vs Vision+State/Action` A/B.
- Do not merge runtime branch into main or freeze formal v1 taxonomy/model. Report proposed revisions to Owner for approval.

## 4. Honest acceptance / stop policy

Prior v0.1 engineering gate `all_gates_pass=true` and schema valid rate `9/10` only demonstrate the prototype is runnable. For v0.2, **pre-register engineering thresholds before any live calls**:
- Zero forbidden inputs, zero unguarded out-of-segment frame citations, zero silent parser rewrites.
- No model output with illegal Schema may be classified `VALID`.
- JSON parse/schema rates and truncation counts must be reported with exact denominators (a reasonable target is ≥90% Schema-valid as in v0.1; **do not** adjust it post hoc).
- Semantic evaluation must include human reference or `NOT_ESTIMABLE`, never fabricated hit-rate or F1.

**Stop after** no-call tests, known-case regression, paired 8–12 fresh Development samples, report/provenance and push of isolated development branch. Do not run formal Qwen3-VL-8B, no 256/512 contract changes, no extensive GT platform, no ACT/VLA training, no unapproved main merge.

## 5. Deliverables and statuses

- The companion `P2_G3_Taxonomy_v0_2_Design_Owner_Freeze_20261013.md`, `P2_G3_Semantic_JSON_v0_2_Output_Design_Owner_Freeze_20261013.md`, this plan and top-level MVP SSOT pointer.
- Local versioned Prompt/Schema/validator/pilot driver and minimal tests.
- `0-doc/90-implementation-local/G3_Taxonomy_v0_2_Implementation_Result_<RUN_DATE>.md` with new sample manifest, hashes, factual output comparison, error diagnoses, any human reference, explicit not-estimable claims.
- `G3_V0_2_RUNTIME_AND_EVALUATION_STATUS` remains **NOT_RUN** at design-freeze time.
