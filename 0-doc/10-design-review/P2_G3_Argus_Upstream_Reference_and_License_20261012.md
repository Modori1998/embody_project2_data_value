# P2-G3 Argus 上游参考版本与许可证记录（2026-10-12）

> STATUS = UPSTREAM_SOURCE_VERIFIED / P2_IMPLEMENTATION_AUDIT_PENDING
> P2_REVIEW_BRANCH = design/p2-g3-argus-scope-20261012
> ARGUS_UPSTREAM_URL = https://github.com/Pantheon-Industries-Inc/argus
> ARGUS_REFERENCE_COMMIT = ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629
> ARGUS_REPOSITORY_LICENSE = Apache-2.0
> This is a fixed **reference** version for design/code comparison, **not** a claim that P2 has copied or reproduced the upstream code.

## 1. What was independently verified

- GitHub repository and commit: [Argus pinned commit](https://github.com/Pantheon-Industries-Inc/argus/tree/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629).
- [README / architecture / licenses](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/README.md): source-aware robot data annotation, RGB/robot state/action/sensor evidence, multi-format ingest, timeline labels, event / recovery / outcome claims, review board and structured exports.
- [LICENSE](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/LICENSE): upstream repository's Apache License 2.0.
- [THIRD_PARTY_NOTICES.txt](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/THIRD_PARTY_NOTICES.txt): bundled fonts and sample records have additional or source-specific terms; downloaded dependencies, model checkpoints and datasets keep separate licenses.
- Primary source reading entrypoints (all pinned to the above SHA): [label/prompts.py](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/label/prompts.py), [label/episode.py](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/label/episode.py), [label/evidence_access.py](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/label/evidence_access.py), [checks/label_consistency.py](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/checks/label_consistency.py), [board/build.py](https://github.com/Pantheon-Industries-Inc/argus/blob/ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629/board/build.py).

## 2. P2 use policy: design reference versus code copying

1. Prefer **reimplementation** of Argus's functional concepts using P2's G1/M2/RGB and RoboMimic adapter; do not claim an off-the-shelf Argus harness is P2-original.
2. Keep a module-by-module attribution matrix with columns `upstream_path`, `upstream_sha`, `P2_path`, `integration_mode: reimplemented/adapted/copied/not_used`, `changes` and `license_obligation`.
3. If any upstream Apache-2.0 source is copied/distributed in P2, preserve applicable copyright, license and existing attribution notices, mark modified files, include an Apache-2.0 license text/copy and any applicable upstream NOTICE content. Do not remove other files' license terms.
4. Do **not** copy fonts, sample datasets, rendered videos, externally downloaded pretrained checkpoints, noncommercial model weights or hand-pose assets without separate license assessment. Apache-2.0 for Argus repository code **does not** mean every linked dataset/checkpoint is Apache-2.0.
5. P2's own Can/MH dataset usage and Qwen3-VL model/license requirements must be checked independently; this document is only the Argus upstream ledger.

## 3. Reproduction scope (does not require the whole upstream app)

Must examine and map: source/provenance, timestamped evidence requests, structured semantic timeline, failures and recovery candidates, label consistency checks, run history and model failures, human audit, traceable exports.

P2 still requires independent design decisions: G1 fixed boundaries vs Argus episode timelines; short-segment contextual frames; 128x128 visibility limits; absent natural language per-episode instructions; forbidden simulator fields; fixed human GT and A/B benchmark.

## 4. Environment instructions for local AI

At each local task start: first fetch latest P2 `origin/main`, `pull --ff-only` in a healthy clean main worktree (do not modify main when unclean), then fetch current PR branches and work on a dedicated task worktree.

For upstream inspection, in **a separate reference directory**, clone public Argus and check out the fixed commit:
```bash
git clone https://github.com/Pantheon-Industries-Inc/argus.git argus_reference
cd argus_reference
git checkout --detach ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629
git rev-parse HEAD
```
If local network cannot fetch, read the GitHub pinned source links above from an authorized connection, and record the missing local execution as pending; do not guess source behavior.

## 5. Status boundaries

The **reference and license identification blocker is closed** by this source verification. This does **not** close implementation audit, frozen G3 taxonomy, VLM inference or independent human validation. Do not mark any of those complete on this evidence alone.
