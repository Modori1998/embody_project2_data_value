from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
A0_ROOT = ROOT / "outputs/g1_p3_stage_a0/g1_stage_a0_20260918_162418_7cbf826e"
SCORE_ROOT = ROOT / "outputs/g1_p3_scoring/g1_baseline_score_20260918_155714_42295cc6"
GT_ROOT = ROOT / "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89"
RUN_ROOT = ROOT / "outputs/g1_audit_runs/g1_calibration_20260918_141032_781e5d8b"
SEED_EXPORT = ROOT / "outputs/g1_audit_web/human_calibration_export/g1_cal_seed_export_20260917_214637_2f8d8802"
FRESH_EXPORT = ROOT / "outputs/g1_audit_web/human_calibration_export/g1_cal_export_20260918_120335_81c068bf"
OWNER_SQLITE = ROOT / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"
PROTOCOLS = [
    ROOT / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_20260917.md",
    ROOT / "0-doc/10-design-review/Project2_G1_P3_Calibration_Protocol_FROZEN_v1_1_PATCH_20260918.md",
]
DATASET = Path(r"C:\Users\95611\embody\1-dataset\robomimic\demo_v15.hdf5")
OUT_BASE = ROOT / "outputs/g1_p3_rule_family_a_prep"
REPORT = ROOT / "0-doc/Project2_G1_P3_RuleFamilyA_Displacement_Preparation_Result_20260918.md"

FEATURES = ["pre_displacement_m", "post_displacement_m", "min_pre_post_displacement_m"]
SOURCE_EVENT_CSV = A0_ROOT / "stage_a0_direction_event_analysis.csv"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    for file_path in files:
        rel = file_path.relative_to(path).as_posix() if path.is_dir() else file_path.name
        digest.update(rel.encode("utf-8"))
        digest.update(str(file_path.stat().st_size).encode("ascii"))
        digest.update(sha256_file(file_path).encode("ascii"))
    return {"sha256": digest.hexdigest(), "file_count": len(files)}


def dataset_fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def source_fingerprints() -> dict:
    return {
        "baseline_run": tree_fingerprint(RUN_ROOT),
        "baseline_score": tree_fingerprint(SCORE_ROOT),
        "canonical_gt": tree_fingerprint(GT_ROOT),
        "stage_a0": tree_fingerprint(A0_ROOT),
        "seed_export": tree_fingerprint(SEED_EXPORT),
        "fresh_export": tree_fingerprint(FRESH_EXPORT),
        "owner_sqlite": tree_fingerprint(OWNER_SQLITE),
        "protocol": {p.name: tree_fingerprint(p) for p in PROTOCOLS},
        "dataset": dataset_fingerprint(DATASET),
    }


def f(value: str | float | int | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def event_rows() -> list[dict]:
    source = read_csv(SOURCE_EVENT_CSV)
    rows: list[dict] = []
    for row in source:
        if row["human_class"] not in {"VALID_DIRECTION", "DIRECTION_FP"}:
            continue
        pre = float(row["pre_displacement_m"])
        post = float(row["post_displacement_m"])
        rows.append(
            {
                "episode_id": row["episode_id"],
                "pred_boundary_id": row["pred_boundary_id"],
                "pred_frame": int(row["pred_frame"]),
                "human_class": row["human_class"],
                "source_package": row["source_package"],
                "error_mode": row["error_mode"],
                "reason_code": row["reason_code"],
                "candidate_type": "DIRECTION_CHANGE",
                "evidence_value": float(row["evidence_value"]),
                "run_length": int(row["run_length"]),
                "pre_displacement_m": pre,
                "post_displacement_m": post,
                "min_pre_post_displacement_m": min(pre, post),
                "max_pre_post_displacement_m": max(pre, post),
                "displacement_asymmetry_m": abs(pre - post),
                "distance_to_nearest_gripper": f(row["distance_to_nearest_gripper_final"]),
                "local_speed_min": f(row["local_speed_min"]),
                "field_provenance": (
                    "Stage A0 ANALYSIS_DERIVED_FIELD; EEF robot0_eef_pos metres; "
                    "W=8; heading_vector=sum(delta_xyz[start:end]); Euclidean norm"
                ),
            }
        )
    return rows


def quantile(values: list[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), q, method="linear"))


