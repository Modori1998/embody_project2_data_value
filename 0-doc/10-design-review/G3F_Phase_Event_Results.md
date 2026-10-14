# G3F Phase–Event Results — 2026-10-14

Base main: `05228ce2dfe5cb8a759b1b3d7431359ad296c5da`. Pre-registration:
`G3F_Phase_Event_Plan.md` (criteria also frozen in code as
`scripts/run_g3f_paired.py::SUCCESS_CRITERIA` before the full run). Raw
requests/responses stay in the gitignored `outputs/g3f/` tree; no RGB, HDF5,
human CSV or model weights are committed. The G3D2-R run and the frozen v0.2.1
prompt are untouched.

## 1. What was run

| Stage | Run ID | Cells | Result |
|---|---|---|---|
| Pilot (plumbing, pre-QC-tightening) | `outputs/g3f/pilot_r1` | 8 | 8/8 valid, `gate_pass=true` |
| Pilot (canonical, tightened QC) | `outputs/g3f/pilot_r2` | 8 | 8/8 valid, 0 retries, `gate_pass=true` |
| Full Development | `outputs/g3f/full_r1` | 24 | 24/24 valid, 0 retries, 0 failures, `gate_pass=true` |

`pilot_r1` exists only because Rule D of the review QC was tightened after it (a
review-layer-only change); it is kept as evidence and is not used as the gate.
The full run used `pilot_r2`.

Identity (both arms): model `Qwen3VL-4B-Instruct-Q4_K_M.gguf` +
`mmproj-Qwen3VL-4B-Instruct-F16.gguf`, schema v0.2 (`4cbec780…`), seed 1234,
temperature 0, max_tokens 512, protocol `fallback_json_object_retry_v1`.
Prompt SHAs: A `11b874a3…0e53b4`, B `61ac6bce…92c4702`. All 36 RGB SHA-256
verified; no input/model drift.

## 2. Reliability (both arms identical)

| Metric | A (v0.2.1) | B (v0.2.2) |
|---|---|---|
| Planned cells | 12 | 12 |
| First-attempt valid | 12 | 12 |
| Retry attempts | 0 | 0 |
| Retry recovered | 0 | 0 |
| Final valid / failed | 12 / 0 | 12 / 0 |
| Prompt tokens | 27,800 | 31,580 |
| Completion tokens | 1,773 | 2,233 |
| Wall seconds (summed) | 33.2 | 40.8 |

No structural failures, no retries, no circuit break triggered. B costs ~14%
more prompt tokens (the replacement text plus the self-check are longer).

## 3. Primary metrics — A vs B (12 segments)

| Metric | A (v0.2.1) | B (v0.2.2) | Δ (B−A) |
|---|---|---|---|
| Motion phase correct | 7 | 7 | 0 |
| Event-set exact match | 5 | 2 | −3 |
| Event-type micro precision | 0.636 | 0.421 | −0.215 |
| Event-type micro recall | 0.636 | 0.727 | +0.091 |
| **Event-type micro F1** | **0.636** | **0.533** | **−0.103** |
| Event-presence F1 | 0.842 | 0.800 | −0.042 |

Per event type (TP/FP/FN):

| Event | A | B |
|---|---|---|
| `grasp_attempt` | 7/4/0 | 6/4/1 |
| `object_motion` | **0/0/3** | **2/7/1** |
| `release_attempt` | 0/0/1 | 0/0/1 |

## 4. Pre-registered success criteria

| # | Criterion | Observed | Pass |
|---|---|---|---|
| 1 | micro-F1 Δ ≥ +0.10 | −0.103 | ✗ |
| 2 | ≥ 2 of 3 `object_motion` positives recovered | 2 (`demo_2`, `demo_159`) | ✓ |
| 3 | `object_motion` FP increase ≤ +1 | +7 | ✗ |
| 4 | phase-correct drop ≤ 1 | 0 | ✓ |
| 5 | event-set exact-match not lower | −3 | ✗ |
| 6 | JSON/Schema/frame evidence equal | both 24/24 valid | ✓ |

## 5. Decision

**`NO_GAIN`.**

