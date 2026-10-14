# G3F-P1 Design — Owner Semantic Decision, v0.2.3, and FP audit — 2026-10-14

Base main: `2969475e8e6ff6b37a33010ad21cf1116beaf11e`.

## 1. Owner Semantic Decision (frozen)

The frozen Schema (`src/project2_g3/semantic_schema.py`) is the single source of
truth for the following, and v0.2.3 must express it without contradiction:

1. `transport` belongs **only** to `motion_phase` (single-choice). It is **not**
   an event, and no same-named event may be added.
2. `object_motion` belongs **only** to `events[]`; `events[]` holds exactly
   `grasp_attempt`, `release_attempt`, `object_motion`.
3. `motion_phase` and `events[]` are **not** one-to-one; a phase does not
   automatically create or forbid an event, but they must stay semantically
   consistent.
4. Confirming `transport`/`lift` requires visible **object** displacement
   evidence; a moving EEF or a closed gripper alone is insufficient.
5. If at least two comparable target frames show a discernible object
   displacement, `object_motion` should be annotated regardless of the dominant
   phase.
6. A moving EEF alone cannot support `object_motion`.
7. Sustained carry does **not** force a `grasp_attempt` (or `release_attempt`)
   inside the current Segment; those events require an observed local process.

**Status marker.** The G3F round's performance conclusion `NO_GAIN` is preserved
unchanged as a *stage-error-conditional* result. It is explicitly annotated
`SEMANTIC_CORRECTION_REQUIRED`: the old prompt expressed a definition that
contradicts the frozen taxonomy, so a favourable F1 for v0.2.1 does not license
restoring the wrong definition. Correctness of the semantic specification and
the model's ability to execute it are two separate questions.

Frozen and never overwritten: `PROMPT_TEMPLATE_V0_2_1`,
`PROMPT_TEMPLATE_V0_2_2`, the original Schema, and all historical run output.

## 2. v0.2.3 — minimal correct implementation

New version `P2_G3_ARGUS_INSPIRED_PROMPT_V0_2_3_CANDIDATE`, built from the frozen
v0.2.1 template by replacing **only** the one conflicting sentence:

Removed:

> `- 长距离的连续搬运可能确实 \`events=[]\`；**不要**为了凑事件率而编造事件。`

Replacement (frozen wording):

> 持续搬运本身不要求当前 Segment 重新发生 grasp_attempt 或 release_attempt；但如果至少两张可比目标帧明确支持物体发生可分辨位移，无论主要动作阶段是什么，都应标注 object_motion。如果只有夹爪或 EEF 移动、物体位移不可辨认，则不得据此添加 object_motion。

v0.2.3 deliberately does **not** include the v0.2.2 ten-line expansion or the
pre-output self-check, so `C − B` isolates the effect of that over-triggering
expansion from the minimal fix.

Diff (v0.2.1 → v0.2.3), exactly one removed and one added line:

```diff
@@ section 5 (events) @@
-- 长距离的连续搬运可能确实 `events=[]`；**不要**为了凑事件率而编造事件。
+- 持续搬运本身不要求当前 Segment 重新发生 grasp_attempt 或 release_attempt；但如果至少两张可比目标帧明确支持物体发生可分辨位移，无论主要动作阶段是什么，都应标注 object_motion。如果只有夹爪或 EEF 移动、物体位移不可辨认，则不得据此添加 object_motion。
```

Unchanged: model, RGB inputs, Segment identity, Schema, `motion_phase` enum,
`event_type` enum, phase evidence rules, event trigger rules, evidence rubric,
required-field block, sampling parameters, retry protocol. No known sample answer
is inserted.

### Prompt SHA-256

| Version | SHA-256 |
|---|---|
| v0.2.1 (A, frozen) | `11b874a3daba9d42398a50bef8473c01924a672f06acda09e0ac3933110e53b4` |
| v0.2.2 (B, frozen) | `61ac6bcea3a67a92b6dbd3a3d55209f990ad09f147aba84cb4b8b1cf892c4702` |
| v0.2.3 (C) | `cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1` |

`tests/test_g3f_phase_event.py` pins all three SHAs (byte-drift protection) and
asserts that the v0.2.1→v0.2.3 diff is exactly one line.

## 3. Appendix — v0.2.2 `object_motion` false-positive audit (zero GPU)

The 7 `object_motion` FPs produced by v0.2.2 on the 12 Development segments
(`outputs/g3f/full_r1`), classified by inspecting the stored note and the three
frozen RGB frames:

| Segment | v0.2.2 note | Class |
|---|---|---|
| demo_180-S0001 | "红色物体静止于桌面，无明显运动或交互发生" | A `NOTE_STATIC_EVENT_MOTION` |
| demo_232-S0002 | "物体在桌面上静止，未见明显位移" | A `NOTE_STATIC_EVENT_MOTION` |
| demo_72-S0002 | "杯子在木板上静止" | A `NOTE_STATIC_EVENT_MOTION` |
| demo_216-S0002 | "Can is stationary on the table." | A `NOTE_STATIC_EVENT_MOTION` |
| demo_28-S0003 | "物体在视觉上随夹爪移动" | B `FALSE_VISUAL_MOTION` |
| demo_169-S0002 | "物体在视觉上发生轻微位移" | B `FALSE_VISUAL_MOTION` |
| demo_71-S0003 | "杯子在视觉上随夹爪轻微移动" | B `FALSE_VISUAL_MOTION` |

* Class C `PHASE_EVENT_CONFLICT`: **0** (phase `approach` with `object_motion`
  is not itself a conflict).
* Class D `REFERENCE_UNCERTAIN`: **0** — see below.

### Independent frame check (P3.4)

The three frozen RGB frames for `demo_28` (14/38/62), `demo_169` (4/16/28) and
`demo_71` (34/70/106) were inspected directly. In all three the can stays in
essentially the same place on the tray while the gripper/end-effector moves down
and toward it. So the "object moves with the gripper" claims are **not**
reference errors: they are genuine visual misjudgements in which EEF/gripper
motion is mistaken for object displacement. No can-displacement evidence is
independently visible in those frames, and the human labels are consistent with
the frames.

### Answers

1. All **4** self-contradictory FPs (class A) are detected by the existing QC
   (`OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE`).
2. The remaining **3** (class B) are real visual-motion misjudgements, not label
   problems.
3. The new sentence in v0.2.2 over-triggered: it added `object_motion` even where
   the model's own note says the object is static (class A), and it also raised
   false motion calls that the note endorses (class B).
4. No independently verifiable can displacement exists in the three RGB frames
   for these FPs. Can GT and extra RGB are **not** fed to the model this round.
