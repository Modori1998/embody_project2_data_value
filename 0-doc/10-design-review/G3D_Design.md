# G3D Design — frozen before model calls, 2026-10-13

Hypothesis: adding legal same-segment robot motion to the same three RGB frames improves multi-event annotation, especially object motion, without increasing grasp false positives. The 12 samples are Development, not held-out.

A receives frozen Task, three Clean RGB and v0.2.1 instructions. B receives exactly those inputs plus one JSON robot-state block. The block contains EEF displacement, path length, gripper start/end aperture and state transition, and normalized action magnitude statistics. Metres apply to EEF; aperture uses source qpos units. EEF movement cannot establish object motion; gripper closure cannot establish grasp success. Both arms retain the same Qwen3-VL-4B Q4 weights, images/hashes, prompt instructions, schema, temperature 0, seed 1234, max_tokens 512 and evidence rules. No group-specific tuning.

Only `load_formal_episode()` policy-visible proprio/actions and M2 `summarize_motion()` from the same episode and inclusive segment interval are permitted. Object GT/pose, simulator state, reward, success, done, next_obs, human labels, historical predictions and G3C notes are forbidden. Fail closed on identity, interval, length, finite values, frame scope, units, provenance or SHA mismatch.

Four-segment gate: demo_2-S0003, demo_169-S0002, demo_172-S0004, demo_180-S0001, 8 calls. Require all requests, JSON/schema, legal evidence, aligned state and frozen inputs to pass before full 24-call run. Check model identity, GPU competing jobs, free VRAM and RGB SHA first. Historical v0.2.1 outputs are diagnostic only.

Full run: 12 paired samples, alternating A→B and B→A across sample order. If substantive output varies on repeat, repeat *all* pairs with the same frozen order and report distribution. No selective reruns. Human reference stays outside inference until all calls finish.

Metrics: phase accuracy; event presence and event-type micro P/R/F1; grasp/object-motion/release TP/FP/FN; exact event-set match; four A/B correctness cells; schema/evidence/cross-boundary QC; latency, tokens and GPU cost per pair. Gate: B object-motion recall ≥2/3 without many new FP, micro-F1 gain ≥0.10 absolute, phase correct decrease ≤1, no extra grasp FP, frozen QC gates satisfied, cost reported. This gate only licenses episode-disjoint 24–36 sample blind evaluation. If no gain, design G3E adaptive RGB keyframes; if unstable, assess repeated-inference stability first.
