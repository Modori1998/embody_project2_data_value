# P2-G3 — Taxonomy v0.2 Design | Owner-approved development spec (2026-10-13)

> **OWNER_DECISION = V0_2_TAXONOMY_DESIGN_FROZEN_FOR_DEVELOPMENT**
>
> **Not the same as:** `FORMAL_G3_TAXONOMY_V1=FROZEN` (remains **NO**), human semantic GT complete (**NO**), or measured 4B/8B semantic improvement (**NOT_MEASURED**).
>
> **Status and authority:** Owner approved this minimal v0.2 revision as the **next implementation and evaluation protocol**. Its definitions and test scope must be versioned before the v0.2 experiment. Any post-outcome changes require v0.3/new-run identity, not silent changes to v0.2 results.

## 1. Source and reason

- Owner-frozen output architecture: `P2_G3_Structured_JSON_and_Evidence_Contract_Owner_Freeze_20261013.md`, JSON-only + controlled enums + short note + frame evidence + deterministic QC.
- Previous implemented candidate: `p2-g3-json-prompt-baseline-20261013` @ `331d9afcc3ed9bbc7897f2a70da13699e915f4b8`. Report: `0-doc/90-implementation-local/G3_JSON_Tiny_Baseline_Result_20261013.md` on that branch. Actual ten development inference calls: HTTP/JSON 10/10, schema valid 9/10, citations in target 10/10, abstention 0/10, `motion_phase` exactly 5 `approach` + 5 `grasp`, `gripper_state` 5 `open` + 5 `closed` and exactly co-varied; `object_relation=gripper_around` 8/10; `events=[]` 9/10; `evidence_quality=sufficient` 10/10. These are **outputs**, NOT correctness/accuracy estimates.
- `demo_33-S0001` and `demo_75-S0001`: Phase1C owner rated target-only A `CANNOT` (subjective observability, not semantic GT), whereas v0.1 model emitted `approach/open/object_static/events=[]/sufficient`; both cite frames [0,1,3]. Avoid automatically re-labeling them as errors.
- `demo_47-S0003`: v0.1 emitted an event with missing mandatory nested evidence, plus note "No motion is observed" and definite grasp-attempt success. Preserve the original invalid output. The situation shows a rubric and consistency coverage gap, not a proven true grasp outcome.
- Phase1B/1C: `CONTEXT_POLICY_DECISION=KEEP_CONTEXT_OPTIONAL`; context doesn't automatically become target evidence. Frozen G1/M2, target frame boundaries and RGB remain unchanged.

## 2. The core distinction: state vs. temporal action

A **state** means what a gripper/object looks like at one sampled instant; an **action** means an observable change/process across ordered samples. `gripper_state=closed` does **NOT** establish `motion_phase=grasp`; it may be holding, transporting, stationary, etc. `grasp` is an **attempt phase**, never proof of successful acquisition. Neither `gripper_state` nor `object_relation` independently establishes force, contact or task success.

For v0.2 `gripper_state` refers to the **last valid target-segment image supplied** (not any arbitrary sample); source/role/frame-index are caller-bound. An uncertain last-frame jaw configuration should be `uncertain` even if an earlier frame is clearly open. The note may describe changes between samples.

### 2.1 Motion-phase controlled vocab — retain nine v0.1 labels; refine meanings

| `motion_phase` | Chinese | V0.2 observed-evidence rule | Forbidden shortcut |
| --- | --- | --- | --- |
| `approach` | 靠近 | Two or more ordered target views plausibly show gripper/EEF approaching the task object relative to comparable visual references | Gripper is simply `open` or near the can |
| `grasp` | 抓取尝试阶段 | Observable closing/positioning *change toward object acquisition*; it is a local attempt phase | One still frame with `closed` jaws; do not infer `success` |
| `lift` | 提起 | Visible object + gripper movement upward across comparable views, relative to workspace | Changed camera viewpoint or gripper closed |
| `transport` | 搬运 | Visible object moves consistently with gripper over time; contact/force not inferred | A static object visually near the gripper |
| `place` | 放置 | Visible move toward support/target location or release action sequence; outcome checked separately | Assume placement success from target goal text |
| `retract` | 撤离 | Gripper/arm visibly moves away from a previous interaction region | Gripper simply open |
| `idle` | 观察范围内静止 | Comparable temporal samples support no significant motion in the **observed window only** | Infer inactivity over unsampled whole segment |
| `other` | 其他可见动作 | Actual visible motion/process exists but fits none of the above | Hide insufficient evidence in `other` |
| `uncertain` | 主要动作无法确认 | Motion direction/phase cannot be supported by temporal evidence, visibility, or reference comparability | Force a non-uncertain label merely because jaws are visible |

These are **v0.2 development specifications**, not retrospectively verified human ground truth. Sparse three-frame sampling may support some states yet not a phase. A short Segment (even four original frames) is **not automatically insufficient**; use visible change, not a duration threshold. No simulator privileged fields or presumed physical speed/force.

### 2.2 Object-relation & gripper-state separation

Keep the existing `object_relation` and `gripper_state` fields separately in v0.2; do **not** merge yet. Existing v0.1 `object_relation` candidate vocabulary is retained for the minimal experiment, with stricter written meanings:

