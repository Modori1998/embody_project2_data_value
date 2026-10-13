# P2-G3 — 12-Segment Semantic Blind Audit Web | Browser development handoff (2026-10-13)

> Status: `WEB_CODE_COMMITTED`, `SOURCE_MICROSET_PINNED_12`, `RGB_RUNTIME_PENDING_LOCAL_VERIFICATION`, `HUMAN_REFERENCE_NOT_YET_COLLECTED`.
>
> Work branch: `feat/p2-g3-semantic-blind-audit-web-20261013` (isolated from `main`). Do not call this a completed 12-image audit or semantic evaluation until real local PNGs are verified and the reviewer fills the CSV.

## 1. What is implemented

- Reuses the **static HTML/CSS/JS blind-review design pattern** from `scripts/build_mvp_calibration_audit_ui.py`, not the G1 boundary-label backend or SQLite schema.
- `scripts/g3_semantic_blind_audit_template.html`: Chinese single-page reviewer with 3 *target* RGB keyframes per segment, 4 required categorical human judgments, optional note, navigation, browser-local autosave, completion count, CSV export and validated re-import.
- `scripts/build_g3_semantic_blind_audit.py`: standard-library-only HTML/package builder. Reads exactly 12 frozen microset records, independently verifies **all 36 PNG file SHA256 values**, rejects missing/changed source images or model-label fields, then writes private output under ignored `outputs/`. It refuses to overwrite an existing audit package and writes via staging.
- `0-doc/10-design-review/evidence/P2_G3_Semantic_Blind_Audit_12_Source_20261013.csv`: 12 fixed microset source identities and expected PNG hashes, extracted from v0.2.1 human-reference template. **No model replies, result columns or labels**.
- `tests/test_g3_semantic_blind_audit_web.py`: tests for 12/36 contract, missing/corrupted images, strict blind-source headers, identity/frame validation, no overwrite, and full source selection.

This new Web neither runs a VLM nor changes frozen G1/M2 or original RGB. No robot PNG/weights/human predictions are committed.

## 2. Exact frozen source / image contract

Upstream immutable source branch:

- `p2-g3-taxonomy-v02-baseline-20261013` @ `e99d0249feb34f658b0de4ed2d4b15efb27d01b1`
- `0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013/human_reference_template.csv`
- Only `cohort=microset` rows (original sample_order 4..15); 3 `known_cases` excluded.
- Sample identities: `demo_2-S0003`, `demo_4-S0003`, `demo_28-S0003`, `demo_180-S0001`, `demo_159-S0003`, `demo_169-S0002`, `demo_172-S0004`, `demo_232-S0002`, `demo_71-S0003`, `demo_72-S0002`, `demo_183-S0003`, `demo_216-S0002`.
- Source RGB must match the **exact v0.2.1 PNG SHA256**; not just visually similar pixels. Validation uses the source `frame_png_sha256s` for frame indices `target_keyframes`.
- Existing v0.2.1 local cache (if still there): `%USERPROFILE%\embody\_local_vlm_deploy\rgb_g3_v02\g3_taxonomy_v02_20261013_r2`, filenames `demo_N-SXXXX_fNNNNN.png`.
- When cache is missing, `--render-missing` optionally calls the **existing** frozen G1 Clean RGB renderer for only the absent target frame indices and compares resulting PNGs to frozen file digests; does NOT call Qwen, change model input contract, create context frames or use model labels.

## 3. Safe local usage (PowerShell)

First ensure the latest GitHub SSOT is synchronized in a clean main worktree:

```powershell
git status --short --branch
git worktree list
git fetch origin --prune
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
```

Only pull in a **clean, healthy main worktree**; if dirty/occupied, don't stash/reset/clean. The actual remote `origin/main` is authoritative. Use an isolated new worktree for the Web development branch, e.g. `git worktree add _p2_g3_audit_web_wt -b local/p2-g3-audit-web origin/feat/p2-g3-semantic-blind-audit-web-20261013` (if branch name already exists, use an unused local name; don't damage existing trees).

Inside that new worktree:

```powershell
python scripts/build_g3_semantic_blind_audit.py
```

If the cached PNGs are missing, invoke from the existing **Project1/2 renderer Python environment**, with source HDF5 and Project1 renderer dependencies available, and ONLY then optionally reconstruct missing frames:

```powershell
python scripts/build_g3_semantic_blind_audit.py --render-missing
```

If SHA mismatch occurs, builder stops. **Do not bypass hashes**, use mislabeled panel images, or replace assets with resized/reencoded versions.

The builder reports the actual output path. Default:

`outputs/p2_g3_semantic_blind_audit/g3_v02_microset_12/index.html`

Start the static local server in a second terminal (from worktree root):

```powershell
python -m http.server 8767 --bind 127.0.0.1 --directory outputs/p2_g3_semantic_blind_audit/g3_v02_microset_12
```

Open: `http://127.0.0.1:8767/`

Never bind publicly (no authentication). The site runs locally, has no external network calls and does not send human results to GitHub.

## 4. Reviewer's four fields

The page prompts exactly:
1. `phase_ref`: approach/grasp/lift/transport/place/retract/idle/other/uncertain.
2. `event_assessment_ref`: event_visible/no_event_visible/insufficient_evidence.
3. `event_type_ref`: grasp_attempt/release_attempt/object_motion/none/uncertain, primary event only. If multiple events are visible, explain others in `explanation`.
4. `evidence_quality_ref`: sufficient/partial/insufficient **for motion_phase**, following frozen Rubric.

Optional reviewer ID, explanation. Each change saves in browser localStorage when available. Export the 12-row CSV early and often; **CSV export also includes unfinished rows**, which do not count as completed. Import only accepts matching source identities, frozen fields, order, valid values, and 12-row count, and does not partially overwrite on failure.

Review blind to v0.1/v0.2.1 predictions and QC statuses. No neighboring-segment images, no extra replay in this round; thus human evidence scope matches vision-only 3-frame conditions.

## 5. Verified vs. needs local verification

**Verified from remote repository metadata:** 12 distinct `microset` IDs, 16-column blind source shape, no known_cases, no JSON model responses injected into source file; actual HTML template and builder/test files are committed to branch.

**Not verifiable from ChatGPT without local assets:** 36 PNG files' actual existence and checksum, browser end-to-end with real images, OS/Python/renderer dependency availability, any actual human reviews or model-vs-human metrics. The local builder and tests must be run before declaring the Web ready for Owner audit. Do **not** record `PNG_VERIFIED=36/36` prematurely.

Local acceptance gate: Builder exits 0 with `status=BUILT_HASH_VERIFIED, png_verified_count=36, segment_count=12`, browser shows all images, four fields save/export/import correctly, local tests pass; then `READY_FOR_BLIND_HUMAN_REVIEW`. Upload **filled CSV** for analysis only after reviewing; no model-label reveal in that UI.
