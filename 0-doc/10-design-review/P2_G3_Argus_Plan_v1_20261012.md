# P2-G3 — Argus-inspired Semantic Annotation | Plan v1

> Date: 2026-10-12  
> Status: `OWNER_DIRECTION_APPROVED / PLAN_PROPOSED / NOT_EXECUTED`  
> Intended repo path: `0-doc/10-design-review/P2_G3_Argus_Plan_v1_20261012.md`  
> Main direction: replace active Retrieval-first execution with an independent G3 semantic annotation lane. Do **not** mark frozen Retrieval as GO/STOP.  
> Local changes must first synchronize to fresh `origin/main`; see §10.

## 0. Fixed principles

- The user approved HOLD of Retrieval v1 and reprioritization to Argus-style G3, with preserved evidence.
- Master implementation objective is **working Argus core functionality on RoboMimic Can/MH**, not identical software/UI/code layout to upstream Argus.
- Minimum validation = A/B paired single-VLM human benchmark. C extra frames and D advanced review rules are **conditional**, not always four full experiments.
- No ACT, VLA, VLM training or full universal data-platform rewrite in P2-G3 v1.
- Episode-level data isolation, human-review independence, model-prompt/schema pinning, cost tracking, no unsupported `DROP/UPWEIGHT` decisions.

## Phase 0 — Commit scope-change governance and preserve HOLD snapshot

**Inputs**: latest GitHub `main`, `Project2_MVP_SSOT_20261008.md`, 18-query frozen Retrieval manifest/rubric, previous G3 minimal taxonomy gate, this design and output contract.

**Actions**:
1. Read `origin/main`, capture exact source commit/SSOT hash. Check whether Final Retrieval was already executed before deciding the HOLD snapshot. Current verified GitHub (2026-10-12): latest `b5fd9b97`, `NEXT=FINAL_RETRIEVAL`; this may change at execution.
2. Add an **append-only owner decision overlay**: `RETRIEVAL_V1 = HOLD_BY_OWNER`, `RETRIEVAL_FINAL_EVALUATION = NOT_EXECUTED` (only when verified), `G3 = NEW_ACTIVE_PRIORITY`, `G3_DEPENDS_ON_RETRIEVAL_GATE = NO`, `RETRIEVAL_RESULT_NOT_REINTERPRETED = YES`.
3. Archive, do not edit, 18-query query/candidate/rubric, embeddings and previous audit data. No retrospective score.
4. Commit G3 design/plan/output design and change log in an isolated branch, PR into `main`, merge only after review. No code or formal VLM runs until governance and taxonomy/source gates are satisfied.

**Gate 0**: Owner overlay merged, no change to frozen Retrieval contents, `RGB_RUNTIME_VALIDATION=PASS`, G1/M2 versions known, no other main changes.

## Phase 1 — Argus reference audit and interface compatibility

**Code to read**: P2 `src/project2_g1/source.py`, `src/project2_mvp/m2.py`, `src/project2_mvp/m2_materializer.py`, `src/project2_mvp/rgb_input.py`, P1 source/renderer; Argus `label/prompts.py`, `label/episode.py`, `label/frames.py`, `label/route.py`, `checks/label_consistency.py`, `review`/`board` entrypoints.

**Tasks**:
- Pin Argus upstream commit SHA and LICENSE, create reference/adaptation attribution matrix.
- Map source fields: episode, segment identity, RGB, frame/time, proprio, gripper, action, source task/instruction; identify missing fields rather than filling guesses.
- Read-only survey of 8–12 episodes for can visibility, grasp/release observability and candidate-positive frequency; note Argus direct-episode timeline assumptions vs P2's frozen G1 segment boundaries.
- Materialize ordered evidence manifests; verify source contract, frame hashes and episode index alignment. No VLM model calls for most tests.
- Set initial estimate of availability of human GT positives for `failed_grasp` and `recovery` before promising event metrics.

**Gate 1**: all evidence inputs traceable; forbidden privileged inputs zero; source+RGB alignment repeatable; unsupported claim categories identified. If contact/result unobservable, contract must reduce to phases/object relations rather than hallucinate failures.

## Phase 2 — Freeze minimal ontology, human rubric, experiment identity

Owner-approved minimal first release fields: `motion_phase`, `object_relation[]`, `event_type/outcome` (candidate and uncertain allowed), `evidence_quality`, `label_source/provenance`, separately `task_outcome` where episode coverage permits.