- `gripper_around`: the jaw geometry **visibly surrounds** the object in the image; near/no-contact alone does not prove it.
- `gripper_contact_visible`: visible proximity consistent with contact **only where the contact interface is actually observable**; never assert physical gripping force.
- `moving_with_gripper`: the object/gripper positions change together across the sampled sequence.
- `object_static`: observed object location appears unchanged across comparable sampled views; not proof it stayed static during unsampled moments.
- `object_not_visible`: target object cannot be visually located in supplied relevant target frames.
- `uncertain`: visual relationship not supportable.

`gripper_state = open / closed / partially_open / uncertain` describes the **last target image's jaw configuration**, not contact or acquisition; keep this field separate. Evaluate overlap empirically; no structural redesign or extra object-visibility field in this round.

## 3. Events v0.2 — add a presence/observability decision

**Retain `events: []`** (zero or more **visibly supported** candidate events), but add **exactly one new top-level model-owned field**:

`event_assessment = event_visible | no_event_visible | insufficient_evidence`

| `event_assessment` | Meaning | Required relationship to `events` |
| --- | --- | --- |
| `event_visible` | Supplied target frames support at least one specifically identifiable candidate event | `events` must contain >=1 substantive supported event with target-frame citations |
| `no_event_visible` | No supported candidate event was **observed in sampled target images** | `events=[]`; no claim that unobserved intervals definitely lacked events |
| `insufficient_evidence` | Given images do not reliably establish whether an event occurred | `events=[]` for this v0.2 small-scope version; report limitation in `observation_note` |

For v0.2 event **items**, substantively supported event types are `grasp_attempt`, `release_attempt`, `object_motion`. V0.1 synthetic `none_observed` / `uncertain` item markers move to `event_assessment`; the migration must be explicitly versioned, never retrofit old JSON. Keep `event_outcome = success / failure / unclear` as currently supported, but only assign success/failure to **the specific local attempted effect** when pre/post visual evidence supports it. For unscored physical `object_motion`, `unclear` means *no demonstrated task-goal success/failure* pending a future `not_applicable` design decision; don't manufacture a goal result. There is **no** episode task outcome in this model response.

**Trigger rules**:

1. `grasp_attempt`: visible behavior directed toward acquiring an object (e.g., jaws transition toward closure near the object), regardless of whether acquisition is proven.
2. `release_attempt`: a visible action to let go at a destination; no automatic successful placement claim.
3. `object_motion`: distinguishable displacement of the object across comparable target views, whether or not gripper caused it.
4. A single still `closed` jaw is **not** a grasp attempt; comparing only nearby-looking stills without credible time change is not enough.
5. If an event is plausible but its occurrence is not observable, prefer `insufficient_evidence`; if the **event happened** visibly but outcome is unknown, `event_visible` with `event_outcome=unclear`. Separate *occurrence uncertainty* from *outcome uncertainty*.
6. Every substantive event has target-frame `evidence_frame_indices` (at least one; pre/post support where success/failure is claimed). Cited timestamps/indices cannot escape frozen target interval; context images cannot make an event belong to the target.

A long continuous transport phase may have `events=[]` if no individual event is supported under these explicit rules. Do **not** force extra events to raise event rate.

## 4. Frozen scope constraints

- `G3_OUTPUT_ARCHITECTURE=FROZEN_JSON_ENUM_NOTE_FRAME_EVIDENCE_QC_V1`; keep **JSON-only + controlled enums + short `observation_note` + frame citations + caller-owned provenance + deterministic QC**.
- The existing top-level fields stay; **one added**: `event_assessment`.
- **No** G1/M2 modifications, no new RGB resolution contract, no mandatory neighbor window. Existing `KEEP_CONTEXT_OPTIONAL` stays in force; base pilot target-only.
- **No** full Argus timeline, Episode-level completion, recovery chain, full review UI, ACT training, KEEP/DROP/UPWEIGHT.
- No unverified claim that a richer Prompt improves 4B semantics; define & lock this v0.2 candidate before new inference.
- Model-family target for later formal work remains 8B with exact revision pending; local 4B Q4 is the **development** pilot, not a substituted official 8B benchmark.

## 5. Status keys

```text
G3_OUTPUT_ARCHITECTURE=FROZEN_JSON_ENUM_NOTE_FRAME_EVIDENCE_QC_V1
G3_TAXONOMY_V0_2_DEV_SPEC=OWNER_APPROVED_FROZEN_FOR_IMPLEMENTATION
G3_EVIDENCE_RUBRIC_V0_2_DEV_SPEC=OWNER_APPROVED_FROZEN_FOR_IMPLEMENTATION
G3_FORMAL_TAXONOMY_V1=NOT_FROZEN
G3_PROMPT_V0_2_BYTES_AND_SHA=PENDING_LOCAL_BUILD
G3_MODEL_4B_V0_2_BASELINE=NOT_RUN
G3_HUMAN_SEMANTIC_GT=NOT_COLLECTED
G3_FORMAL_8B_EVALUATION=NOT_STARTED
```

Do not use `OWNER_APPROVED` as evidence that the model output is accurate.
