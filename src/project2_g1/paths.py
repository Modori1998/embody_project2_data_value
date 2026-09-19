"""Local discovery paths. Raw datasets are READ_ONLY."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT2_ROOT = Path(__file__).resolve().parents[2]
PROJECT1_ROOT = Path(r"C:\Users\95611\embody\2-Project1_dataset")
P1_SCR = PROJECT1_ROOT / "scr"
P1_ADAPTER_PATH = P1_SCR / "project1_benchmark" / "robomimic_adapter.py"
P1_RGB_MATERIALIZER_PATH = P1_SCR / "project1_benchmark" / "robomimic_rgb_materializer.py"
P1_SOURCE_CONTRACT = (
    PROJECT1_ROOT
    / "doc"
    / "0-overview"
    / "Project1_RoboMimic_Unified_Source_Contract_v1_20260906.md"
)

DATASET_RAW_HDF5 = Path(r"C:\Users\95611\embody\1-dataset\robomimic\demo_v15.hdf5")
DATASET_LOW_DIM_HDF5 = Path(r"C:\Users\95611\embody\1-dataset\robomimic\low_dim_v15.hdf5")
DATASET_TYPE = "RoboMimic v1.5 Can/MH (low_dim + raw dual-HDF5)"

OUTPUT_ROOT = PROJECT2_ROOT / "outputs" / "g1_p1_signal_audit"
CONFIG_PATH = PROJECT2_ROOT / "configs" / "g1_p1_signal_contract.json"
G1_P2_CONFIG_PATH = PROJECT2_ROOT / "configs" / "g1_p2_exploratory_segmentation.json"
G1_P2_OUTPUT_ROOT = PROJECT2_ROOT / "outputs" / "g1_p2_boundary_audit"

PROJECT2_ENGINEERING_MASTER = (
    PROJECT2_ROOT / "0-doc" / "Project_2_Engineering_Design_Master_v1_20260914.md"
)
PROJECT2_ROADMAP = (
    PROJECT2_ROOT / "0-doc" / "Project2_Development_Roadmap_and_Design_Gate_Plan_v1_20260914.md"
)
PROJECT2_READABLE_DESIGN = (
    PROJECT2_ROOT / "0-doc" / "02_robot_demonstration_mining_autolabel_design.md"
)


def ensure_project1_on_path() -> Path:
    """Import P1 production adapter without copying it."""

    if not P1_SCR.is_dir():
        raise FileNotFoundError(f"Project 1 scr directory missing: {P1_SCR}")
    path = str(P1_SCR)
    if path not in sys.path:
        sys.path.insert(0, path)
    return P1_SCR
