"""Project 2 G1 Audit Web packaging (Batch 2: Human Review persistence).

Implements the Phase 6 Human Calibration Export. It does not implement
Detector calibration, Canonical GT transformation, or parameter search.
"""

from .contract import CONTRACT_VERSION, validate_g1_audit_folder

__all__ = ["CONTRACT_VERSION", "validate_g1_audit_folder"]
