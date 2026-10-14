# G3D2 Temporal Prompt Plan — frozen before first G3D2 model call

1. Preserve the G3D audit and all source runs. Verify SHA, source episode, frame interval, model/mmproj, context and GPU before inference.
2. Render all five requests offline, compare full message-content order and exact PNG bytes. Hash every prompt, state block, image and canonical request. Stop on any unplanned difference.
3. Use a new immutable run ID for 20 pilot calls. Stop on timeout, process error, malformed JSON/schema, invalid evidence or GPU competition; save the failing request and service log. No old G3D responses may fill missing cells.
4. Only after 20/20 gate pass, use a second immutable run ID for all 60 Development calls. Read the formal local G3C reference only after inference finishes. Compute all frozen metrics and per-segment contrasts. Repeat all 60 only if substantive variation is observed under the predeclared stability rule.
5. Conclude PROMPT_CANDIDATE, TEMPORAL_STATE_CANDIDATE, NO_GAIN or INCONCLUSIVE. Document next independent-validation or G3E plan. Keep raw requests, RGB, HDF5, model, personal CSV and machine paths out of GitHub.

Budget: 20 pilot + 60 Development calls, approximately five times the former two-arm Development call count. Use the same 512 output-token budget in every group; no group-specific tuning. Run only when no M11/ACT or other GPU training is active. No process except the G3D2-owned model service may be stopped by this task.
