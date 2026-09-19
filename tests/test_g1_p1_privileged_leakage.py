"""Formal calculator must not consume privileged simulator GT."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.signals import FormalSignals, compute_formal_signals


FORBIDDEN_FIELD_TOKENS = (
    "can_pos",
    "can_quat",
    "can_to_robot0",
    "object_packed",
    "object_gt",
    "reward",
    "rewards",
    "success",
    "dones",
    "next_obs",
    "raw_mujoco",
    "states",
)

FORBIDDEN_STRINGS_IN_CALCULATOR = {
    "Can_pos",
    "Can_quat",
    "Can_to_robot0_eef",
    "object-state",
    "next_obs",
    "rewards",
    "dones",
    "success",
}


class PrivilegedLeakageTests(unittest.TestCase):
    def test_privileged_leakage(self) -> None:
        field_names = {name.lower() for name in FormalSignals.__dataclass_fields__}
        leaked = [token for token in FORBIDDEN_FIELD_TOKENS if any(token in field for field in field_names)]
        self.assertEqual(leaked, [], f"FormalSignals leaked privileged fields: {leaked}")

        source_path = Path(compute_formal_signals.__code__.co_filename)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        leaked_strings = sorted(FORBIDDEN_STRINGS_IN_CALCULATOR.intersection(strings))
        self.assertEqual(leaked_strings, [], f"calculator source contains privileged keys: {leaked_strings}")
        self.assertTrue(source_path.name == "signals.py")


if __name__ == "__main__":
    unittest.main()
