# G3D result and G3E next plan — 2026-10-14

The first G3D small run stopped after 3/8 calls: llama.cpp received the fourth (`demo_180-S0001` A) and stalled while encoding its third image. Logs did not show OOM or CUDA failure. M11 contention was not established as the cause. A new small run completed 8/8, as did two 24-call full runs; their event sets and phases agreed. Review then found that the B block lacked the pre-registered EEF start/end coordinates. This execution defect was fixed and the gate and all 24 calls were rerun in new local directories. Only this corrected run is scored below.

Corrected small gate: 8/8 HTTP, JSON, schema and frame evidence valid. Corrected full run: 24/24 valid. All 36 PNG SHA values matched frozen manifest. No unauthorized state fields were used. `REVIEW_REQUIRED` statuses were semantic consistency candidates, not schema or frame-reference failures.

| Metric | A Vision | B Vision + Robot State |
|---|---:|---:|
| Phase correct | 7/12 | 7/12 |
| Event presence F1 | 0.842 | 0.800 |
| Event type micro F1 | 0.636 | 0.522 |
| Exact event sets | 5/12 | 3/12 |
| Grasp TP/FP/FN | 7/4/0 | 6/4/1 |
| Object motion TP/FP/FN | 0/0/3 | 0/2/3 |
| Release TP/FP/FN | 0/0/1 | 0/0/1 |
| Total wall time | 29.05 s | 32.73 s |
| Prompt tokens | 27,800 | 33,976 |
| Completion tokens | 1,777 | 1,872 |

Event-set comparison: A-only correct 2, B-only correct 0, both correct 3, both wrong 7. B did not recover object motion in the three reference-positive segments, did not fix the three named grasp false positives, and did not recover release in `demo_172`. Development gate: `G3D_NO_GAIN`. These twelve discussed Development examples are not independent held-out accuracy evidence.

## G3E Adaptive Keyframes design, not yet executed

Compare the same model, schema, task and frozen Segment boundaries with (A) the original three RGB frames and (C) the same three plus a small, preselected RGB supplement around gripper-state transitions and high EEF-motion intervals. Freeze the supplement selection algorithm using only robot-side motion before viewing model predictions or human labels. Verify each extra PNG SHA, source episode and inclusive segment bounds. Keep object GT, rewards, simulator states, historical predictions and human reference outside the prompt. Use a new Development gate followed, only on a gain signal, by episode-disjoint blind evaluation. Pre-register a fixed maximum extra-frame and call budget before running; report whether any gain offsets image-token and latency cost. Do not tune the supplement using these 12 reviewed labels.

Main integration remains pending because the main working tree reports an untracked `.cindy-worktrees/` directory containing active linked worktrees. No directory was removed, stashed or ignored and no main merge or push was attempted.
