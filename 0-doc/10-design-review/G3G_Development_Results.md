# G3G 12-Segment Development paired comparison — 2026-10-15

**Decision: `8B_NO_CONFIRMED_GAIN`.** The fresh schema-constrained Development run completed 48/48 planned cells, but the 8B missed two of six preregistered candidate gates. This is a Development screening result, not an independent or generalization result. No Independent Test, G3E, prompt search, or model training was run.

## Identity, protocol and completeness

Run ID: `development_20261015_schema_r1`; base Git HEAD: `318712d4d7624605cb4e55c1f7255d034cee74ce`. The 12 ordered G3C microset identities, episode boundaries, three source PNG SHA256s and frame indices came from the frozen `P2_G3_Taxonomy_v0_2_20261013` manifest. The local G3C 20-column multi-event human reference SHA256 is `ecc716860eaf7617e00c1b23812fb1394a2719851346580a24e057a7e1ac938c`; all 12 rows matched the frozen manifest on episode, boundaries, frame indices and PNG hashes. The human CSV and all raw requests/responses remain local.

Both models used llama.cpp `0.6.0-dev` build `11577` (`cbe28bb3c`), `ctx-size=4096`, temperature 0, seed 1234, max_tokens 512, three unchanged 128×128 RGBs, frozen Task A text and frozen v0.2.3 Task B text/schema. Task A used the original `json_object`; Task B used `json_object` with the original v0.2 schema embedded as `schema`, followed by independent full schema and frame-evidence validation. 4B used `-ngl 99`; 8B used `-ngl 32`. Model/mmproj SHA256s and prompt/schema hashes are recorded in each local arm manifest and match [the paired Pilot](G3G_Paired_Pilot_Results.md). Model-specific internal chat templates remain a comparability limitation, although both arms used the same backend and the model-visible text plus image bytes matched for all **24 pairs**.

4B ran first for 24 cells; its service was closed before 8B ran 24 cells. Each arm had **24/24 first-attempt valid, zero retries, zero failed**, HTTP 200 and `finish_reason=stop` throughout. No image drift, truncation, OOM or service failure occurred. All raw calls, request and PNG hashes, QC findings, resource samples, model identities and terminal states are in gitignored `outputs/g3g/development_20261015_schema_r1/`. No earlier Pilot or schema-check prediction was reused.

## Formal Task B metrics

The scoring uses the existing `truth()` and `score_pairs()` event-set definitions, including all multi-events per segment. The denominator is all 12 valid paired segments. Event presence treats a nonempty event set as positive.

| Metric | This-run 4B | This-run 8B | 8B minus 4B |
|---|---:|---:|---:|
| Motion phase correct / 12 | 6 (0.500) | 5 (0.417) | −1 |
| Event presence precision / recall / F1 | 0.667 / 1.000 / **0.800** | 0.700 / 0.875 / **0.778** | F1 −0.022 |
| Multi-event micro precision / recall / F1 | 0.538 / 0.636 / **0.583** | 0.700 / 0.636 / **0.667** | F1 **+0.083** |
| Multi-event TP / FP / FN | 7 / 6 / 4 | 7 / 3 / 4 | FP −3; TP and FN unchanged |
| Exact event-set match / 12 | 4 | 5 | +1 |
| `grasp_attempt` TP / FP / FN | 7 / 5 / 0 | 6 / 3 / 1 | one true grasp lost; two FP removed |
| `release_attempt` TP / FP / FN | 0 / 0 / 1 | 0 / 0 / 1 | unchanged |
| `object_motion` TP / FP / FN | 0 / 1 / 3 | 1 / 0 / 2 | one TP gained; one FP removed |
| Phase/event QC review candidates / 12 | 1 | 0 | −1 detected conflict |
| Task B first/final structure valid | 12/12; 12/12 | 12/12; 12/12 | equal |