def stats(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min": min(values),
        "q10": quantile(values, 0.10),
        "q25": quantile(values, 0.25),
        "median": quantile(values, 0.50),
        "q75": quantile(values, 0.75),
        "q90": quantile(values, 0.90),
        "max": max(values),
        "mean": float(np.mean(values)),
    }


def distribution_rows(events: list[dict]) -> list[dict]:
    output: list[dict] = []
    for feature in FEATURES:
        for package in ("ALL", "SEED", "FRESH"):
            selected = events if package == "ALL" else [e for e in events if e["source_package"] == package]
            by_class = {
                cls: [float(e[feature]) for e in selected if e["human_class"] == cls]
                for cls in ("VALID_DIRECTION", "DIRECTION_FP")
            }
            class_stats = {cls: stats(vals) for cls, vals in by_class.items()}
            valid, fp = class_stats["VALID_DIRECTION"], class_stats["DIRECTION_FP"]
            range_low, range_high = max(valid["min"], fp["min"]), min(valid["max"], fp["max"])
            iqr_low, iqr_high = max(valid["q25"], fp["q25"]), min(valid["q75"], fp["q75"])
            for cls in ("VALID_DIRECTION", "DIRECTION_FP"):
                row = {"feature": feature, "source_package": package, "human_class": cls}
                row.update(class_stats[cls])
                row.update(
                    {
                        "range_overlap": "YES" if range_high >= range_low else "NO",
                        "range_overlap_low": range_low if range_high >= range_low else "",
                        "range_overlap_high": range_high if range_high >= range_low else "",
                        "iqr_overlap": "YES" if iqr_high >= iqr_low else "NO",
                        "iqr_overlap_low": iqr_low if iqr_high >= iqr_low else "",
                        "iqr_overlap_high": iqr_high if iqr_high >= iqr_low else "",
                        "valid_minimum": valid["min"],
                        "valid_q10": valid["q10"],
                        "fp_minimum": fp["min"],
                        "fp_maximum": fp["max"],
                    }
                )
                output.append(row)
    return output


def mode_rows(events: list[dict]) -> list[dict]:
    fps = [e for e in events if e["human_class"] == "DIRECTION_FP"]
    output = []
    for mode in ("MODE_01", "MODE_02", "MODE_03", "UNASSIGNED"):
        selected = [e for e in fps if e["error_mode"] == mode]
        output.append(
            {
                "error_mode": mode,
                "count": len(selected),
                "events": "|".join(f'{e["episode_id"]}@{e["pred_frame"]}' for e in selected),
                "pre_min": min(e["pre_displacement_m"] for e in selected),
                "pre_median": float(np.median([e["pre_displacement_m"] for e in selected])),
                "pre_max": max(e["pre_displacement_m"] for e in selected),
                "post_min": min(e["post_displacement_m"] for e in selected),
                "post_median": float(np.median([e["post_displacement_m"] for e in selected])),
                "post_max": max(e["post_displacement_m"] for e in selected),
                "min_pre_post_min": min(e["min_pre_post_displacement_m"] for e in selected),
                "min_pre_post_median": float(np.median([e["min_pre_post_displacement_m"] for e in selected])),
                "min_pre_post_max": max(e["min_pre_post_displacement_m"] for e in selected),
                "primary_layer": "CONSOLIDATION" if mode == "MODE_03" else "CANDIDATE_ACCEPTANCE_REVIEW",
            }
        )
    return output


def counterexample_rows(events: list[dict]) -> list[dict]:
    valid = sorted(
        [e for e in events if e["human_class"] == "VALID_DIRECTION"],
        key=lambda e: e["min_pre_post_displacement_m"],
    )
    rows = []
    for rank, event in enumerate(valid[:5], 1):
        row = dict(event)
        row.update({"counterexample_type": "LOWEST_VALID_MIN_PRE_POST", "rank": rank})
        rows.append(row)
    fresh = [e for e in valid if e["source_package"] == "FRESH"]
    for feature in FEATURES:
        event = min(fresh, key=lambda e: e[feature])
        row = dict(event)
        row.update({"counterexample_type": f"FRESH_VALID_LOWEST_{feature.upper()}", "rank": 1})
        rows.append(row)
    return rows


