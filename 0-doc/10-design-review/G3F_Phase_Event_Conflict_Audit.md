# G3F Phase–Event Conflict Audit (read-only) — 2026-10-14

Base main: `05228ce2dfe5cb8a759b1b3d7431359ad296c5da`. This audit only **reads**
stored artifacts; it changes no prediction, no human label, no frozen prompt,
no schema and no historical run.

## 1. Scope and sources

| Source | Role |
|---|---|
| `src/project2_g3/semantic_prompt.py` (`PROMPT_TEMPLATE_V0_2_1`) | the prompt whose wording is under audit |
| `src/project2_g3/semantic_schema.py` (`PHASE_EVIDENCE_RULES_V0_2`, `EVENT_TRIGGER_RULES_V0_2`) | the frozen definitions of `transport` / `lift` / `object_motion` |
| `src/project2_g3/semantic_validation.py` | existing (frozen) QC |
| `outputs/g3d2r/full_fallback_r1` (59 valid cells) | the 60-cell G3D2-R Development run |
| `G3C_12_Segment_Human_MultiEvent_Reference_v2.csv` (local, not committed) | frozen human multi-event reference |
| `scripts/replay_g3f_phase_event_qc.py` | offline classifier used below |

## 2. The suspected conflict

The frozen schema defines:

* `transport` = 物体随时间与夹爪保持一致移动；
* `lift` = 物体与夹爪一起向上位移；
* `object_motion` = 在可比目标帧之间物体有可分辨的位移，无论是否由夹爪造成。

The v0.2.1 prompt stated:

> 长距离的连续搬运可能确实 `events=[]`；**不要**为了凑事件率而编造事件。

So a model could satisfy `motion_phase=transport` while correctly following the
prompt yet leave `events=[]` (or omit `object_motion`), even though the schema
says the object visibly moved. That is a **semantic inconsistency in the
instructions**, independent of whether the model would actually exploit it.

## 3. Per-cell audit (9 flagged segments × 5 arms = 45 cells)

`Conflict Type` is the offline classification: `PHASE_EVENT_ENTAILMENT_MISS`
(phase implies the event but the event is absent), `OBSERVED_BUT_NOT_LABELED`
(note explicitly describes object displacement but the event is missing),
`PERCEPTION_OR_PHASE_MISS` (neither phase nor note identifies object motion),
`EVENT_CONTRADICTION` (note explicitly denies object motion but `object_motion`
is present), `CELL_INVALID`, `CONSISTENT`.

| Segment | Human Phase | Human Events | Group | Pred Phase | Pred Events | Conflict Type |
|---|---|---|---|---|---|---|
| demo_2-S0003 | transport | grasp_attempt, object_motion | G0 | grasp | grasp_attempt | OBSERVED_BUT_NOT_LABELED |
| demo_2-S0003 | transport | grasp_attempt, object_motion | G1 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_2-S0003 | transport | grasp_attempt, object_motion | T0 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_2-S0003 | transport | grasp_attempt, object_motion | T1 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_2-S0003 | transport | grasp_attempt, object_motion | T2 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_4-S0003 | transport | grasp_attempt, object_motion | G0 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_4-S0003 | transport | grasp_attempt, object_motion | G1 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_4-S0003 | transport | grasp_attempt, object_motion | T0 | retract | release_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_4-S0003 | transport | grasp_attempt, object_motion | T1 | grasp | grasp_attempt | OBSERVED_BUT_NOT_LABELED |
| demo_4-S0003 | transport | grasp_attempt, object_motion | T2 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_159-S0003 | transport | grasp_attempt, object_motion | G0 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_159-S0003 | transport | grasp_attempt, object_motion | G1 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_159-S0003 | transport | grasp_attempt, object_motion | T0 | retract | release_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_159-S0003 | transport | grasp_attempt, object_motion | T1 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_159-S0003 | transport | grasp_attempt, object_motion | T2 | grasp | grasp_attempt | PERCEPTION_OR_PHASE_MISS |
| demo_169-S0002 | approach | — | G0 | approach | grasp_attempt | CONSISTENT |
| demo_169-S0002 | approach | — | G1 | approach | grasp_attempt | CONSISTENT |
| demo_169-S0002 | approach | — | T0 | grasp | grasp_attempt | CONSISTENT |
| demo_169-S0002 | approach | — | T1 | approach | grasp_attempt | CONSISTENT |
| demo_169-S0002 | approach | — | T2 | approach | grasp_attempt, object_motion | EVENT_CONTRADICTION |
| demo_232-S0002 | approach | — | G0 | approach | grasp_attempt | CONSISTENT |
| demo_232-S0002 | approach | — | G1 | approach | grasp_attempt | CONSISTENT |
| demo_232-S0002 | approach | — | T0 | grasp | grasp_attempt | CONSISTENT |
| demo_232-S0002 | approach | — | T1 | grasp | grasp_attempt | CONSISTENT |
| demo_232-S0002 | approach | — | T2 | approach | grasp_attempt, object_motion | EVENT_CONTRADICTION |
| demo_72-S0002 | approach | — | G0 | approach | grasp_attempt | CONSISTENT |
| demo_72-S0002 | approach | — | G1 | approach | grasp_attempt | CONSISTENT |
| demo_72-S0002 | approach | — | T0 | approach | grasp_attempt, object_motion | CONSISTENT |
| demo_72-S0002 | approach | — | T1 | approach | grasp_attempt, object_motion | EVENT_CONTRADICTION |
| demo_72-S0002 | approach | — | T2 | approach | grasp_attempt | CONSISTENT |
| demo_180-S0001 | idle | — | G0 | idle | — | CONSISTENT |
| demo_180-S0001 | idle | — | G1 | idle | grasp_attempt | CONSISTENT |
| demo_180-S0001 | idle | — | T0 | idle | object_motion | EVENT_CONTRADICTION |
| demo_180-S0001 | idle | — | T1 | idle | grasp_attempt | CONSISTENT |
| demo_180-S0001 | idle | — | T2 | approach | grasp_attempt | CONSISTENT |
| demo_71-S0003 | approach | grasp_attempt | G0 | grasp | grasp_attempt | CONSISTENT |
| demo_71-S0003 | approach | grasp_attempt | G1 | INVALID | — | CELL_INVALID |
| demo_71-S0003 | approach | grasp_attempt | T0 | grasp | grasp_attempt | CONSISTENT |
| demo_71-S0003 | approach | grasp_attempt | T1 | approach | grasp_attempt, object_motion | EVENT_CONTRADICTION |
| demo_71-S0003 | approach | grasp_attempt | T2 | approach | grasp_attempt, object_motion | EVENT_CONTRADICTION |
| demo_172-S0004 | place | release_attempt | G0 | grasp | grasp_attempt | CONSISTENT |
| demo_172-S0004 | place | release_attempt | G1 | idle | object_motion | EVENT_CONTRADICTION |
| demo_172-S0004 | place | release_attempt | T0 | grasp | grasp_attempt | CONSISTENT |
| demo_172-S0004 | place | release_attempt | T1 | idle | object_motion | EVENT_CONTRADICTION |
| demo_172-S0004 | place | release_attempt | T2 | idle | object_motion | EVENT_CONTRADICTION |