The Phase–Event fix **does** raise `object_motion` recall from 0/3 to 2/3 and
does correct `demo_159` from `grasp` to `transport`. But it also makes the model
emit `object_motion` on 7 segments where the human says none, which lowers
overall event micro-F1 (0.636 → 0.533) and event-set exact match (5 → 2).
The pre-registered bar is not met, so this prompt variant is **rejected** and
prompt expansion stops here. It is not a candidate, and it must not be described
as an accuracy improvement.

## 6. P5 — per-segment A/B diagnosis

| Segment | Human | A phase/events | B phase/events | Change |
|---|---|---|---|---|
| demo_2-S0003 | transport / grasp+OM | grasp / grasp | grasp / grasp+**OM** | `EVENT_RECOVERED`, `IMPROVED` |
| demo_4-S0003 | transport / grasp+OM | grasp / grasp | grasp / grasp | `NO_CHANGE` (both wrong) |
| demo_28-S0003 | approach / grasp | approach / grasp ✓ | approach / grasp+**OM** | `EVENT_FALSE_POSITIVE_ADDED`, `REGRESSED` |
| demo_180-S0001 | idle / — | idle / — ✓ | idle / **OM** | `EVENT_FALSE_POSITIVE_ADDED`, `REGRESSED` |
| demo_159-S0003 | transport / grasp+OM | grasp / grasp | **transport** / **OM** | `PHASE_CORRECTED`, `EVENT_RECOVERED` |
| demo_169-S0002 | approach / — | approach / grasp | grasp / grasp+**OM** | `EVENT_FALSE_POSITIVE_ADDED` |
| demo_172-S0004 | place / release | grasp / grasp | grasp / grasp | `NO_CHANGE` (both wrong) |
| demo_232-S0002 | approach / — | approach / grasp | approach / grasp+**OM** | `EVENT_FALSE_POSITIVE_ADDED` |
| demo_71-S0003 | approach / grasp | grasp / grasp ✓ | grasp / grasp+**OM** | `EVENT_FALSE_POSITIVE_ADDED`, `REGRESSED` |
| demo_72-S0002 | approach / — | approach / grasp | approach / grasp+**OM** | `EVENT_FALSE_POSITIVE_ADDED` |
| demo_183-S0003 | grasp / grasp | grasp / grasp ✓ | grasp / grasp ✓ | `NO_CHANGE` (both correct) |
| demo_216-S0002 | approach / grasp | approach / grasp ✓ | approach / grasp+**OM** | `EVENT_FALSE_POSITIVE_ADDED`, `REGRESSED` |

Counts: `EVENT_RECOVERED` 2, `PHASE_CORRECTED` 1, `EVENT_FALSE_POSITIVE_ADDED` 7,
improved/exact 1, regressed 4, `NO_CHANGE` 3.

### What the notes show (why the FPs happen)

B's notes split cleanly:

* **Genuine recovery** — `demo_2` B: "物体在视觉上发生轻微位移"; `demo_159` B:
  "物体随夹爪在空间中移动". The new rule produced an observation-consistent,
  correct `object_motion`.
* **Over-call despite a static note** — `demo_180`, `demo_232`, `demo_72`,
  `demo_216`: B's note still says the object is static ("红色物体静止于桌面",
  "物体在桌面上静止", "杯子静止在木板上", "杯子在桌面上静止") yet the event set
  now contains `object_motion`. The new instruction partly fired mechanically,
  contradicting the model's own observation. The new QC flags all **4** of these.
* **Supported but human-disagreed** — `demo_28`, `demo_169`, `demo_71`: B's note
  describes motion ("随夹爪移动" / "发生轻微位移"), so it is internally consistent
  but the reference says no event.

`demo_180` (the old CLOSED-as-grasp case): A stayed correct (`idle`, no events);
B changed to `idle` + `object_motion` — the fix did not help and introduced an
error. `demo_172` (old spurious object motion): both A and B stayed wrong
(`grasp`), neither introduced `object_motion`; B's note is shorter and still
misses the release.

## 7. Consistency QC on the new run

