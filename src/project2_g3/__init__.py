"""P2-G3 semantic annotation package.

This package currently contains the **v0.1 candidate** structured-JSON
annotation contract, its prompt builder, its deterministic validator and the
deterministic development-sample builder used by the tiny baseline.

Frozen upstream authority (read before changing anything here)
-------------------------------------------------------------
* ``0-doc/10-design-review/P2_G3_Structured_JSON_and_Evidence_Contract_Owner_Freeze_20261013.md``
  -- ``G3_OUTPUT_ARCHITECTURE = FROZEN_JSON_ENUM_NOTE_FRAME_EVIDENCE_QC_V1``.
* ``0-doc/10-design-review/P2_G3_Argus_Output_Design_v1_20261012.md`` -- draft schema.
* ``0-doc/10-design-review/P2_G3_Phase1B_1C_Observability_Owner_Freeze_20261013.md``
  -- ``CONTEXT_POLICY_DECISION = KEEP_CONTEXT_OPTIONAL``.

Boundary of what is frozen: the *architecture* (one JSON object, controlled
enums, short grounding note, frame-level evidence citations, deterministic QC,
trusted caller-owned provenance, immutable raw responses).  The **exact enum
values, the prompt bytes and the schema version here are v0.1 candidates and
are NOT Owner-frozen.**
"""

SEMANTIC_SCHEMA_VERSION = "P2_G3_SEMANTIC_JSON_V0_1_CANDIDATE"
SEMANTIC_PROMPT_VERSION = "P2_G3_ARGUS_INSPIRED_PROMPT_V0_1_CANDIDATE"

__all__ = ["SEMANTIC_SCHEMA_VERSION", "SEMANTIC_PROMPT_VERSION"]
