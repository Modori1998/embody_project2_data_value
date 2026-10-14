# G3F-P1 Results — 2026-10-14

Base main: `2969475e8e6ff6b37a33010ad21cf1116beaf11e`. Pre-registration:
`G3F_P1_Plan.md` (criteria also frozen in `scripts/run_g3f_p1_paired.py` before
the full run). Raw requests/responses stay in the gitignored `outputs/g3f_p1/`
tree. The G3F `NO_GAIN` result and every historical run/prompt are untouched.

## 1. Runs

| Stage | Run ID | Cells | Result |
|---|---|---|---|
| Pilot | `outputs/g3f_p1/pilot_r1` | 4 × 3 = 12 | 12/12 valid, `gate_pass=true` |
| Full Development | `outputs/g3f_p1/full_r1` | 12 × 3 = 36 | 36/36 valid, 0 retries, 0 failures, `gate_pass=true` |

Arms (freshly run in this round; no historical response spliced in):

| Arm | Prompt | SHA-256 |
|---|---|---|
| A | v0.2.1 | `11b874a3daba9d42398a50bef8473c01924a672f06acda09e0ac3933110e53b4` |
| B | v0.2.2 | `61ac6bcea3a67a92b6dbd3a3d55209f990ad09f147aba84cb4b8b1cf892c4702` |
| C | v0.2.3 | `cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1` |

## 2. Primary metrics (12 segments, identical cohort)

| Metric | A (v0.2.1) | B (v0.2.2) | C (v0.2.3) |
|---|---|---|---|
| Event micro-F1 | **0.636** | 0.533 | 0.560 |
| Event micro precision | 0.636 | 0.421 | 0.500 |
| Event micro recall | 0.636 | 0.727 | 0.636 |
| Event-set exact match | **5** | 2 | 3 |
| Motion phase correct | **7** | 7 | 6 |
| Event-presence F1 | 0.842 | 0.800 | 0.800 |
| `object_motion` TP/FP/FN | **0/0/3** | 2/7/1 | **0/2/3** |
| `grasp_attempt` TP/FP/FN | 7/4/0 | 6/4/1 | 7/5/0 |
| `release_attempt` TP/FP/FN | 0/0/1 | 0/0/1 | 0/0/1 |

### Primary contrasts

* **C − A**: micro-F1 −0.076, exact −2, phase −1, `object_motion` TP 0 → 0
  (no recovery), `object_motion` FP 0 → 2.
