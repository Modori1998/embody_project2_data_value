# G3D2 Temporal Prompt Output Design — frozen before first G3D2 model call

Each new local run directory contains `run_manifest.json` (version, frozen source hashes, model/mmproj identity, five-arm matrix, parameters, cohort, gates), `inputs.jsonl` (full ordered message content, image bytes via data URIs, state text and hashes), `responses.jsonl` (raw HTTP response, parsed unmodified JSON, QC, latency, tokens, GPU), `summary.json` (20/20 or 60/60 gate and reason), `scores.json` (five-arm metrics), and `per_segment.jsonl` (all five predictions and human reference only after inference). Existing G3D output directories remain immutable.

Score each group for phase correct/accuracy, event presence P/R/F1, event-type micro P/R/F1, exact event-set matches, and grasp/object-motion/release TP/FP/FN. Report five pre-registered contrasts, per-segment net improvements/regressions, response validity, prompt/completion tokens, latency, and GPU use. Separate model instability from input drift by comparing request hashes. A failed pilot is `G3D2_PILOT_HOLD`; a partial full run is `G3D2_FULL_INCOMPLETE`. Never infer missing scores from historical output.

GitHub export is a sanitized aggregate report and implementation only. Personal human CSV, PNG, HDF5, model weights, base64 request bodies, cloud credentials and local absolute paths stay local.