def label(event: dict) -> str:
    return f'{event["episode_id"].replace("data/", "")}@{event["pred_frame"]}'


def class_color(event: dict) -> str:
    return "#1769aa" if event["human_class"] == "VALID_DIRECTION" else "#d32f2f"


def distribution_plot(events: list[dict], feature: str, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    classes = ["VALID_DIRECTION", "DIRECTION_FP"]
    for x, cls in enumerate(classes):
        selected = [e for e in events if e["human_class"] == cls]
        jitter = np.linspace(-0.13, 0.13, len(selected))
        for offset, event in zip(jitter, sorted(selected, key=lambda e: e[feature])):
            ax.scatter(x + offset, event[feature], c=class_color(event), s=45, alpha=0.85)
            ax.annotate(label(event), (x + offset, event[feature]), xytext=(3, 3), textcoords="offset points", fontsize=7)
    ax.set_xticks([0, 1], classes)
    ax.set_ylabel(f"{feature} (m)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def scatter_plot(events: list[dict], title: str, path: Path, mode_labels: bool = False) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    markers = {"SEED": "o", "FRESH": "s"}
    for event in events:
        ax.scatter(
            event["pre_displacement_m"], event["post_displacement_m"],
            c=class_color(event), marker=markers[event["source_package"]], s=60, alpha=0.85,
        )
        suffix = f'/{event["error_mode"]}' if mode_labels and event["error_mode"] else ""
        ax.annotate(label(event) + suffix, (event["pre_displacement_m"], event["post_displacement_m"]),
                    xytext=(4, 3), textcoords="offset points", fontsize=7)
    ax.set_xlabel("pre_displacement_m")
    ax.set_ylabel("post_displacement_m")
    ax.set_title(title + " | blue=VALID red=FP; circle=Seed square=Fresh")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def counterexample_plot(events: list[dict], path: Path) -> None:
    valid = sorted([e for e in events if e["human_class"] == "VALID_DIRECTION"], key=lambda e: e["min_pre_post_displacement_m"])[:5]
    fig, ax = plt.subplots(figsize=(10, 5))
    names = [label(e) + f'/{e["source_package"]}' for e in valid]
    ax.barh(names[::-1], [e["min_pre_post_displacement_m"] for e in valid][::-1], color="#1769aa")
    ax.set_xlabel("min(pre, post) displacement (m)")
    ax.set_title("Lowest five VALID Direction counterexamples")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def loo_robustness(events: list[dict]) -> dict:
    result = {}
    for feature in FEATURES:
        checks = []
        for omitted in events:
            remaining = [e for e in events if e is not omitted]
            valid = [e[feature] for e in remaining if e["human_class"] == "VALID_DIRECTION"]
            fp = [e[feature] for e in remaining if e["human_class"] == "DIRECTION_FP"]
            checks.append(float(np.median(valid)) > float(np.median(fp)))
        result[feature] = {
            "qualitative_test": "VALID median > FP median after omitting each single event; no cutoff fitted",
            "passes": sum(checks),
            "total": len(checks),
            "trend_survives_every_omission": all(checks),
        }
    return result


def make_report(prep_id: str, prep_root: Path, events: list[dict], distributions: list[dict], modes: list[dict], immutability: dict) -> str:
    def d(feature: str, cls: str, package: str = "ALL") -> dict:
        return next(r for r in distributions if r["feature"] == feature and r["human_class"] == cls and r["source_package"] == package)

    def compact(row: dict) -> str:
        return (
            f'n={row["count"]}, min={row["min"]:.6f}, q25={row["q25"]:.6f}, '
            f'median={row["median"]:.6f}, q75={row["q75"]:.6f}, max={row["max"]:.6f}, mean={row["mean"]:.6f}'
        )

    lowest = sorted([e for e in events if e["human_class"] == "VALID_DIRECTION"], key=lambda e: e["min_pre_post_displacement_m"])[:5]
    mode_lines = []
    for mode in modes:
        selected = [e for e in events if e["human_class"] == "DIRECTION_FP" and e["error_mode"] == mode["error_mode"]]
        facts = "; ".join(
            f'{label(e)} pre={e["pre_displacement_m"]:.6f}, post={e["post_displacement_m"]:.6f}, min={e["min_pre_post_displacement_m"]:.6f}'
            for e in selected
        )
        mode_lines.append(f'- `{mode["error_mode"]}`: {facts}')
    counter_lines = [
        f'| {i} | {label(e)} | {e["source_package"]} | {e["pre_displacement_m"]:.6f} | {e["post_displacement_m"]:.6f} | {e["min_pre_post_displacement_m"]:.6f} | {e["evidence_value"]:.6f} | {e["run_length"]} |'
        for i, e in enumerate(lowest, 1)
    ]
    return f"""# Project 2 G1-P3 Rule Family A Displacement Preparation Result

```text
DATE = 2026-09-18
DOCUMENT_STATUS = ANALYSIS_PREPARATION_RESULT
PREP_ID = {prep_id}
A_PREP_EVIDENCE_STATUS = READY_FOR_RULE_FAMILY_A_REVIEW
DETECTOR_MODIFIED = NO
PARAMETER_SEARCH_EXECUTED = NO
THRESHOLD_SWEEP = NO
DISPLACEMENT_CUTOFF_SELECTED = NO
STAGE_A_EXECUTED = NO
```

## Input Identity

```text
baseline_run_id = g1_calibration_20260918_141032_781e5d8b
baseline_score_id = g1_baseline_score_20260918_155714_42295cc6
canonical_gt_snapshot_id = g1_canonical_gt_20260918_131636_c9916b89
stage_a0_analysis_id = g1_stage_a0_20260918_162418_7cbf826e
config_hash = dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630
signal_contract_hash = 24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d
```

## Displacement Semantics

`pre_displacement_m = ||sum(delta_xyz[t-8:t])||₂`; `post_displacement_m = ||sum(delta_xyz[t:t+8])||₂`。
`delta_xyz` 是 `obs/robot0_eef_pos` 的 backward difference，单位 meter；窗口在 Episode 边缘 clip 到 `[0,n)`。
这与 `direction_change_evidence` 使用相同左右窗口。字段为 `ANALYSIS_DERIVED_FIELD`，不写回 P1。

```text
SIGNAL_CONTRACT_CHANGE = NO
```

## Cohort

```text
VALID_DIRECTION = 17 (Seed=6, Fresh=11)
DIRECTION_FP = 9 (MODE_01=3, MODE_02=3, MODE_03=1, UNASSIGNED=2)
NON_DIRECTION_FP = 1 (outside Rule Family A scope)
```

## Marginal Distributions

### pre_displacement_m

- VALID: {compact(d("pre_displacement_m", "VALID_DIRECTION"))}
- FP: {compact(d("pre_displacement_m", "DIRECTION_FP"))}
- Range overlap: `{d("pre_displacement_m", "VALID_DIRECTION")["range_overlap"]}`; IQR overlap: `{d("pre_displacement_m", "VALID_DIRECTION")["iqr_overlap"]}`

### post_displacement_m

- VALID: {compact(d("post_displacement_m", "VALID_DIRECTION"))}
- FP: {compact(d("post_displacement_m", "DIRECTION_FP"))}
- Range overlap: `{d("post_displacement_m", "VALID_DIRECTION")["range_overlap"]}`; IQR overlap: `{d("post_displacement_m", "VALID_DIRECTION")["iqr_overlap"]}`

### min(pre, post)

- VALID: {compact(d("min_pre_post_displacement_m", "VALID_DIRECTION"))}
- FP: {compact(d("min_pre_post_displacement_m", "DIRECTION_FP"))}
- Range overlap: `{d("min_pre_post_displacement_m", "VALID_DIRECTION")["range_overlap"]}`; IQR overlap: `{d("min_pre_post_displacement_m", "VALID_DIRECTION")["iqr_overlap"]}`

所有三个字段均为 range overlap，但 ALL cohort 的 IQR 不重叠。存在 FP 大位移反例和 VALID 低位移反例，不能由本报告推导 cutoff。

## MODE Facts

{chr(10).join(mode_lines)}

MODE_03 的 primary layer 保持 `CONSOLIDATION`；这里只记录其 displacement context。

## Lowest VALID Counterexamples

| rank | event | package | pre | post | min | evidence | run_length |
|---:|---|---|---:|---:|---:|---:|---:|
{chr(10).join(counter_lines)}

## Seed / Fresh Preparation Finding

Seed 与 Fresh 中，三个 displacement 字段的 VALID median 均高于 FP median；但 Fresh FP 只有 2 条，且 `demo_162@211` 是较大 displacement FP。

```text
SEED_PATTERN = VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP
FRESH_PATTERN = VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP
CONSISTENCY = INSUFFICIENT
INSUFFICIENT_FRESH_NEGATIVE_EVIDENCE = YES
```

## Rule Shape Evidence

- `both-side requirement｜双侧要求`：pre/post 各自保留方向性，能解释“运动后停住”或“几乎从静止起步”的哪一侧不足，但需要两个条件。
- `min(pre,post) requirement｜较弱侧位移要求`：与“双侧都充分”等价地表达最弱运动侧，单变量、物理解释更紧凑；本报告不选择阈值。

## Robustness

定性 leave-one-event-out 只检查 `VALID median > FP median` 是否由单点驱动，不拟合 cutoff。结果记录在 `rule_family_a_meta.json`。

## Immutability

```text
BASELINE_RUN_UNCHANGED = {immutability["baseline_run"]}
BASELINE_SCORE_UNCHANGED = {immutability["baseline_score"]}
CANONICAL_GT_UNCHANGED = {immutability["canonical_gt"]}
STAGE_A0_ARTIFACT_UNCHANGED = {immutability["stage_a0"]}
SEED_EXPORT_UNCHANGED = {immutability["seed_export"]}
FRESH_EXPORT_UNCHANGED = {immutability["fresh_export"]}
OWNER_SQLITE_UNCHANGED = {immutability["owner_sqlite"]}
PROTOCOL_UNCHANGED = {immutability["protocol"]}
DATASET_UNCHANGED = {immutability["dataset"]}
```

## Status

```text
A_PREP_EVIDENCE_STATUS = READY_FOR_RULE_FAMILY_A_REVIEW
```

This result prepares evidence only. It does not freeze a rule family or displacement threshold.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prep-id")
    args = parser.parse_args()
    now = datetime.now(timezone.utc).astimezone()
    prep_id = args.prep_id or f'g1_rule_family_a_prep_{now.strftime("%Y%m%d_%H%M%S")}'
    final_root = OUT_BASE / prep_id
    if final_root.exists():
        raise FileExistsError(f"Immutable output already exists: {final_root}")

    a0_meta = read_json(A0_ROOT / "stage_a0_meta.json")
    score_meta = read_json(SCORE_ROOT / "score_meta.json")
    gt_meta = read_json(GT_ROOT / "canonical_gt_meta.json")
    run_meta = read_json(RUN_ROOT / "run_meta.json")
    cohorts = read_json(A0_ROOT / "stage_a0_cohorts.json")
    ids = {
        a0_meta["baseline_run_id"], score_meta["run_id"], run_meta["run_id"]
    }
    if ids != {"g1_calibration_20260918_141032_781e5d8b"}:
        raise RuntimeError(f"Baseline identity mismatch: {ids}")
    if {a0_meta["canonical_gt_snapshot_id"], score_meta["canonical_gt_snapshot_id"], gt_meta["canonical_gt_snapshot_id"]} != {"g1_canonical_gt_20260918_131636_c9916b89"}:
        raise RuntimeError("Canonical GT identity mismatch")
    if len({a0_meta["config_hash"], score_meta["config_hash"], run_meta["config_hash"]}) != 1:
        raise RuntimeError("Config hash mismatch")
    if len({a0_meta["signal_contract_hash"], score_meta["signal_contract_hash"], run_meta["signal_contract_hash"]}) != 1:
        raise RuntimeError("Signal contract hash mismatch")

    before = source_fingerprints()
    events = event_rows()
    if len(events) != cohorts["TOTAL_VALID_DIRECTION"] + cohorts["DIRECTION_FP"]:
        raise RuntimeError("Cohort size mismatch")
    distributions = distribution_rows(events)
    modes = mode_rows(events)
    counters = counterexample_rows(events)
    loo = loo_robustness(events)

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{prep_id}.", dir=OUT_BASE))
    try:
        plots = temp_root / "plots"
        plots.mkdir()
        write_csv(temp_root / "rule_family_a_displacement_events.csv", events)
        write_csv(temp_root / "rule_family_a_distribution_summary.csv", distributions)
        write_csv(temp_root / "rule_family_a_counterexamples.csv", counters)
        write_csv(temp_root / "rule_family_a_mode_summary.csv", modes)
        distribution_plot(events, "pre_displacement_m", "Rule Family A: pre displacement", plots / "01_pre_displacement_valid_vs_fp.png")
        distribution_plot(events, "post_displacement_m", "Rule Family A: post displacement", plots / "02_post_displacement_valid_vs_fp.png")
        distribution_plot(events, "min_pre_post_displacement_m", "Rule Family A: min(pre, post)", plots / "03_min_pre_post_valid_vs_fp.png")
        scatter_plot(events, "Rule Family A: pre vs post", plots / "04_pre_vs_post_all.png")
        scatter_plot([e for e in events if e["source_package"] == "SEED"], "Seed-only pre vs post", plots / "05_pre_vs_post_seed.png")
        scatter_plot([e for e in events if e["source_package"] == "FRESH"], "Fresh-only pre vs post", plots / "06_pre_vs_post_fresh.png")
        scatter_plot(events, "MODE-labelled pre vs post", plots / "07_pre_vs_post_modes.png", mode_labels=True)
        counterexample_plot(events, plots / "08_lowest_valid_counterexamples.png")

        after = source_fingerprints()
        immutability = {key: "PASS" if before[key] == after[key] else "FAIL" for key in before}
        if set(immutability.values()) != {"PASS"}:
            raise RuntimeError(f"Source immutability failed: {immutability}")
        meta = {
            "prep_id": prep_id,
            "created_at": now.isoformat(),
            "status": "READY_FOR_RULE_FAMILY_A_REVIEW",
            "baseline_run_id": a0_meta["baseline_run_id"],
            "baseline_score_id": a0_meta["baseline_score_id"],
            "canonical_gt_snapshot_id": a0_meta["canonical_gt_snapshot_id"],
            "stage_a0_analysis_id": a0_meta["analysis_id"],
            "config_hash": a0_meta["config_hash"],
            "signal_contract_hash": a0_meta["signal_contract_hash"],
            "displacement_semantics": {
                "field_type": "ANALYSIS_DERIVED_FIELD",
                "window_frames": 8,
                "frame_interval_seconds": 0.05,
                "coordinate_source": "obs/robot0_eef_pos (EEF translation, metres)",
                "pre": "L2 norm of sum(delta_xyz[t-8:t])",
                "post": "L2 norm of sum(delta_xyz[t:t+8])",
                "edge_behavior": "heading_vector clips start/end to [0,n_frames)",
                "same_windows_as_direction_change_evidence": True,
                "signal_contract_change": "NO",
            },
            "cohort": cohorts,
            "non_direction_fp": {"count": 1, "event": "data/demo_255@135 IDLE_TO_MOVE", "outside_rule_family_a_scope": True},
            "leave_one_event_out": loo,
            "seed_fresh": {
                "seed_pattern": "VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP",
                "fresh_pattern": "VALID_HIGHER_MEDIAN_WITH_RANGE_OVERLAP",
                "consistency": "INSUFFICIENT",
                "insufficient_fresh_negative_evidence": True,
            },
            "source_fingerprints_before": before,
            "source_fingerprints_after": after,
            "immutability": immutability,
            "non_scope": {
                "detector_modified": False,
                "config_generated": False,
                "parameter_search_executed": False,
                "threshold_sweep": False,
                "displacement_cutoff_selected": False,
                "stage_a_executed": False,
                "stage_b_executed": False,
                "signal_contract_modified": False,
                "canonical_gt_modified": False,
                "human_review_modified": False,
            },
        }
        (temp_root / "rule_family_a_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        findings = make_report(prep_id, final_root, events, distributions, modes, immutability)
        (temp_root / "rule_family_a_preparation_findings.md").write_text(findings, encoding="utf-8-sig")
        os.replace(temp_root, final_root)
        report_tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
        report_tmp.write_text(findings, encoding="utf-8-sig")
        os.replace(report_tmp, REPORT)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    print(json.dumps({"prep_id": prep_id, "prep_root": str(final_root), "report": str(REPORT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
