"""Launch Project 2 G1 Audit Web (Batch 3: Human Review export).

Default bind is 127.0.0.1. This process has no authentication.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.paths import PROJECT2_ROOT
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.registry import default_owner_db_path, default_registry_path
from project2_g1_audit_web.reviews import DEFAULT_REVIEWER

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project 2 G1 Audit Web (Batch 3)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--project-root", type=Path, default=PROJECT2_ROOT)
    parser.add_argument("--registry-path", type=Path, default=None)
    parser.add_argument("--sqlite-path", type=Path, default=None)
    parser.add_argument("--proxy-cache-root", type=Path, default=None)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry_path = args.registry_path or default_registry_path(args.project_root)
    sqlite_path = args.sqlite_path or default_owner_db_path(args.project_root)
    cache_root = args.proxy_cache_root or (Path(sqlite_path).parent / "video_proxy_cache")
    app = create_app(
        project_root=args.project_root,
        registry_path=registry_path,
        owner_db_path=sqlite_path,
        proxy_cache_root=cache_root,
        reviewer=args.reviewer,
    )
    print("Project 2 G1 Audit Web Batch 3")
    print("host =", args.host)
    print("port =", args.port)
    print("registry =", Path(registry_path).resolve())
    print("owner_sqlite =", Path(sqlite_path).resolve())
    print("proxy_cache =", Path(cache_root).resolve())
    print("reviewer =", args.reviewer)
    print("open =", f"http://{args.host}:{args.port}/")
    print("stop = Ctrl+C")
    if args.host in {"0.0.0.0", "::"}:
        print("WARNING: unauthenticated service is bound beyond localhost.")
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
