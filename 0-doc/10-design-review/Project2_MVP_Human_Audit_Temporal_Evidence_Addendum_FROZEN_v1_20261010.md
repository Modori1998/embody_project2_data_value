# Project 2 MVP Human Audit Temporal Evidence Addendum FROZEN v1

```text
DATE = 2026-10-10
DOCUMENT_STATUS = FROZEN_v1
FROZEN = YES
SOURCE_OF_TRUTH = GITHUB_MAIN

DESIGN_OWNER_DECISION = APPROVED
PARENT_PROTOCOL = MVP_CORE_RETRIEVAL_PROTOCOL_v1
ADDENDUM_SCOPE = CALIBRATION_HUMAN_AUDIT_TEMPORAL_EVIDENCE
```

## Frozen rules

1. The reviewer may see a complete temporal GIF for each Query and Candidate segment.
2. Each GIF is generated only from Formal Clean RGB frames inside that segment's inclusive `[start_frame, end_frame]` range, in true temporal order. Uniform downsampling is allowed for size control, and the first and last frames must be retained.
3. Segment GIFs are Human Audit evidence only. They are forbidden as SigLIP2, Motion, VLM, FAISS, or any other Retrieval input.
4. The reviewer-visible GIF and page must not expose Retrieval method, similarity score, method-specific rank, or hidden-repeat status.
5. Existing `START / MIDDLE / END / GRIPPER_EVENT` keyframes remain visible alongside the GIF.
6. No Human relevance label existed when this addendum was frozen. Adding temporal evidence therefore does not alter or contaminate a previous Human label set.
7. Existing Calibration query selection, Top-5 results, blind item order, 83 unique pairs, 12 hidden repeats, and 95 total audit items remain unchanged.

This addendum changes only reviewer-visible temporal evidence. It does not modify the Frozen Retrieval Protocol's representation, candidate population, query selection, retrieval, or evaluation semantics.

```text
HUMAN_LABELS_STARTED = NO
RETRIEVAL_RERUN = NO
NEXT = CALIBRATION_BLIND_HUMAN_AUDIT
```