Conflict-type distribution over 45 cells: `PERCEPTION_OR_PHASE_MISS` **13**,
`CONSISTENT` **20**, `EVENT_CONTRADICTION` **9**, `OBSERVED_BUT_NOT_LABELED` **2**,
`CELL_INVALID` **1**. `PHASE_EVENT_ENTAILMENT_MISS` **0**.

Full per-cell rows including the verbatim `observation_note`, evidence frames and
existing QC are in the local `outputs/g3d2r/full_fallback_r1/phase_event_qc_replay.jsonl`.

## 4. Direct answers

1. **What phase did the three `object_motion` misses predict?**
   `demo_2`, `demo_159`, `demo_4` — all 15 cells predicted `grasp`, except
   `demo_4`/T0 and `demo_159`/T0 which predicted `retract`. **No cell ever
   predicted `transport` or `lift` on these three segments.**
2. **Did any prediction assert `transport`/`lift` without `object_motion`?**
   No. Across all 59 valid cells only **one** asserted `transport`
   (`demo_183-S0003`/T2) and it *did* include `object_motion`. So the specific
   `PHASE_EVENT_ENTAILMENT_MISS` pattern never actually occurred.
3. **Did the note describe the object moving with the gripper?** For the 15
   misses, mostly **no** — 13 deny or omit object motion ("未见明显位移",
   "can remains stationary", "No object motion observed"). Two cells do describe
   it: `demo_2`/G0 ("夹爪与物体保持相对位置变化") and `demo_4`/T1
   ("物体位置有微小位移") — both still omit the `object_motion` event
   (`OBSERVED_BUT_NOT_LABELED`).
4. **Did some cells describe only EEF/gripper motion, not object motion?** Yes —
   this is the dominant pattern (13/15). The model tracked the arm/gripper and
   explicitly stated the object did not move.
5. **Any cell that said the object was static yet reported `object_motion`?**
   Yes, **9** `EVENT_CONTRADICTION` cells, concentrated in the state/temporal
   arms: `demo_172` G1/T1/T2, `demo_180` T0, `demo_169` T2, `demo_232` T2,
   `demo_72` T1, `demo_71` T1/T2.
6. **Phase correct but event missed?** **0** cells (because no arm produced the
   correct `transport` phase on the three positives).
7. **Phase and event both wrong?** **25** of 59 valid cells (mostly the 15
   `object_motion` misses plus grasp/release confusions on `demo_172`,
   `demo_169`, `demo_232`, `demo_72`).
8. **Does the human reference itself contain `transport`/`lift` without
   `object_motion`?** **No.** All three `transport` rows carry `object_motion`,
   there is no `lift` row, and no other row is inconsistent with the schema.

## 5. P1.2 — human reference check

* No `Reference Conflict` was found: the 12 human rows use `phase_ref` and
  `event_types_ref` in line with the frozen definitions, and every non-empty
  `event_types_ref` is a subset of the allowed three event types.
* No human label was modified; no model output was used to "correct" the human
  reference. A blind re-audit is therefore **not** required by this evidence.
* The one known caveat is that the reference is only 12 Development segments, so
  it is a diagnostic set, never a held-out test.

## 6. Interpretation and limits

* The conflict is **real as an instruction defect** and it is **demonstrated**:
  `demo_2`/G0 and `demo_4`/T1 describe object displacement in their own note
  while omitting `object_motion`. That is exactly the behaviour the sentence
  licensed.
* But the conflict is **not the main cause** of the historical misses: on those
  cells the model misclassified the *phase* (grasp instead of transport) and
  explicitly reported the object as stationary. Fixing the wording alone cannot
  restore an event the model did not perceive.
* This audit cannot and does not claim to reconstruct the model's internal
  reasoning; it reports only the relationship between the emitted fields.

## 7. Follow-up (executed in this round)

* Prompt fix: `G3F_Phase_Event_Prompt_Design.md` (v0.2.2 candidate).
* Consistency QC: `G3F_Phase_Event_Output_Design.md`.
* Paired test of whether the fix helps: `G3F_Phase_Event_Plan.md` /
  `G3F_Phase_Event_Results.md`.
