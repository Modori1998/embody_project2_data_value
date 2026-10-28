# Flora → P2 G3 Adapter v0.1 | Web/offline engineering handoff (2026-10-28)

**Status:** P0 inventory and P1/P2 adapter code smoke-tested offline; **P1 real source-frame alignment BLOCKED**, **P2 Qwen annotation NOT RUN**. Not a production or formal G3 gate pass. Reference design: [P2_Flora_G3_Adapter_v0_1_Design_Proposal_20261028.md](../10-design-review/P2_Flora_G3_Adapter_v0_1_Design_Proposal_20261028.md).

## What was implemented

- `src/project2_g3/flora_adapter.py`: reads the native Flora ZIP *without extracting or modifying it*, writes raw JSON references with SHA256, produces Episode inventory, Flora-to-G1 candidate links and alignment audit.
- `scripts/build_flora_g3_adapter.py`: offline command-line entry point. No GPU, Qwen or NVIDIA weights needed.
- `tests/test_flora_adapter.py`: six synthetic-fixture tests for missing provenance, one-to-many G1 relationships, source-video hash mismatch, source-clock mismatch, bad timestamps and invalid intervals.
- Model annotation compatibility is a thin bridge to **existing** `semantic_validation.validate_model_output_v0_2`. No alternative event taxonomy or validator was introduced, and no G3 inference has been executed.

### Offline invocation (from repository root)

```bash
python -m unittest discover -s tests -p 'test_flora_adapter.py' -v
python scripts/build_flora_g3_adapter.py \
  /path/to/flora_native_all15_export.zip \
  /path/to/outputs/flora_g3_adapter/v0_1/demo15
```

Optional, **only if an independently sourced mapping manifest exists**:

```bash
python scripts/build_flora_g3_adapter.py \
  /path/to/flora_native_all15_export.zip \
  /path/to/outputs/flora_g3_adapter/v0_1/with_mapping \
  --source-manifest /path/to/trusted_source_frame_mapping.json
```

CLI exit code `3` = **alignment blocked**, not an execution crash. Local hardening now also blocks internally consistent candidate manifests: consistency alone cannot prove external provenance. See [local source and partial G1 audit](P2_Flora_G3_Local_Alignment_Audit_20261028.md) for the recovered 15-video lineage and remaining full-coverage blocker.

### Current real-data run (uploaded ZIP, no G1 source manifest)

| Check | Result |
|---|---|
| Native JSON parsed | 15/15 |
| Flora segments indexed | 31/31 |
| Adapter link rows | 31, all `UNALIGNED` |
| Mapping errors | 15 × `MISSING_SOURCE_MANIFEST` |
| `source_alignment_verified` | **false** |
| Synthetic tests | 6/6 passed in isolated Python 3 environment |
| Original Flora bytes | not modified |

Outputs:
- `native_inventory.csv` — per Episode raw file name/SHA, duration, segment count, mapping status
- `flora_g1_links.jsonl` — per Flora segment ref; `g1_target.segment_id=null` if unaligned; `g3.prediction=null`, `g3.status=NOT_RUN`
- `alignment_audit.csv` — explicit provenance and blocker status
- `adapter_summary.json` — counts and gate flags

**Do not commit** MP4s, raw RGB, HDF5, large model weights or original user-provided ZIP into Git.

## External source mapping input contract (not available in current ZIP)

A future `P2_FLORA_G1_SOURCE_MAPPING_V0_1` document supplies per-Episode:
- `flora_episode_id` and **trusted P2** `source_episode_id`
- `source_clock` exactly matching the Flora JSON
- `flora_video_sha256` matching Flora `input_sha256.main`
- `source_manifest_sha256` representing the externally sourced P2 manifest (a string alone does **not** prove its authenticity)
- a dense ordered `frame_map` array with `video_frame_index`, `relative_pts_s` and `source_frame_index`, grounded in the *actual video export* rather than guessed as `round(t × 20fps)`
- authoritative frozen G1 `g1_segments` rows with `segment_id`, inclusive `start_frame`, inclusive `end_frame`.

The format is exercised in synthetic tests, not asserted as an already-existing upstream manifest. Candidate intervals are inferred only from frames explicitly present in the supplied map, not interpolated to unsampled intervals. Overlap can be one-to-many. All computed links remain `CANDIDATE_SOURCE_UNVERIFIED` until provenance is independently checked.

## Honest blockers / missing inputs

1. **Blocking P1 real-world alignment:** the available Flora ZIP holds caption, time windows, coarse frame plans and SHA metadata, but does **not** contain a verified relation from its MP4 frames to RoboMimic source state/frame indices and frozen G1 Segment IDs. GitHub includes G1 implementation and documents, but their existence does not prove this particular video export's state/frame identity. Currently the user reports only the 15 videos in LanYun. If no source export manifest or original RoboMimic trajectory is available anywhere, real P1 G1 alignment **cannot be verified**.
2. **Blocking new G3 visually grounded inference:** Clean RGB evidence packs aligned to target G1 frames are unavailable in the uploaded ZIP. A caption cannot be treated as event GT. The 15 MP4s might support a separately versioned **video-only exploratory** analysis after upload, but not retroactively satisfy frozen P2 RGB/Frame Manifest requirements.
3. **Blocking event accuracy and QC efficacy claims:** no independent newly aligned human evidence and no negative-case validation run. The existing G3F human-labeled G1 segments can support development diagnostics only after identity/temporal alignment is grounded.

**Not blocked:** P0 inventory, JSON indexing, unit-tested interface code, offline failure reporting, reference to the existing G3 v0.2 Validator.

## Resume safely

GitHub remains the code/document SSOT. Before a local implementation, `git fetch origin`, then safely fast-forward the appropriate clean branch/worktree with `git pull --ff-only`; do not overwrite active M07/M11/P2 worktrees. For this web-first branch, verify remote code and review independently; merge only after owner review and integration checks on the whole project.

**No GPU used, no source videos downloaded, no model executed, no training or automatic KEEP/DROP decisions.**
