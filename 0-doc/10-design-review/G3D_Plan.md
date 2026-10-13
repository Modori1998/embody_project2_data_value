# G3D Plan — 2026-10-13

1. Verify GitHub main, v0.2.1 source commit, G3C audit CSV, 12 segment IDs, 36 PNG SHA and local formal episode files. Stop on drift; never regenerate reference or resegment.
2. Freeze A/B prompts and request hashes, with only the B motion JSON block added. Write identity checks and unit tests. Keep model requests and personal CSV local.
3. Run four-pair gate only if Q4 service identity, GPU headroom, absence of conflicting training and all input hashes pass. Record raw requests/responses, parsed JSON, schema/evidence QC, latency, tokens, VRAM and SHA. Stop on failure.
4. Run all 12 alternating pairs under the same parameters. Score against the local human CSV only after inference. Apply preregistered gate without adjustment.
5. If gain, draft episode-disjoint blind evaluation; if no gain, draft G3E; if unstable, repeat all pairs. Publish code/docs only, without HDF5, PNG, weights, personal CSV or unsanitized local paths.

Resource budget: 8 gate calls, then 24 full calls; paired repeats only on observed substantive instability. No GPU job may be terminated for this experiment.

Current preflight: 36/36 PNG SHA match; Q4 service at `127.0.0.1:8080` is unreachable and another GPU Python process is active. Status `EXPERIMENT_NOT_RUN`. Full run remains gated.
