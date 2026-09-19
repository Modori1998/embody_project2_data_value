"""AST leakage check for G1-P2 engine modules (no privileged Formal inputs)."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.boundary_engine import run_boundary_engine

FORBIDDEN = (
    "Can_pos",
    "Can_quat",
    "Can_to_robot0_eef",
    "next_obs",
    "rewards",
    "dones",
    "success",
)


class EnginePrivilegedLeakageFileTests(unittest.TestCase):
    def test_engine_files_do_not_reference_privileged_keys(self) -> None:
        files = [
            SRC / "project2_g1" / "boundary_engine.py",
            SRC / "project2_g1" / "boundary_config.py",
            SRC / "project2_g1" / "boundary_io.py",
        ]
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            strings = [
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            ]
            leaked = sorted(set(FORBIDDEN).intersection(strings))
            self.assertEqual(leaked, [], f"{path.name} leaked {leaked}")
        self.assertEqual(Path(run_boundary_engine.__code__.co_filename).name, "boundary_engine.py")
        self.assertEqual(run_boundary_engine.__code__.co_argcount, 2)


if __name__ == "__main__":
    unittest.main()