Offline replay of `PHASE_EVENT_QC_V0_2_2_CANDIDATE` over `outputs/g3f/full_r1`:
arm A produced **0** findings; arm B produced **4**
`OBJECT_MOTION_NOTE_CONFLICT_CANDIDATE` findings — exactly the four
over-call cells above. False alerts on event-exact cells: **0** for both arms.
Rule A/B again fired **0** times (B still never asserted `transport` except
`demo_159`, where it included the event).

## 8. Answers to the Owner's questions

1. **Where was the prompt contradiction?** The v0.2.1 sentence licensed
   `events=[]` for sustained carry while the frozen schema says a visible object
   displacement entails `object_motion`. See `G3F_Phase_Event_Conflict_Audit.md`.
2. **Did `object_motion` exist since v0.1?** Yes — the event type and its
   definition are unchanged across v0.1/v0.2/v0.2.1; only the prompt's carry
   sentence conflicted with it.
3. **Were the three historical misses phase errors or event misses?** Phase
   errors: all 15 cells predicted `grasp`/`retract`, never `transport`, and their
   notes denied object motion. `phase-correct-but-event-missed` = **0**.
4. **Did the old model ever describe object motion yet omit the event?** Yes, two
   cells: `demo_2`/G0 and `demo_4`/T1 (`OBSERVED_BUT_NOT_LABELED`).
5. **What did the new QC catch, and did it false-alarm?** On G3D2-R it caught 12
   genuine note/event contradictions (all on wrongly-labelled object_motion) and
   10 grasp-note contradictions; on the new run it caught all 4 of B's
   self-contradictory FPs. It produced 2 flagged cells whose event set was
   already correct, but in both the note itself contradicts the label, so they
   are genuine inconsistencies rather than scoring errors. Rule A/B are blind to
   the historical misses (no `transport`/`lift` was ever predicted).
6. **What exactly changed in the prompt?** Only two edits: the carry sentence was
   replaced by an explicit Phase–Event coherence rule, and a short pre-output
   self-check was added. See `G3F_Phase_Event_Prompt_Design.md`.
7. **Did the 8 pilot cells pass?** Yes, 8/8, with both prompt SHAs recorded.
8. **Result of the 24 Development cells?** 24/24 valid; A micro-F1 0.636,
   B 0.533.
9. **Did `object_motion` TP/FP/FN improve?** TP 0→2, FN 3→1 (improved), but FP
   0→7 (much worse). Net F1 contribution negative.
10. **Net gain on phase / event-set / micro-F1?** Phase 7→7 (flat), exact match
    5→2 (worse), micro-F1 0.636→0.533 (worse). No net gain.
11. **Is two-stage annotation / Can Position / G3E worth it?** The conflict was
    real but is **not** the main cause of the misses. A prompt-only fix trades a
    small recall gain for a large precision loss, so more prompt stacking is not
    justified. The binding limit looks like *which frames are shown*: three fixed
    keyframes cannot distinguish "object moves with the gripper" from "gripper
    approaches a static object" for these segments. **G3E Adaptive Keyframes** is
    the justified next hypothesis (pre-registered, Episode-disjoint), not
    two-stage annotation or Can Position on the current inputs.
12. **GitHub / tests / Run ID / blockers** — below.

Development cohort only. Even the recovered `object_motion` cases are diagnostic,
not a performance claim; an Episode-disjoint held-out set is still required
before any method is credited.

## 9. Cost

* Full run: 24 model calls (no retries), 59,380 prompt + 4,006 completion tokens,
  73.97 s summed latency. Pilot `pilot_r2`: 8 calls, 23.39 s summed latency.
* GPU: RTX 4060 Laptop, single frozen `llama-server`, ≤ ~4.4 GiB VRAM.

## 10. Artifacts

* Prompt: `src/project2_g3/semantic_prompt.py` (`PROMPT_TEMPLATE_V0_2_2`).
* QC: `src/project2_g3/phase_event_qc.py`.
* Runner: `scripts/run_g3f_paired.py`.
* Offline replay: `scripts/replay_g3f_phase_event_qc.py`.
* Tests: `tests/test_g3f_phase_event.py`, `tests/test_g3d2r_reliability.py`.
* Local results (gitignored): `outputs/g3f/pilot_r2`, `outputs/g3f/full_r1`.
* Sample order, hashes and criteria: `outputs/g3f/full_r1/run_manifest.json`.
