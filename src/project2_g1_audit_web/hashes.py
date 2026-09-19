"""Deterministic config / signal-contract hashes. No mtime, no machine paths."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SIGNAL_CONTRACT_VERSION = "g1_p1_signal_contract.v0"
SOURCE_DATASET_ID = "robomimic_v15_can_mh"

# Frozen identity of Formal Signal formulas. Changing this string set is the
# way to invalidate P1 review reuse. It does not alter signal computation.
FORMAL_SIGNAL_IDENTITY = {
    "index_rule": "POLICY_OBSERVATION_t = RGB_t + PROPRIO_t; ACTION_TARGET_t = ACTION_t",
    "delta_rule": "delta[0]=0; delta[t]=x[t]-x[t-1]",
    "signals": [
        "eef_x",
        "eef_y",
        "eef_z",
        "delta_x",
        "delta_y",
        "delta_z",
        "translation_step_norm",
        "translation_speed",
        "direction_change_evidence",
        "gripper_aperture",
        "gripper_state_candidate",
        "angular_change",
        "action_change_evidence",
    ],
}


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_canonical(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def config_hash_from_payload(payload: Any) -> str:
    return sha256_canonical(payload)


def config_hash_from_path(path: str | Path) -> str:
    return config_hash_from_payload(load_json(path))


def signal_contract_hash_from_payload(payload: Any) -> str:
    return sha256_canonical(
        {
            "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "config": payload,
            "implementation_identity": FORMAL_SIGNAL_IDENTITY,
        }
    )


def signal_contract_hash_from_path(path: str | Path) -> str:
    return signal_contract_hash_from_payload(load_json(path))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: str | Path) -> Iterable[Path]:
    base = Path(root)
    return sorted(path for path in base.rglob("*") if path.is_file())


def tree_fingerprint(root: str | Path) -> dict[str, Any]:
    base = Path(root).resolve()
    files = []
    tree = hashlib.sha256()
    for path in iter_files(base):
        rel = path.relative_to(base).as_posix()
        digest = sha256_file(path)
        files.append({"rel": rel, "sha256": digest, "size": path.stat().st_size})
        tree.update(rel.encode("utf-8"))
        tree.update(b"\n")
        tree.update(digest.encode("ascii"))
        tree.update(b"\n")
    return {
        "root": str(base),
        "file_count": len(files),
        "tree_fingerprint": tree.hexdigest(),
        "files": files,
    }


def allocate_run_id(*, run_stage: str, config_hash: str, created_at: str, salt: str = "") -> str:
    stamp = "undated"
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        stamp = parsed.strftime("%Y%m%d_%H%M%S")
    except ValueError:
        digits = "".join(ch for ch in created_at if ch.isdigit())
        stamp = digits[:14] or "undated"
    stage = str(run_stage or "run").strip().lower()
    digest = hashlib.sha256(
        f"{stage}|{config_hash}|{created_at}|{salt}".encode("utf-8")
    ).hexdigest()[:8]
    return f"g1_{stage}_{stamp}_{digest}"
