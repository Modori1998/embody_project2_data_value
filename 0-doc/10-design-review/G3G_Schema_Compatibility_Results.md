# G3G-P1 structured-output compatibility (2026-10-15)

**Decision: `READY_FOR_PAIRED_PILOT`.** This is a format and resource check, not a semantic performance result. No full Pilot or Development cells were run in this round. Raw requests, PNG-derived payloads, responses, samples, and service logs remain only in gitignored `outputs/g3g/schema_diag_20261015_r1/`. The failed Pilot remains untouched.

## Diagnosis and protocol

The previous 8B Task B requests contained all eight field definitions in the frozen v0.2.3 prompt. All four responses (two segments, first call and retry) were HTTP 200, `finish_reason=stop`, parseable JSON, and omitted only the required **top-level** `evidence_frame_indices`. The active `response_format={"type":"json_object"}` constrained general JSON syntax, not required keys. Server logs showed the model's embedded chat template, three image parts, and no context truncation. The prompt and request transport did not lose the field. The exact internal reason the 8B chose to omit it remains unknown.

The older llama.cpp `0.6.0-dev` build `11577`, commit `cbe28bb3c`, had previously accepted `response_format={"type":"json_schema","schema":...}` but generated a generic object grammar and still omitted required fields. This round reproduced that failure with a synthetic two-field schema: an instruction to omit `b` yielded `{"a":"ok"}`. The **same executable** enforced `b` when given `response_format={"type":"json_object","schema":...}`. No backend upgrade was needed; the old binary was retained. The [upstream llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) describes the schema-bearing `json_object` form.

The new [runner](../../scripts/run_g3g_schema_check.py) sends the unmodified `json_schema_v0_2()` under `json_object.schema`. It keeps the original model-visible text, image bytes, order, seed 1234, temperature 0, max_tokens 512, and ctx-size 4096. The runner checks the original Pilot's text-plus-image content hash before each call. 4B and 8B use the same backend binary and response format. `-ngl` remains model-specific: 8B 32, 4B 99. Model and mmproj hashes are verified before inference.

Two image-free negative probes challenged the format. The full v0.2 schema probe asked for only `motion_phase` and to omit other fields; generation included all eight required fields and passed `check_schema_v0_2`. A nested probe asked for an incomplete event and an extra `debug` key; generation supplied the event's required keys and omitted `debug`, but duplicated an `object_relation` value. **The grammar does not fully enforce `uniqueItems`.** Support for every numeric/string bound in the frozen JSON Schema was not established. The independent validator remains mandatory and catches such violations; an invalid result is recorded and receives at most one retry. No field is added or repaired after generation. This is a demonstrated field-level constraint with validator coverage, not a claim that every JSON Schema keyword is enforced during decoding.

## Real three-image Task B check

Each cell used its original 128×128 START/MIDDLE/END PNGs. All four requests ended at `stop`, passed parse, schema and frame-evidence checks on the first attempt, and used no retry. Both model services were stopped after their own arm. There was no OOM or low-RAM stop.

| Arm | Segment | Phase | Events | Top-level evidence frames | Tokens prompt/completion | Wall time | Peak VRAM | Minimum free RAM |
|---|---|---|---|---|---:|---:|---:|---:|
| 8B | `demo_2-S0003` | `grasp` | `grasp_attempt:unclear` | 63, 84, 106 | 2352 / 166 | 8.05 s | 6201 MiB | 4865 MiB |
| 8B | `demo_159-S0003` | `transport` | `object_motion:unclear` | 81, 115, 150 | 2369 / 151 | 6.72 s | 6209 MiB | 4550 MiB |
| 4B | `demo_2-S0003` | `grasp` | `grasp_attempt:unclear` | 63, 84, 106 | 2352 / 150 | 3.30 s | 4349 MiB | 6441 MiB |
| 4B | `demo_159-S0003` | `grasp` | `grasp_attempt:unclear` | 81, 115, 150 | 2369 / 152 | 3.16 s | 4351 MiB | 6078 MiB |

The new 8B event sets and phases match their respective *invalid* first Pilot responses: `demo_2` still describes contact without Can displacement, and `demo_159` still describes object travel. The new 4B responses retain `grasp_attempt` on both segments. Wording and top-level citations changed under constrained decoding; the original failures cannot be scored as valid annotations. Four formatting checks do not establish model superiority. For the paired calls, 8B took 14.77 s versus 4B 6.46 s in total, about 2.29 times as long; peak observed VRAM was 6209 versus 4351 MiB, about 1858 MiB higher. Free RAM values depend on host baseline and are not model-only memory costs.

## Gate and limits

The new protocol is suitable for a **fresh paired** 16-cell engineering Pilot: both models completed the two specified real three-image checks with the same schema-constrained request format, independent validation, safe resource readings, and saved raw records. It does not rehabilitate the interrupted Pilot's 12 cells. The fresh Pilot must retain first-attempt failures, bounded retries, and a stop for systemic invalid output. In particular, `uniqueItems` and other unverified JSON Schema keywords remain validator responsibilities. No Pilot was started here.

Tests: `python -m pytest tests/test_g3g_schema_check.py tests/test_g3g_pilot.py -q` → 4 passed.