The micro-F1 gain comes from **three fewer false event triggers**, with the same total true positives and false negatives. Event-presence F1 actually falls because 8B emits no event on one segment that has a human `release_attempt`. The QC review count is only the existing heuristic's detected evidence–label conflicts: 4B `demo_232` emits `object_motion` while its note says the object was stationary. It is not a complete semantic contradiction rate; for example, 8B `demo_169` describes an open gripper without closure but emits `grasp_attempt` and receives no QC flag.

## Formal Task A diagnostics

`Y/N/U` mean model answers yes/no/uncertain. For `Can position change`, both models say **yes on all three human `object_motion` positives** (`demo_2`, `demo_4`, `demo_159`): answer-level TP=3, FN=0 and positive-case recall=3/3 for each. The human reference has no explicit negative answers to the four Task A questions, so Can-motion FP, precision and F1 are **UNSCORABLE**. The other nine Can-motion cases and gripper-synchrony/open-close judgments are likewise unscorable against this reference; an absent event label is not converted to a negative visual-motion answer. All 96 Task A judgment frame-reference arrays contain only supplied frames. On the three positives, both arms cite frames including the human object-motion evidence pair, but legal citations do not prove the observations are correct.

| Task A answer distribution over 12 | 4B Y/N/U | 8B Y/N/U |
|---|---:|---:|
| Can visible | 12 / 0 / 0 | 12 / 0 / 0 |
| Can position change | 3 / 0 / 9 | 6 / 6 / 0 |
| Can moves with gripper | 3 / 0 / 9 | 1 / 8 / 3 |
| Gripper open-close change | 2 / 0 / 10 | 2 / 4 / 6 |

4B's three positive Can-motion answers describe mostly robot/gripper movement in their observations; 8B's three positive observations explicitly describe Can locations across frames. That is a qualitative evidence difference, not a scored perception gain. 8B also answers Can-motion **yes** on `demo_232`, `demo_183` and `demo_216`, whose human reference does not contain `object_motion`; those Task A answers require a separate visual reference before they can be counted as false positives.

## Twelve paired segments

Task A tuple order: **Can visible / Can position change / moves with gripper / gripper open-close change**. `Y=yes`, `N=no`, `U=uncertain`. Event sets are shown without event outcomes; the complete parsed outputs and notes remain local. Human phase and event sets are the frozen multi-event reference.

| Segment | Human phase; events | Task A 4B → 8B | Task B 4B phase; events | Task B 8B phase; events | 4B → 8B change |
|---|---|---|---|---|---|
| `demo_2-S0003` | `transport`; `{grasp_attempt, object_motion}` | Y/Y/Y/U → Y/Y/N/U | `grasp`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | Unchanged B miss: transport/object motion. |
| `demo_4-S0003` | `transport`; `{grasp_attempt, object_motion}` | Y/Y/Y/Y → Y/Y/Y/Y | `grasp`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | Unchanged B miss: transport/object motion. |
| `demo_28-S0003` | `approach`; `{grasp_attempt}` | Y/U/U/U → Y/N/N/U | `approach`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | Phase correct → wrong; event set unchanged correct. |
| `demo_180-S0001` | `idle`; `{}` | Y/U/U/U → Y/N/U/U | `idle`; `{grasp_attempt}` | `idle`; `{}` | False grasp removed; exact event set restored. |
| `demo_159-S0003` | `transport`; `{grasp_attempt, object_motion}` | Y/Y/Y/Y → Y/Y/U/U | `grasp`; `{grasp_attempt}` | `transport`; `{object_motion}` | Transport/object motion recovered; true grasp omitted. |
| `demo_169-S0002` | `approach`; `{}` | Y/U/U/U → Y/N/N/N | `grasp`; `{grasp_attempt}` | `approach`; `{grasp_attempt}` | Phase corrected; false grasp persists. |
| `demo_172-S0004` | `place`; `{release_attempt}` | Y/U/U/U → Y/N/N/N | `grasp`; `{grasp_attempt}` | `idle`; `{}` | False grasp removed; release remains missed and presence becomes false negative. |
| `demo_232-S0002` | `approach`; `{}` | Y/U/U/U → Y/Y/U/U | `approach`; `{grasp_attempt, object_motion}` | `grasp`; `{grasp_attempt}` | False object motion removed; false grasp persists; phase degrades. |
| `demo_71-S0003` | `approach`; `{grasp_attempt}` | Y/U/U/U → Y/N/N/N | `grasp`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | Unchanged phase miss; event set correct. |
| `demo_72-S0002` | `approach`; `{}` | Y/U/U/U → Y/N/N/N | `approach`; `{grasp_attempt}` | `approach`; `{grasp_attempt}` | False grasp unchanged. |
| `demo_183-S0003` | `grasp`; `{grasp_attempt}` | Y/U/U/U → Y/Y/N/U | `grasp`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | B remains correct; 8B A motion yes is unscored. |
| `demo_216-S0002` | `approach`; `{grasp_attempt}` | Y/U/U/U → Y/Y/N/Y | `approach`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | Phase correct → wrong; event set unchanged correct. |