Tasks:
- Draft one-page glossary with positive/negative/uncertain examples for each supported class. Decide overlap/multi-label and conditions under which `grasp` differs from `grasp_attempt`.
- Freeze phase and relation classes; mark unsupported rare event classes as `CANDIDATE_ONLY` or `NOT_EVALUATED`.
- Define human audit packet and correction schema, allowing `HUMAN_UNSURE` and adjudication without seeing VLM outputs.
- Pre-register **A/B**: same segment/episode set, same model, same permitted keyframes, only B adds approved M2 summary.
- Propose Episode-level Calibration and Held-out splits. Suggested budget 20–30 calibration + 60–80 held-out segments, confirmed **only after** audit and actual positive counts; select independent Episodes before using model outputs.

**Gate 2**: owner approval for taxonomy v1, model/revision/preprocessing pin, human rubric, sample manifest, comparison metrics, stop conditions and conditional module criteria. No formal held-out edits thereafter.

## Phase 3 — Functional Argus-style minimal pipeline (no model calls first)

**New module root** `src/project2_g3/` (do not rewrite G1/M2 or frozen Retrieval code):

| Path (proposed) | Responsibility |
|---|---|
| `contracts.py` | Versioned evidence/event/label/review schemas; type and enum validation |
| `source_adapter.py` | Frozen G1/M2 read-only adapter; frame/timestamp and role checks |
| `evidence.py` | Immutable ordered clean keyframes, task/source, motion summary and hashes |
| `prompts/semantic_label_v1.txt` | Controlled ontology and evidence-limited labeling instructions |
| `vlm_client.py` | Pinned single Qwen3-VL endpoint, retry and cost bookkeeping |
| `labeler.py` | Structured decode, error separation and raw output provenance |
| `checks.py` | Time/schema/label consistency and **qualified** motion/vision contradiction flags |
| `review.py` | Audit evidence package, human corrections, abstention states |
| `events.py` | Queryable candidate index and episode-local event linkage |
| `export.py` | Immutable JSONL/CSV exports and manifest consistency |
| `run.py` | Reproducible CLI: smoke, inference, reparse, export, evaluate modes |

**Mandatory tests**: frame off-by-one; segment+episode identity; source loss/missing frame; action-magnitude physical-unit confusion; invalid JSON/enum; VLM timeout; no-gripper-event; empty/near-static movement; event time beyond segment; image hashes; retry/resume identity; parser replay without inference; `AUTO_ACCEPT` ≠ training `KEEP`.

**Gate 3**: all offline no-call tests pass; 3–5 mock episodes export valid timeline/JSONL; model errors don't become quality labels. No mandatory advanced viewer or extra-frame sampler yet.

## Phase 4 — Tiny live VLM baseline and calibration

1. Run 8–12 **small inference** examples under exact model & cost cap, record failures and human-observable limitations. This is a baseline feasibility probe, **not** final results.
2. Run calibration 20–30 proposed segments, independent human review first/without prediction exposure; version prompt corrections and record changes; allow ontology simplification if categories unobservable.
3. Start with A (Vision-only) and B (Vision + robot M2 summary). Ensure motion information appears with valid definitions and consistent timestamps; prohibit privileged fields.
4. Identify concentrated bad-case modes: `SEMANTIC_CONFUSION`, `TEMPORAL_GAP`, `SOURCE_ERROR`, `MODEL_FORMAT`, `HUMAN_UNSURE`.
5. Only when actual `TEMPORAL_GAP` errors are material, propose C event-adjacent clean RGB window with frozen signal-only triggers and bounded image budget; otherwise C stays unimplemented.
6. Implement structural/time consistency checks regardless; only if seeking **review efficiency / label precision gain** build and compare substantive D routing rules against simple/random review at matched budgets.

**Gate 4**: prompt/schema, allowed images and frame budget, A/B cohorts, human rubric and metric definitions are frozen before Formal eval; C/D explicit decision log `ACTIVATE` or `DEFER` based on calibration errors only.

## Phase 5 — Blind human assessment and paired A/B evidence

