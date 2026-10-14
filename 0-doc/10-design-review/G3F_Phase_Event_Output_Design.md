# G3F Phase–Event Output Design (consistency QC v0.2.2) — 2026-10-14

Base main: `05228ce2dfe5cb8a759b1b3d7431359ad296c5da`.

## 1. What this adds

A **versioned, opt-in, non-destructive** review layer for G3 semantic
annotations: `src/project2_g3/phase_event_qc.py`,
`PHASE_EVENT_QC_VERSION = "P2_G3_PHASE_EVENT_QC_V0_2_2_CANDIDATE"`.

It is intentionally **separate** from the frozen `semantic_validation` module.
The frozen v0.2.1 validator (structural schema/frame/status logic) is not edited
and is still the only thing that decides `VALID` / `REVIEW_REQUIRED` /
`INVALID_MODEL_OUTPUT`.

## 2. Rules

All findings are `scope=CANDIDATE` (review candidates), never hard-invalid.

| Rule | Condition | `check_id` |
|---|---|---|
| A | `motion_phase in {transport, lift}` and `object_motion ∉ events` | `PHASE_OBJECT_MOTION_MISSING_CANDIDATE` |
| B | `moving_with_gripper ∈ object_relation` and `object_motion ∉ events` | `RELATION_OBJECT_MOTION_MISSING_CANDIDATE` |
| C | note **explicitly** denies object motion/displacement and `object_motion ∈ events` | `OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE` |
| D | `grasp_attempt ∈ events` and note **explicitly** denies an observed grasp process (or states the gripper did not change configuration *and* nothing visible happened) | `GRASP_EVENT_NOTE_CONFLICT_CANDIDATE` |

Rule A is a *review candidate*, not an instruction to insert an event: it must be
resolved by deciding whether the phase is right or the event was missed.

Rule C requires an **explicit denial** ("物体静止" / "can remains stationary" /
"no object motion"); a mere absence of a motion mention does not fire.

Rule D does **not** fire on `gripper_state=closed` alone, and — after a pilot
false alert — does **not** fire on outcome uncertainty ("尚未明确是否被抓取成功"),
because that negates the *outcome*, not the process.

## 3. Non-destructive guarantees

The QC:

* never modifies a prediction, a human label or a phase;
* never adds `object_motion`;
* never escalates a candidate to `INVALID_MODEL_OUTPUT`;
* never deletes a prediction to improve a score.

`review_annotation(payload)` returns a new envelope
(`{phase_event_qc_version, review_status, findings}`) and leaves the input
dictionary untouched (unit-tested). QC-triggered retry is explicitly **out of
scope** for this round; it would be a separate experimental version, so the
prompt-only A/B comparison stays clean.

## 4. Offline replay over frozen history

`scripts/replay_g3f_phase_event_qc.py --run-dir <run> --human-reference <csv>`
replays the QC over an already-finished run. For the G3D2-R 60-cell run:

| Group | Rule C fires | Rule D fires |
|---|---|---|
| G0 | 0 | 0 |
| G1 | 1 | 5 |
| T0 | 1 | 0 |
| T1 | 4 | 1 |
| T2 | 6 | 4 |
| **Total** | **12** | **10** |

* Rule A: **0** fires. Rule B: **0** fires.
* Known `object_motion` true positives detected (`demo_2`, `demo_4`, `demo_159`):
  **0 / 3**.
* Cells flagged while their event set was already exactly correct: **2**
  (`demo_216`/G1, `demo_28`/G1) — both are Rule D, and in both the note literally
  says "No visible grasp … occurs" while the event set claims `grasp_attempt`, so
  the flag is a genuine note/label contradiction, not a scoring error.

### Coverage and blind spots (reported honestly)

* Rule C is precise on this data: **12/12** fires are annotations that really do
  contain an `object_motion` event contradicted by their own note.
* Rule A/B are **blind** to the historical `object_motion` misses: none of the 15
  miss cells asserted `transport`/`lift` (only `demo_183`/T2 ever predicted
  `transport`, and it included the event) and none asserted
  `moving_with_gripper`. A model that predicts `grasp` and denies object motion
  cannot be caught by a "transport implies object_motion" rule — this must be
  stated rather than hidden.

## 5. Artifacts

* `src/project2_g3/phase_event_qc.py` — rules.
* `scripts/replay_g3f_phase_event_qc.py` — offline replay.
* `tests/test_g3f_phase_event.py` — rule and non-destructiveness tests.
* Local replay outputs (gitignored):
  `outputs/g3d2r/full_fallback_r1/phase_event_qc_replay.{json,jsonl}`.
