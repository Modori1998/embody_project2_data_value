"""Controlled G1 media serving. Reuses M07 Range / ETag response; G1 resolver is local."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import Response
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from project2_g1.paths import ensure_project1_on_path

from .contract import MEDIA_FIELD_BY_KEY, MEDIA_KEYS
from .input import EpisodeRecord

ensure_project1_on_path()
from project1_benchmark.m07_audit_web_media import MediaAccessError, media_file_response  # noqa: E402


def encode_episode_id(episode_id: str) -> str:
    from urllib.parse import quote

    return quote(str(episode_id or "").replace("/", "--"), safe="-_.")


def decode_episode_id(encoded: str) -> str:
    from urllib.parse import unquote

    return unquote(str(encoded or "")).replace("--", "/")


def media_url(run_id: str, episode_id: str, media_key: str) -> str:
    return "/media/{}/{}/{}".format(run_id, encode_episode_id(episode_id), media_key)


def _under_root(run_root: Path, rel: str) -> Path:
    text = str(rel or "").strip().replace("\\", "/")
    if text == "" or text.startswith("/") or (len(text) >= 2 and text[1] == ":"):
        raise MediaAccessError(HTTP_403_FORBIDDEN, "media path is not relative")
    if Path(text).is_absolute() or ".." in Path(text).parts:
        raise MediaAccessError(HTTP_403_FORBIDDEN, "path traversal blocked")
    root = run_root.resolve()
    candidate = (root / text).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MediaAccessError(HTTP_403_FORBIDDEN, "media path escapes run root") from exc
    return candidate


def resolve_g1_media_file(run_root: str | Path, episode: EpisodeRecord, media_key: str) -> Path:
    key = str(media_key or "").strip()
    if key not in MEDIA_KEYS or key not in MEDIA_FIELD_BY_KEY:
        raise MediaAccessError(HTTP_403_FORBIDDEN, f"unknown media_key: {media_key!r}")
    if "/" in key or "\\" in key or ".." in key:
        raise MediaAccessError(HTTP_403_FORBIDDEN, "illegal media_key")
    if key == "video":
        rel = episode.video_relpath
    elif key == "signal_boundary_plot":
        rel = episode.plot_relpath
    else:
        rel = episode.signal_plot_relpath
    if not rel:
        raise MediaAccessError(HTTP_404_NOT_FOUND, f"empty media field for {key}")
    path = _under_root(Path(run_root), rel)
    if not path.is_file() or path.stat().st_size <= 0:
        raise MediaAccessError(HTTP_404_NOT_FOUND, "media file missing")
    return path


def g1_media_file_response(path: Path, request: Request) -> Response:
    return media_file_response(path, request)
