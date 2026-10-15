# G3G schema-constrained paired Pilot — 2026-10-15

**Decision: `PILOT_PASS` (engineering gate only).** All 16 planned cells finished on the first request and passed their task-specific parser, schema, and frame-reference checks. This four-segment Pilot is an initial diagnostic, not a Development score or a generalization claim. The run stopped after 16 cells; no 12-segment Development experiment was started.

## Run identity and engineering gate

Base Git commit: `6a2184747dead033da010a20a12768f17453f33f`. New local run: gitignored `outputs/g3g/pilot_20261015_schema_r1/`. Previous failed Pilot and G3G-P1 schema-check outputs were retained unchanged. The runner's opt-in `--schema-constrained` mode sends the original Task A `json_object` request and Task B `json_object` with the frozen `json_schema_v0_2()` embedded as `schema`. Independent validation still checks `uniqueItems` and the rest of the schema. The historical runner's default wire format is unchanged.

Both arms used llama.cpp `0.6.0-dev` build `11577` (`cbe28bb3c`), `ctx-size=4096`, temperature 0, seed 1234, max_tokens 512, and serial single-model service. 4B used `-ngl 99`; 8B used `-ngl 32`. 4B GGUF/mmproj SHA256: `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` / `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331`. 8B GGUF/mmproj SHA256: `67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2` / `ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38`. Frozen prompt-template SHA256: `cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1`; schema SHA256: `4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7`.

The runner rechecked model/mmproj hashes and each original PNG hash and dimension. All eight paired text-plus-three-image content hashes, PNG hashes, frame indices, and request formats matched between arms. Every response was HTTP 200 with `finish_reason=stop`; no truncation, OOM, service error, or retry occurred. 4B: 8/8 first-valid, 0 retried, 0 failed. 8B: 8/8 first-valid, 0 retried, 0 failed. Both services were shut down after their arms.

| Actual requests | 4B | 8B |
|---|---:|---:|
| Total wall time | 29.78 s | 60.33 s |
| Task A / Task B wall time | 17.47 / 12.32 s | 33.93 / 26.39 s |
| Prompt tokens | 10,359 | 10,359 |
| Completion tokens | 1,809 | 1,628 |
| Peak observed VRAM | 4,351 MiB | 6,201 MiB |
| Lowest observed free RAM | 4,919 MiB | 3,848 MiB |

8B took about 2.03 times the wall time and used 1,850 MiB more peak VRAM. The free-RAM minima include unrelated host activity and are not an isolated model-memory measurement. Neither arm crossed the run's 1,024 MiB free-RAM stop threshold.

## Four-segment paired observations

Human phase and event sets below come from the frozen local `G3C_12_Segment_Human_MultiEvent_Reference_v2.csv` (SHA256 `ecc716860eaf7617e00c1b23812fb1394a2719851346580a24e057a7e1ac938c`). Task A shows `Can visible / Can position change / moves with gripper / gripper open-close change`; `?` means the model said `uncertain`. The human reference does not independently answer every Task A subquestion; those entries remain **UNSCORABLE**, especially gripper synchrony and opening/closing. Human `object_motion` supports a positive Can-motion reference on the two transport segments. Lack of an event label is not treated as a negative Task A visual-motion answer.

| Segment | Human phase; event set | 4B Task A | 8B Task A | 4B Task B phase; event set | 8B Task B phase; event set | Paired reading |
|---|---|---|---|---|---|---|
| `demo_2-S0003` | `transport`; `{grasp_attempt, object_motion}` | yes / yes / yes / ? | yes / yes / no / ? | `grasp`; `{grasp_attempt}` | `grasp`; `{grasp_attempt}` | Both detect Can position change in A, yet B still denies displacement and misses transport/object motion. 8B's gripper-synchrony answer changed to no; no independent reference is available to score it. |
| `demo_159-S0003` | `transport`; `{grasp_attempt, object_motion}` | yes / yes / yes / yes | yes / yes / ? / ? | `grasp`; `{grasp_attempt}` | `transport`; `{object_motion}` | 8B fixes phase and detects object motion in B, but drops the human `grasp_attempt`; A Can-motion judgment is unchanged. |
| `demo_169-S0002` | `approach`; `{}` | yes / ? / ? / ? | yes / no / no / no | `grasp`; `{grasp_attempt}` | `approach`; `{grasp_attempt}` | 8B fixes phase, but both still falsely trigger grasp. A answers beyond visibility lack an independently scored human Task A reference. |
| `demo_180-S0001` | `idle`; `{}` | yes / ? / ? / ? | yes / no / no / no | `idle`; `{grasp_attempt}` | `idle`; `{}` | 8B removes the false grasp event; phase remains correct. A answers beyond visibility remain unscored. |

Notes from Task B: on `demo_2`, both models describe contact or a grasp attempt and no clear Can displacement. On `demo_159`, 4B says no clear lifting/transport, while 8B describes the object moving between boxes. On `demo_169`, 8B explicitly says the gripper stayed open without closure, yet emits `grasp_attempt`; this is an observation-to-event tension that the current phase/event QC did not flag. On `demo_180`, 4B describes an open gripper without contact while emitting `grasp_attempt`; 8B emits no event. All Task B outputs passed structural/evidence validation; that does not make their event labels correct.

For the **four selected Pilot segments only**, 4B has 2 event true positives, 2 false positives, and 2 false negatives (micro-F1 0.500); 8B has 2/1/2 (micro-F1 0.571). 8B object-motion recall is 1/2 versus 4B 0/2, with no object-motion false positive in either arm. 8B also misses one `grasp_attempt` positive while reducing one negative-sample false grasp. Exact event-set matches are 0/4 for 4B and 1/4 for 8B; phase matches are 1/4 and 3/4. These selected cases do not satisfy or replace the preregistered 12-segment Development decision rule. The two positives' Task A Can-motion answers are identical, so the Pilot does **not** demonstrate improved Can-motion perception; the Task B change on `demo_159` may reflect task-conditioned interpretation or event mapping. `demo_2` shows that a correct Task A motion judgment can coexist with a Task B miss.

## Next gate

`PILOT_PASS` means the paired schema-constrained protocol is runnable and resource-safe under this workload. A fresh 12-segment paired Development run is technically permissible as a **separate next step**, using the already frozen thresholds and retaining per-attempt failures. It was not run here. No prompt, schema, taxonomy, image, human label, or historical experiment result was changed.
