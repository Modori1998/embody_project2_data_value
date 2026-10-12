"""Project 2 G3 Phase-1 read-only audit utilities.

Scope of this package (deliberately narrow):

- deterministic Development-pool sampling that avoids every frozen Formal set;
- a no-VLM EvidencePack adapter that assembles the evidence a future G3
  labeler would be allowed to consume;
- explicit forbidden-field and temporal-alignment guards.

This package never calls a VLM, never runs Formal retrieval, and never mutates
Frozen G1 / M2 / retrieval artifacts or the raw dataset.  It is an audit-only
scaffold for the P2-G3 / Argus engineering feasibility review.
"""

from __future__ import annotations

G3_PHASE1_VERSION = "P2_G3_PHASE1_AUDIT_V1"

__all__ = ["G3_PHASE1_VERSION"]
