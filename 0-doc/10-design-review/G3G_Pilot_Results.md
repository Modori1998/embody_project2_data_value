# G3G 16-cell Pilot — early stop, `PILOT_FAIL` (2026-10-14)

This is an engineering Pilot, **not** the 12-segment Development comparison. The frozen G3G design, v0.2.3 prompt, v0.2 schema, taxonomy and human reference were not modified. No historical 4B response was reused. Local raw requests, responses, resource samples and server logs are in gitignored `outputs/g3g/pilot_20261014_r1/` and adjacent `pilot_20261014_r1_{4b,8b}_server.log`.

## Run identity and stopping point

| Item | 4B | 8B |
|---|---|---|
| GGUF SHA256 | `66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a` | `67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2` |
| FP16 mmproj SHA256 | `256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331` | `ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38` |
| Backend | llama.cpp `0.6.0-dev` build `11577` commit `cbe28bb3c` | Same executable |
| GPU layers / ctx | 99 / 4096 | 32 / 4096 |
| Planned cells | 8 | 8 |
| Attempted cells | 8 | 4 |
| First-attempt structurally valid | 8/8 | 2/4 |
| Retry attempts / recovered | 0 / 0 | 2 / 0 |
| Final valid / failed | 8 / 0 | 2 / 2 |

4B ran first and its service was closed before 8B was loaded. The Pilot stopped after `demo_159-S0003` Task B: both 8B Task B cells attempted so far (`demo_2`, `demo_159`) returned HTTP 200 and complete JSON, but omitted the **top-level** required `evidence_frame_indices` on the first attempt and the single permitted retry. Event-internal frame references do not satisfy the top-level schema. Both also claimed `evidence_quality=sufficient` without a top-level citation. The two retries repeated the same omissions. This met the Pilot's global stop condition for broadly invalid Schema output. `demo_169` and `demo_180` were **not** sent to 8B; no result is imputed for them.

Each arm used the same frozen PNG bytes and order, Task A text and Task B v0.2.3 renderer, JSON-object response mode, max_tokens 512, temperature 0 and seed 1234. For all four cells sent to both models, hashes of the complete model-visible text-plus-images content match. All 14 actual requests ended with `finish_reason=stop`, and the server logs show three 128×128 images handled per initial cell (subsequent retries used cache). There was no output truncation or GPU OOM. Model-specific chat templates and tokenizer internals may still differ; therefore a completed performance contrast would require the full paired run and further engineering review.

## Resource and runtime observations

| Metric, all actual attempts | 4B, 8 attempts | 8B, 6 attempts |
|---|---:|---:|
| Wall time total | 29.87 s | 41.30 s |
| Prompt tokens total | 10,359 | 9,901 |
| Completion tokens total | 1,809 | 1,132 |
| Peak observed VRAM | 4,924 MiB | 6,201 MiB |
| Lowest observed free system RAM | 4,012 MiB | 5,157 MiB |

These totals cover different attempt counts and cannot be compared as a cost ratio. On the two paired Task A first calls, 4B took 5.79/5.09 s and 8B took 9.03/9.81 s (`demo_2`/`demo_159`), roughly 1.7× the mean wall time. The absolute free-RAM minima reflect different host baselines during the serial runs. Neither arm showed a resource-danger signal during these calls.

## Per-segment observations (Pilot only)

| Segment | 4B Task A | 8B Task A | 4B Task B (valid JSON/schema) | 8B Task B |
|---|---|---|---|---|
| `demo_2-S0003` | Can visible **yes**, position change **yes**, moves with gripper **yes**, gripper change uncertain | yes / yes / **no** / uncertain | phase `grasp`; `{grasp_attempt}`; note describes closed gripper/contact and no obvious displacement | **INVALID** twice: missing top-level evidence frames; unscorable as a formal annotation. Raw content says `grasp`, `{grasp_attempt}`, and denies can displacement. |
| `demo_159-S0003` | yes / yes / **yes** / yes | yes / yes / **uncertain** / uncertain | phase `grasp`; `{grasp_attempt}`; note denies clear lifting/transport | **INVALID** twice: same missing top-level field. Raw content says `transport`, `{object_motion}` and describes object travel, but is not a valid Task B result. |
| `demo_169-S0002` | Can visible yes; other three judgments uncertain | **not run** | phase `grasp`; `{grasp_attempt}`; note says no obvious can displacement | **not run** |
| `demo_180-S0001` | Can visible yes; other three judgments uncertain | **not run** | phase `idle`; `{grasp_attempt}`; note says gripper open, no contact, can stationary; QC flags phase-event conflict | **not run** |

Both models' Task A outputs reported Can position change on the two attempted positive examples; this Pilot supplies no evidence that 8B detects that particular motion more often than 4B. The 8B `demo_159` Task B raw content looks promising for transport/object motion, but its required schema field is missing, so counting it as a formal recovery would hide the engineering failure. The two negative samples have no 8B comparison. Four selected samples cannot establish a model-size gain.

**Decision: `PILOT_FAIL`.** The engineering gate requires legal JSON/schema and terminal states for all planned units. It stopped at 12/16 attempted cells because the first two 8B Task B cells remained schema-invalid after the same bounded retry as 4B. Do not proceed automatically to the 12-segment Development run. The next engineering step is to diagnose the 8B structured-output omission while keeping the frozen task conditions and previous raw responses intact; any changed backend or decoding protocol must trigger a fresh, paired Pilot for both models.
