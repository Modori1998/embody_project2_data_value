# P2-G3 — Semantic JSON v0.2 Output Design | Owner Freeze (2026-10-13)

> STATUS: OWNER_APPROVED_V0_2_DEV_SPEC; NOT FORMAL TAXONOMY V1; MODEL RESULTS NOT YET OBSERVED.

## 1. Minimal schema delta

Preserve existing seven model-owned keys: motion_phase, object_relation, gripper_state, events, evidence_frame_indices, evidence_quality, observation_note.

Add one required model-owned key: `event_assessment` with values `event_visible`, `no_event_visible`, `insufficient_evidence`.

Model must return exactly one JSON object. Schema sets additionalProperties=false at root and event rows. Episode/Segment/frame origin, model revision and hashes are attached by trusted caller metadata, not trusted from model output.

Keep nine motion-phase enums with tightened time-based definitions in Taxonomy v0.2 Design. Keep object_relation six enums, gripper_state four enums; `gripper_state` describes last valid target-frame jaws only. Keep events as array of `{event_type,event_outcome,evidence_frame_indices}`. Main substantive event types are grasp_attempt, release_attempt, object_motion; previous none_observed/uncertain event-item sentinels are replaced by event_assessment in v0.2. Do not modify v0.1 records.

Keep event_outcome success/failure/unclear for **local attempts**, not whole-Episode task outcome. For object_motion where no attempted task effect is defined, report unclear rather than manufacture success/failure; possible later not_applicable needs separate decision.

Evidence quality sufficient/partial/insufficient is now assessed relative to the **primary motion_phase**, not all fields. event_assessment expresses event occurrence visibility; event_outcome=unclear handles event-result ambiguity.

## 2. Event cardinality contract

| event_assessment | Valid events | Meaning |
| --- | --- | --- |
| event_visible | One or more substantive event items with target frame citations | A candidate event is visibly supported |
| no_event_visible | Empty array `[]` | No event observed within the sampled target frames; unsampled intervals remain unknown |
| insufficient_evidence | Empty array `[]` | Unable to establish whether an event occurred |

Any conflicting combination is hard-invalid Schema/contract output. Do not silently fix it. If event occurs but outcome is unknown, choose `event_visible` with event_outcome=`unclear`.

## 3. Schematic JSON payload (not a model output)

```json
{
  "motion_phase": "grasp",
  "object_relation": ["gripper_around"],
  "gripper_state": "closed",
  "event_assessment": "event_visible",
  "events": [{"event_type": "grasp_attempt", "event_outcome": "unclear", "evidence_frame_indices": [40, 45]}],
  "evidence_frame_indices": [40, 45],
  "evidence_quality": "sufficient",
  "observation_note": "The gripper closes toward an object; successful acquisition is not established."
}
```

Frame indices in examples are illustrative and must be checked against the actual target Segment's immutable evidence manifest.

## 4. Validation policy

- DETERMINISTIC hard-invalid: unparseable/incomplete response, missing field, wrong type/enum, event_assessment/events mismatch, forbidden caller-owned ID, illegal frame index, source/role mismatch, neighbor citation as target event. Preserve raw response.
- REVIEW CANDIDATE: note contradicts asserted motion, insufficient evidence for definite event outcome, phase and evidence_quality at odds, semantic note/category disagreement. Text patterns can have false positives; never rewrite output based on heuristics.
- VALID means it passes known structural and logical checks, not human-confirmed semantic correctness.
- Maintain PROCESSING_ERROR / INVALID_INPUT / INVALID_MODEL_OUTPUT / REVIEW_REQUIRED / UNRESOLVED / VALID categories with the v0.2 versioned changes.

## 5. Reporting

Report separately: `motion_phase_uncertain_rate`, `evidence_quality_partial_or_insufficient_rate`, `event_assessment_insufficient_evidence_rate`, `whole_annotation_abstained_rate`, `event_visible_rate`, `events_nonempty_rate`, `schema_valid_rate`, `frame_reference_valid_rate`, `review_required_rate`.

Previous v0.1 `whole_annotation_abstained_rate` means all substantive phase/jaw/relation fields abstain; v0.2 may retain this status definition but must report partial/field-level uncertainty separately. Do not compare v0.2 event_assessment accuracy to v0.1 because v0.1 had no such field.

## 6. Baseline + restrictions

Use same fixed local 4B Q4 for first pilot, target-only 128x128 clean RGB; diagnostic cases demo_33-S0001/demo_75-S0001/demo_47-S0003 are already seen, and NEW 8–12 Development cases must be pinned separately before running. A v0.1/v0.2 same-sample comparison should use matched source/frame/model/runtime parameters; v0.2 Prompt and Schema frozen before call. Any comparison against semantic ground truth requires independent human reference; otherwise mark semantic accuracy NOT_ESTIMABLE.

All run outputs/version hashes and raw responses must remain immutable. No G1/M2 contract edits, no trained model, no 8B formal evaluation, no held-out, no high-res RGB contract change, no training KEEP/DROP decisions. The updated output architecture is approved for v0.2 implementation but NOT promoted to formal P2-G3 Taxonomy v1.
