# G3D four-segment gate incident — 2026-10-14

Status: `SMALL_GATE_FAILED`; no full experiment or semantic gain claim.

The first three calls returned HTTP 200 and passed JSON, v0.2 schema and frame-reference QC: `demo_2-S0003` A (5.16 s), B (4.15 s), and `demo_180-S0001` B (4.89 s). Alternating order was used. `demo_2` A exactly matched the historical v0.2.1 parsed output; A and B both reported `grasp_attempt` without `object_motion`. This is a partial diagnostic, not paired cohort evidence.

The fourth request stalled during image decode and hit the client timeout. Server log recorded image decoding taking about 9,931 seconds. The process stayed responsive afterward, but the eight-call gate was incomplete. A separate Python process then appeared in the GPU process list. The G3D-owned server was stopped; no other process was terminated.

Before a repeat: check no competing GPU task, preserve frozen model/PNG/prompt/schema/params, use the bounded client timeout and immutable output folder. Repeat all four A/B pairs, not only the failed request. If the stall recurs, report `INCONCLUSIVE` and do not launch the 12-pair run. If 8/8 pass, evaluate QC and A-vs-historical drift before full inference.
