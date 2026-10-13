# P2-G3 — Structured JSON + Evidence Contract | Owner Freeze 2026-10-13

> **OWNER_DECISION = FROZEN_OUTPUT_ARCHITECTURE_V1**
>
> **Decided**: **Controlled-enum JSON + short free-form observation note + frame-level evidence citations + deterministic validation**, inspired by Argus but implemented for P2-specific frozen G1/M2 contracts.
>
> **NOT frozen**: exact G3 semantic taxonomy/enumeration set, final JSON Schema v1 implementation, frozen Prompt bytes/SHA, Qwen3-VL exact checkpoint, formal VLM input modality A/B, human GT/held-out evaluation, any accuracy claim, 256/512 high-resolution RGB contract, or training disposition.

## 0. Authority, provenance and change boundary

Owner explicitly accepted this output **architecture** in the 2026-10-13 discussion. This document is the authoritative design decision after merge to \`main\`, superseding *only the unsettled output-format choice* in the earlier G3 design proposal; existing frozen source, timing and dataset restrictions remain authoritative. Changing this architecture requires a new version / owner decision, not silent edits.

Related SSOT:

- \`0-doc/Project2_MVP_SSOT_20261008.md\`
- \`0-doc/10-design-review/P2_G3_Argus_Design_v1_20261012.md\`
- \`0-doc/10-design-review/P2_G3_Argus_Output_Design_v1_20261012.md\` (historical **draft schema**, not automatically promoted to frozen taxonomy)
- \`0-doc/10-design-review/P2_G3_Phase1B_1C_Observability_Owner_Freeze_20261013.md\` (Phase1C owner scores, context optional)
- \`p2-g3-local-vlm-deploy-20261013\` @ \`a1bc80ba9b6bf7de12bcb02e606e917240881101\` (local Qwen3-VL deployment report & probe evidence, independent experimental branch)
- Upstream Argus \`Pantheon-Industries-Inc/argus\` @ \`ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629\`, \`label/prompts.py\`, \`label/harness.py\`, \`checks/label_consistency.py\`. Preserve the upstream license ledger.

**What Argus actually does:** asks for **JSON-only** (including \`response_format: {"type":"json_object"}\`) while allowing free-form action/notes text *inside* the JSON. It produces episode timelines, key events, completion, recovery, etc. \`label_consistency\` checks contradictions among **fields of one annotation**, not between independent calls and not a proof of visual truth. P2 adopts this structured-plus-explanation idea, **not** the full Argus schema, vocabulary, prompt or episode-level claims.

## 1. Why this was frozen (negative deployment evidence)

The 2026-10-13 **local deployment smoke test** ran Qwen3-VL-4B-Instruct GGUF Q4_K_M on Windows 11 RTX 4060 Laptop 8GB with CUDA llama.cpp b11577. Main 1/3/6-image configurations loaded and inferred on GPU, with sampled peak VRAM ~4832 MiB; **runtime viability only**, not a semantic validation result.

Observed errors (read the exact run JSON on the deployment branch; no scores fabricated here):

1. Identical single frame, separate prompts: free text asserted gripper **open / not gripping**, JSON asserted \`gripper_state=closed\` and notes claimed **holding**. **Both are unverified model predictions**, neither is GT. Both prompts and response formats changed; not a controlled isolation of format alone.
2. Multi-frame input: model conflated next-segment context with target segment, even after being told not to. A response with expanded output-token budget continued to contradict itself about which frames belonged to the target.
3. Main free-text responses hit a 128-token output cap; JSON parsed successfully in one smoke request. **JSON parse success is not semantic correctness**.
4. Image token budget was small (~18 tokens per 128×128 RGB in the recorded primary configuration), but the alternate budget probe did not consistently resolve errors. Do not claim resolution/token budget was proven causal.

**Decision implication**: Use a stable JSON interface and fail-closed provenance guard, but **do not claim JSON-only cures hallucination, uncertainty calibration or neighbor contamination**. A small human-supported baseline must check such failure modes separately.

## 2. Frozen P2-G3 output architecture

| Layer | Owner decision | What it guarantees / does not guarantee |
| --- | --- | --- |
| **Model response** | A **single JSON object**; no free-form prose wrapper or Markdown code fence as the intended interface | Machine-readability; **not** factual accuracy |
| **Controlled fields** | Core semantic categories use explicit finite enums and an \`uncertain\` / \`unclear\` state where appropriate; missing/illegal values are invalid output | Comparable labels for search, metrics and review |
| **Natural language inside JSON** | Short, grounded \`observation_note\` (one or two concise sentences), describing visible evidence and uncertainty; **not a competing second classification** | A person can review why it decided; note remains an unverified model statement |
| **Evidence citations** | Each asserted target-segment behavior/event cites model-visible **frame indices / IDs**; validation checks every reference against an immutable request-frame manifest | References can be verified as **supplied and correctly scoped**, not that visual semantics are true |
| **Provenance IDs** | \`source_episode_id\`, \`segment_id\`, interval, input/renderer/model/prompt/schema hashes are **injected by pipeline from trusted manifests**; never accepted from untrusted model output as truth | Prevents model text from changing source identity |
| **Deterministic checks** | Parse/type/enum, temporal scope, source identity, evidence sufficiency **availability**, cross-field logical constraints, source/role separation | Raises flags or errors; **never auto-corrects, manufactures GT, or proves semantic correctness** |
| **Human review** | Original model response is immutable; parser outputs, QC flags, review actions and any human correction are separate versioned records | Full audit trail; no implicit \`AUTO_ACCEPT → training KEEP\` |

**Granularity**: primary unit is the pre-existing **G1 Segment**. The model is **not allowed to redefine the frozen segment**. Episode task completion/recovery require separately supported episode-level evidence, not a guess from a few segment keyframes.

### 2.1 Minimal model-owned payload — shape illustration only

\`\`\`json
{
  "motion_phase": "transport",
  "object_relation": ["moving_with_gripper"],
  "gripper_state": "uncertain",
  "events": [
    {
      "event_type": "object_motion",
      "event_outcome": "unclear",
      "evidence_frame_indices": [70, 90]
    }
  ],
  "evidence_frame_indices": [50, 70, 90],
  "evidence_quality": "insufficient",
  "observation_note": "The red object appears to move with the gripper; contact is occluded."
}
\`\`\`

**Schematic example, NOT a real model result and NOT the final frozen enum table.** \`events\` may be empty, and \`object_relation\` is shown as an array to remain compatible with the existing Output Design draft; the exact cardinalities/nullability and optional \`gripper_state\` need their own Schema/Taxonomy freeze. \`gripper_state=closed\` must **never** be equated to \`holding=true\` or task success. No free-standing separate prose answer is produced.

\`segment_id\` is intentionally **not** model-owned: trusted caller attaches it after parsing. On-disk records should wrap the validated prediction with caller-owned identity and hashes, rather than prompting the model to invent IDs.

### 2.2 Evidence identity / neighbor safety — mandatory

- **Frozen target interval**: \`[start_frame, end_frame]\` inclusive from G1, from its own Episode.
- **Model-visible frame manifest**: immutable ordered entries with \`frame_index\`, \`role\`, \`source_episode_id\`, \`origin_segment_id\`, \`target_segment_id\`, \`is_target_segment_frame\`, \`pixel_sha256\`. Every cited frame must match exactly one allowed entry in the actual request.
- **Target event citation**: an event claimed to happen *inside the target* must cite only target-segment frames, with its claimed time within the frozen target interval. If the model cites a context frame as a target event → **\`TARGET_CONTEXT_CROSS_BOUNDARY\`**, invalid for automatic indexing; keep the raw answer and route to review.
- **Neighbor context**: \`CONTEXT_POLICY_DECISION=KEEP_CONTEXT_OPTIONAL\`. If allowed in a separately identified exploratory variant, keep context frames in a distinct role/channel. A note may say a following frame *suggests* an interpretation, but it cannot turn a neighbor event into a target event. Until the formal context input policy is approved, the initial pilot should default to **target-keyframes-only**.
- **Sparse evidence**: never manufacture an exact contact/release instant or task outcome between two sampled frames; use unresolved/uncertain/interval status according to subsequently approved schema.
- **No privileged leak**: permitted RGB and explicitly approved EEF/gripper/action signals only; exclude object GT, reward, done, simulator state as direct model inputs. Frozen Renderer may read underlying STATE solely to generate Clean RGB.

### 2.3 Proposed deterministic QC, to implement and test next

**Hard invalid / fail-closed (no automatic label):**
- JSON unparseable/truncated (especially \`finish_reason=length\`), not an object, missing mandatory keys, wrong type, unsupported enum, extra forbidden structural fields when strict schema is adopted.
- Missing/unrecognized evidence frame, mismatched Episode, out-of-range index, asserted target event backed only by a context frame, incorrect source/role.
- Forbidden input field or invalid source/provenance hash (\`INVALID_INPUT\` before model call).

**Review candidates rather than verified errors:**
- \`observation_note\` narratively contradicts a categorical field (e.g., \`open\` vs \`closed\`, or claiming holding while a field says uncertain): \`LABEL_NOTE_CONFLICT_CANDIDATE\`; flag, do not rewrite the note or pick a side.
- Outcome / relation / event logically inconsistent with *their defined semantics*: rule IDs and severity must be specified after taxonomy; do not invent universal equivalences.
- No post-event visual observation for asserted success: \`EVIDENCE_SUFFICIENCY_CANDIDATE\`, not a certified incorrect label.
- Model uncertainty \`false\` without enough visible evidence: calibration/review candidate, not deterministic falsification.

Separate statuses \`MODEL_PARSE_ERROR\`, \`INVALID_MODEL_OUTPUT\`, \`INVALID_INPUT\`, \`PROCESSING_ERROR\`, \`REVIEW_REQUIRED\`, \`UNRESOLVED\`, as appropriate to existing Output Design. **Never treat processing failure as a bad demonstration**.

## 3. Non-goals and still-open decisions

**Frozen now:** output interface pattern (JSON object + controlled semantics + note + evidence references + deterministic QC), strict source ownership, original response immutability, uncertainty/neighbor safety; no free-text-only labeling pipeline.

**Still to propose and freeze separately:** exact allowed \`motion_phase/object_relation/event_type/event_outcome/evidence_quality\` values; nullability/array cardinality; definition of \`gripper_state\` and whether it belongs in primary P2 MVP; exact Prompt v1 words + SHA; model family/revision (formal candidate Qwen3-VL-8B-Instruct, local 4B Q4 is only a development probe); vision-only vs vision+state Action A/B; independent human annotation rubric, episode-disjoint evaluation splits and metrics; budget/stop thresholds, optional 256/512 native RGB.

Do **not** conflate:
- Phase1C observability A/B: target-only frames vs target+neighbor.
- Future formal semantic A/B: Vision-only vs Vision + permitted robot-state/action (same target frames).
- JSON shape validity vs visual factual correctness.
- A VLM annotation candidate vs training data discard/weight action.

Retrieval stays \`HOLD_BY_OWNER\`; G3 v1 has **no** ACT/VLA training and \`training_disposition=NOT_EVALUATED\`.

## 4. Next local execution — small and gated

1. **First fetch/pull latest \`origin/main\`** into a clean healthy worktree; do not overwrite unrelated local state. Inspect this Owner Freeze and the existing Output Design; continue on isolated task branch/worktree.
2. Reuse Phase1B/Phase1C frame/provenance utilities and deployed local 4B probe; do not rebuild renderer, download weights again or merge other runtime branches into main implicitly.
3. Draft a compact **minimal enum taxonomy + JSON Schema + versioned Argus-inspired P2 Prompt** and implement canonical validation. Preserve the draft-vs-frozen boundary; proposed categories remain pending Owner review unless explicitly approved later.
4. Before any broader run, perform a **tiny 8–12 Segment development pilot** only after prompt/schema and sample IDs/hashes are pinned; use one fixed local 4B Q4 configuration with JSON-only and a safe output-token cap so complete responses end in \`stop\`. This is *inference*, not training.
5. Add mock/contract tests first, then a few real images; compare model predictions to independently readable frames and human review where needed. **No accuracy percentages without human GT**, no formal held-out, no automatic 8B or high-res contract change.
6. Report whether the structured response is valid, whether evidence is within target bounds, whether note/enum conflicts persist, and which exact fields/labels need redesign; stop and request Owner approval of taxonomy/Prompt before formal benchmarking.

**Local pilot gate:** \`SMALL_PILOT_PENDING\` until it actually runs. A successful local 4B inference merely shows implementation feasibility. It does not constitute formal Qwen3-VL-8B semantic accuracy evidence.