* **C − B**: micro-F1 +0.027, exact +1, `object_motion` FP **7 → 2** (the
  minimal fix avoids most of the expansion's over-triggering), but
  `object_motion` TP **2 → 0** (it also loses the two true recoveries).

## 3. Pre-registered release criteria (C vs A)

| # | Criterion | Observed | Pass |
|---|---|---|---|
| 1 | C `object_motion` TP ≥ 2 | 0 | ✗ |
| 2 | C `object_motion` FP ≤ 2 | 2 | ✓ |
| 3 | C micro-F1 ≥ A | 0.560 < 0.636 | ✗ |
| 4 | C exact match ≥ A | 3 < 5 | ✗ |
| 5 | C phase correct ≥ A − 1 | 6 ≥ 6 | ✓ |
| 6 | engineering validity equal | 36/36 valid, identity OK | ✓ |

**Decision: `NOT_READY`** — C fails the release bar, so the 4B automatic
annotation quality is marked NOT_READY for an independent evaluation.

The wrong old semantics is **not** restored: v0.2.3 stays as the
semantically-correct candidate implementation, and the G3F `NO_GAIN` result is
preserved unchanged.

## 4. Per-segment A/B/C predictions

| Segment | Human | A | B | C |
|---|---|---|---|---|
| demo_2-S0003 | transport / grasp+OM | grasp / grasp | grasp / grasp+**OM** | grasp / grasp |
| demo_4-S0003 | transport / grasp+OM | grasp / grasp | grasp / grasp | grasp / grasp |
| demo_28-S0003 | approach / grasp | approach / grasp ✓ | approach / grasp+**OM** | approach / grasp ✓ |
| demo_180-S0001 | idle / — | idle / — ✓ | idle / **OM** | idle / **grasp** |
| demo_159-S0003 | transport / grasp+OM | grasp / grasp | **transport** / **OM** | grasp / grasp |
| demo_169-S0002 | approach / — | approach / grasp | grasp / grasp+**OM** | **grasp** / grasp |
| demo_172-S0004 | place / release | grasp / grasp | grasp / grasp | grasp / grasp |
| demo_232-S0002 | approach / — | approach / grasp | approach / grasp+**OM** | approach / grasp+**OM** |
| demo_71-S0003 | approach / grasp | grasp / grasp ✓ | grasp / grasp+**OM** | grasp / grasp ✓ |
| demo_72-S0002 | approach / — | approach / grasp | approach / grasp+**OM** | approach / grasp |
| demo_183-S0003 | grasp / grasp | grasp / grasp ✓ | grasp / grasp ✓ | grasp / grasp ✓ |
| demo_216-S0002 | approach / grasp | approach / grasp ✓ | approach / grasp+**OM** | approach / grasp+**OM** |

(✓ = event set exactly matches the reference.)

### Wrong → right / right → wrong

* **A → C**: nothing improved; two regressions — `demo_180` (`idle`, no event,
  correct under A → `idle` + `grasp_attempt`) and `demo_216` (correct under A →
  `approach` + `object_motion`). `demo_169`'s phase moved from correct
  (`approach`) to wrong (`grasp`).
* **B → C**: C removed the `object_motion` false positives on `demo_28`,
  `demo_71`, `demo_72`, `demo_169` and `demo_180` (7 → 2), and recovered
  `demo_183`, `demo_28`; but it also dropped B's two true recoveries
  (`demo_2`, `demo_159`). Two `object_motion` FPs remain (`demo_232`,
  `demo_216`).

### Why C missed the true positives

C's notes on the three `object_motion` positives state the object did not move:

* `demo_2` C: "物体位于桌面上，未见明显位移。"
* `demo_4` C: "物体位于桌面上，未见明显位移。"
* `demo_159` C: "物体位于夹爪…物体位于托盘上，未见明显位移。"

The model does **not** perceive the can displacement at all, so no amount of
Phase–Event mapping can emit the event. Conversely, C's two residual FPs
(`demo_232`, `demo_216`) carry notes that say the can is stationary
("杯子在桌面上静止" / "Can is stationary on the table.") while the event set
claims `object_motion` — self-contradiction, not perception.

## 5. Phase–Event QC findings (offline replay)

| Arm | Rule C (`OBJECT_MOTION_NOTE_CONFLICT`) | Rule D | Rule A/B |
|---|---|---|---|
| A | 0 | 0 | 0 |
| B | 4 | 0 | 0 |
| C | **2** | 0 | 0 |

* C's 2 findings are exactly its 2 `object_motion` FPs (`demo_232`, `demo_216`):
  the QC catches every self-contradictory `object_motion` C produced.
* Rule A/B fire 0 times: no arm asserted `transport`/`lift` without
  `object_motion`, and C never asserted `moving_with_gripper`.
* Missing-object-motion cells detected by the rules: **0/3** — the blind spot is
  unchanged (a model that predicts `grasp` and denies motion cannot trip a
  "transport implies object_motion" rule).

## 6. Diagnosis (P6) and next step

* C still misses all three real object displacements, and its own
  `observation_note` says the object is static. → The bottleneck is **visual
  evidence extraction**, not Phase–Event mapping or prompt wording.
* Two FPs are note/event self-contradictions (caught by QC) → keep the
  non-destructive consistency QC; do not auto-edit events.
* No case where the note correctly described can motion but the event was missing
  appears in this round.
* The model cannot reliably separate can motion from EEF/gripper motion with three
  fixed frames.

Consequently the next phase should be **G3E Adaptive Keyframes**, pre-registered,
with arms **E0** (raw 3 frames), **E1** (5 uniformly selected frames) and **E2**
(5 adaptively selected frames). RGB-derived Can Position may be kept as a
separate candidate input; simulator Object GT must never enter the formal input.
This is a *hypothesis*: the 12 Development samples alone cannot prove that extra
frames are required.

## 7. Cost

| Arm | Prompt tok | Completion tok | Wall s |
|---|---|---|---|
| A | 27,800 | 1,786 | 32.0 |
| B | 31,580 | 2,216 | 40.3 |
| C | 28,340 | 1,844 | 32.9 |
| **Total** | **87,720** | **5,846** | **105.19** |

36 model calls, 0 retries, 0 failures; single frozen `llama-server`, ≤ ~4.4 GiB
VRAM. Pilot `pilot_r1`: 12 calls, 35.16 s.

## 8. Answers to the Owner

1. **Why the prompt had to be fixed** — v0.2.1 licensed `events=[]` for sustained
   carry while the frozen taxonomy says a visible object displacement entails
   `object_motion`. A higher F1 for the defective prompt does not make the
   definition correct.
2. **What v0.2.3 changed vs v0.2.2** — only the single conflicting sentence was
   replaced; v0.2.2's ten-line expansion and its pre-output self-check were not
   carried over (byte-checked).
3. **Did `object_motion` TP/FP improve?** — C: TP 0 (unchanged from A), FP 2
   (down from B's 7 but up from A's 0). Net: not improved.
4. **Which cases changed?** — C fixed B's over-triggering on 5 segments; C
   regressed `demo_180` and `demo_216` vs A; C recovered nothing that A missed.
5. **Perception or mapping?** — Perception (visual evidence extraction). The
   model's own notes call the object static on the three true positives.
6. **Is the new semantics preserved?** — Yes. v0.2.3 implements the correct
   taxonomy and is retained; the incorrect rule is not restored.
7. **Is the 4B VLM ready for an independent evaluation?** — **No.** Marked
   `NOT_READY`.
8. **Start G3E?** — Recommended as a pre-registered next phase (E0/E1/E2), not as
   a proven necessity.

## 9. Artifacts

* Prompt: `src/project2_g3/semantic_prompt.py` (`PROMPT_TEMPLATE_V0_2_3`).
* Runner: `scripts/run_g3f_p1_paired.py`.
* QC: `src/project2_g3/phase_event_qc.py`; replay:
  `scripts/replay_g3f_phase_event_qc.py`.
* Tests: `tests/test_g3f_phase_event.py` (11 tests; pins all three prompt SHAs).
* Local results (gitignored): `outputs/g3f_p1/pilot_r1`, `outputs/g3f_p1/full_r1`.
