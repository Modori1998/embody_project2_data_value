# G3F-P1 Output Design — 2026-10-14

Base main: `2969475e8e6ff6b37a33010ad21cf1116beaf11e`.

## 1. Runner output (per run directory)

`scripts/run_g3f_p1_paired.py` writes one immutable directory per run:

| File | Content |
|---|---|
| `run_manifest.json` | three prompt SHAs, model/mmproj/schema SHA, RGB SHA, sample order, sampling, retry budget, QC version, frozen success criteria |
| `inputs.jsonl` | exact ordered prompt + image request, request/prompt/RGB SHAs (no RGB bytes committed) |
| `responses.jsonl` | every attempt: raw HTTP response, parsed JSON, frozen-validator QC, phase-event QC envelope, tokens, wall time, GPU sample |
| `per_segment.jsonl` | human reference + A/B/C predictions (only after inference) |
| `scores.json` | per-arm micro F1 / exact / phase / per-type TP-FP-FN |
| `summary.json` | gate, reliability, tokens, success-criteria evaluation |

The runner fails closed: it refuses an existing output directory, a pilot that
is not 12/12 valid, a prompt-SHA drift from the pilot, frozen prompt/schema
drift, RGB SHA mismatch, model/mmproj identity change, or a competing GPU
process.

## 2. Retry / failure policy

Unchanged `FALLBACK_JSON_OBJECT_RETRY_V1`: at most 2 structure attempts and 3
service attempts per cell. The first valid attempt is the final prediction. All
attempts are retained; a permanently failed cell gets an explicit final status
and is never repaired or dropped. A GPU OOM or repeated service failure is a
global stop.

## 3. Scoring

Per-arm metrics use `project2_g3.g3d_paired.score_pairs` on the human multi-event
reference; micro P/R/F1 is over event types, exact match is over the event set,
phase accuracy over the single-choice phase. All three arms are scored on the
identical 12-segment cohort (no per-arm denominators differ this round, because
all 36 cells were valid).

## 4. Phase–Event consistency QC

`src/project2_g3/phase_event_qc.py`
(`P2_G3_PHASE_EVENT_QC_V0_2_2_CANDIDATE`) is applied to every parsed prediction
and stored in the attempt record. It is a **review layer only**:

* it never edits a prediction, a phase or a human label;
* it never inserts `object_motion`;
* it never escalates a candidate to `INVALID_MODEL_OUTPUT`;
* it never deletes an error to improve a score.

`scripts/replay_g3f_phase_event_qc.py` recomputes the QC offline over any stored
run (G3D2-R `group` arms and G3F `arm` arms both supported), so the findings are
reproducible without GPU.

## 5. Reporting

`G3F_P1_Results.md` reports the full metric table, per-segment A/B/C predictions,
the two primary contrasts (C−A, C−B), the pre-registered release criteria, and
the token/latency/retry cost. Raw RGB, HDF5, the private human CSV and model
weights are never committed.
