"""Project 2 G1: Signal Contract (P1) + exploratory Boundary Engine (P2).

G1-P2 consumes frozen G1-P1 FormalSignals. It does not freeze thresholds
and does not emit semantic phase labels.
"""

from .boundary_config import G1P2Config, load_g1_p2_config
from .config import G1P1Config, load_g1_p1_config

__all__ = ["G1P1Config", "load_g1_p1_config", "G1P2Config", "load_g1_p2_config"]