**Formal protocol**:
- Use held-out Episode-separated segments; identical model revision/settings for A/B and same freeze; persist image hashes, frame roles and source timestamps.
- Human independent review: full temporal replay may be shown to reviewers (audit-only); hide VLM labels, group identity and predicted scores until human reference labels locked.
- Main results: accuracy, supported Macro-F1, relation/event confusion & prevalence, uncertain rate, event localization within annotated timing tolerance, per-episode paired errors, token/frame/time cost.
- If D is activated, verify accepted-label accuracy **and** auto-accept coverage with same reviewed labels; top-N review yield compared to random or unmodified simple baseline; never silently relabel flagged results.
- Cases marked `HUMAN_UNSURE` are accounted for with denominators and sensitivity; do not cherry-pick.
- Fix bugs only outside frozen results; if a serious protocol defect occurs, invalidate run and redo under new version, with an audit trail.

**Gate 5**: `GO / LIMITED_CLAIM / INCONCLUSIVE / STOP-PIVOT` based on pre-registered rules. No asserted improvement from a small random fluctuation or inadequate event positives.

## Phase 6 — Usable semantic index and minimal reviewer

Create a simple P2 audit interface (existing web audit or static evidence review acceptable): episode timeline, action and relation labels, event time, key evidence images, provenance, QC flags, manual correction log. Provide CLI filters such as `--event grasp_attempt`, `--qc REVIEW_REQUIRED`, `--episode ...` and export `event_candidates.jsonl` / review queues. Supports raw response reparsing without rerunning billed VLM requests and correct handling of incomplete jobs.

**Gate 6**: fresh checkout can run no-call fixtures, limited VLM inference, audit and export from a pinned source/manifest. Clear README demonstrates actual captured cases, while disclosing upstream references and task/data limits. No made-up failure counts.

## 7. Deliverables and completion thresholds

| Deliverable | Mandatory proof |
|---|---|
| `input_manifest` and `evidence_packs` | Episode/segment/frame hashes, renderer and sensor provenance |
| `structured_labels` and `events` | Frozen schema + raw VLM response retention |
| `label_qc_findings` | Explicit rule ID, evidence, outcome and unmatched/uncertain |
| Human review packet + corrections | Reviewer-blind identity and reproducible correction history |
| A/B benchmark | Same cohort/model, human GT and per-category denominators |
| Dataset event index | Real event query and export demonstration |
| Audit README & 3–5 cases | Only verified real cases, source and evidence references |
| Attribution & license | Argus pinned version, copied/adapted modules documented |

If G3 produces sound labels but no proven A/B gain, output a **valid tool** and `LIMITED_CLAIM`; do not invent a multi-modal breakthrough. If no available failure events, don't report failure detection generalization.

## 8. Explicit exclusions

- SigLIP2/FAISS iterative tuning and Final Retrieval v1 while `HOLD_BY_OWNER`.
- ACT / VLA retraining, sampling weight optimization, downstream task-success claims.
- Automatic deletion or hard REJECT of episodes from candidate semantic events.
- Synthetic failure injection to inflate natural failure prevalence.
- A second VLM silent fallback or use of privileged simulator object GT as an input.
- Full Argus board/site reimplementation or universal robotics format support in first release.

## 9. Status writeback when merged

SSOT overlay should state `G3_NEW_ACTIVE_PRIORITY` and explicit `RETRIEVAL_V1_HOLD_BY_OWNER`, but preserve the historical `NEXT=FINAL_RETRIEVAL` line as **previous snapshot** or annotate it superseded. Exact runtime status remains `G3_TAXONOMY=PENDING_OWNER_FREEZE`, `G3_INFERENCE=NOT_STARTED`, not magically `CLOSED`. Merge/check identity should be written to release notes.

## 10. Local development preflight — ALWAYS BEFORE ANY EDIT

```bash
# Use a healthy clean main worktree / fresh clone; do not touch other worktrees.
git fetch origin main
# Run the following only where it is safe to update main:
git switch main
git pull --ff-only origin main
git status --short
# Assert no unexpected tracked/untracked changes; verify main == origin/main.
# Then create a dedicated review/task branch or worktree from the NEW origin/main.
```

If `main` is used by another worktree or repository metadata is damaged, **do not force switch, reset, merge or discard edits**; use a healthy fresh clone and create a task branch from fetched `origin/main`. All requirements, schemas and status changes are derived from GitHub SSOT; never rely solely on cached local SHA. Tests and final output must include source SHA, branch, modified file list, test results, live inference status and a list of untouched frozen artifacts.