The three human `object_motion` positives are **`demo_2-S0003`, `demo_4-S0003`, `demo_159-S0003`**. 4B misses all three in B; 8B recovers only `demo_159`. Both arms' A calls answer Can motion yes on all three, whereas the B calls for `demo_2` and `demo_4` deny clear displacement and omit `object_motion`. This directly shows task-conditioned inconsistency; whether its cause is visual attention, evidence selection or event mapping remains an inference. `demo_172` shows both models fail Place/Release. 8B's reduced FP is meaningful within this set, but costs one true grasp event and one event-presence detection.

## Cost and preregistered decision

| Actual 24 calls per arm | 4B | 8B |
|---|---:|---:|
| Total wall time; mean per cell | 88.87 s; 3.70 s | 201.89 s; 8.41 s |
| Prompt / completion tokens | 31,084 / 5,356 | 31,084 / 5,175 |
| Peak observed VRAM | 4,351 MiB | 6,201 MiB |
| Lowest observed free system RAM | 1,960 MiB | 1,046 MiB |

8B costs **+4.71 s per paired cell on average**, about **2.27×** wall time, and **+1,850 MiB** peak observed VRAM. 8B's lowest free RAM was only about **22 MiB above the runner's 1,024 MiB stop threshold**. No OOM or actual stop occurred, so this run is engineering-valid, but the small margin is a material constraint for another long run. Free-RAM minima include other host activity and do not isolate model allocation.

| Frozen Development gate | Observed | Result |
|---|---|---|
| Event micro-F1 gain ≥ +0.10 | +0.083 | **FAIL** |
| 8B `object_motion` TP ≥ 2 of 3 | 1 of 3 | **FAIL** |
| 8B `object_motion` FP ≤ 1 | 0 | PASS |
| Exact event-set matches gain ≥ 1 | 5 vs 4 | PASS |
| Phase correct count drop ≤ 1 | 5 vs 6 | PASS |
| Engineering validity no evident failure | 48/48 valid, no OOM; RAM margin narrow | PASS with resource caveat |

**Final decision: `8B_NO_CONFIRMED_GAIN`.** The 8B did not meet the mandatory F1 or object-motion recall gates, despite fewer false positives. The available scored Task A positive cases do not establish a perception gain; a `PERCEPTION_GAIN_MAPPING_BOTTLENECK` designation is therefore not justified. The results favor investigating why the same model can describe motion in A and deny it in B, and whether three 128×128 frames are sufficient, before committing to the cost of 8B. Any changed input or semantic mapping would need its own frozen, paired evaluation. This Development set has only 12 selected segments, a quantized model and sparse Task A human reference; it cannot establish population-level model-size effects. No Independent Test was started.
