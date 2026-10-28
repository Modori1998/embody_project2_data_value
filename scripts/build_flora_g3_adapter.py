"""Offline CLI: python scripts/build_flora_g3_adapter.py FLORA_ZIP OUT_DIR [--source-manifest FILE]."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.project2_g3.flora_adapter import AdapterError, build_links


def main():
    p = argparse.ArgumentParser(description="Build Flora native -> P2 G1 *candidate* links without model inference")
    p.add_argument("flora_zip")
    p.add_argument("output_dir")
    p.add_argument("--source-manifest", default=None)
    args = p.parse_args()
    try:
        result = build_links(args.flora_zip, args.output_dir, args.source_manifest)
    except (AdapterError, OSError, ValueError) as exc:
        print(f"ADAPTER_INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["alignment_blocked"] else 3


if __name__ == "__main__":
    sys.exit(main())
