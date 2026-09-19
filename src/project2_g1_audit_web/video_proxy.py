"""G1 adapter around M07 H264_BROWSER_V1 video proxy. Source files stay read-only."""

from __future__ import annotations

from pathlib import Path

from starlette.status import HTTP_403_FORBIDDEN

from project2_g1.paths import ensure_project1_on_path

ensure_project1_on_path()
from project1_benchmark.m07_audit_web_video_proxy import (  # noqa: E402
    PROXY_PROFILE_VERSION,
    AuditVideoProxyManager,
    ProxyIdentity,
    VideoProxyError,
    classify_needs_proxy,
    sha256_file,
    stable_proxy_url,
)


class G1AuditVideoProxyManager(AuditVideoProxyManager):
    """Prefer the newest readable source. Skip NTFS-denied stale registrations."""

    def _resolve_live_source(self, source_sha256: str) -> Path:
        with self._db_lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT source_path FROM allowed_sources
                    WHERE source_sha256 = ?
                    ORDER BY registered_at DESC
                    """,
                    (source_sha256,),
                ).fetchall()
            finally:
                connection.close()
        for row in rows:
            candidate = Path(str(row["source_path"]))
            try:
                if candidate.is_file() and sha256_file(candidate) == source_sha256:
                    return candidate
            except OSError:
                continue
        raise VideoProxyError(
            HTTP_403_FORBIDDEN,
            "registered source no longer matches requested hash",
            code="UNVALIDATED_SOURCE",
        )


class G1AuditVideoProxy:
    def __init__(self, cache_root: str | Path, manager: AuditVideoProxyManager | None = None):
        self.manager = manager or G1AuditVideoProxyManager(cache_root=cache_root)

    def register_video(self, source: str | Path, *, run_id: str, episode_id: str) -> ProxyIdentity:
        path = Path(source)
        digest = sha256_file(path)
        probe = self.manager.probe(path)
        ident = ProxyIdentity(
            source_sha256=digest,
            proxy_profile_version=PROXY_PROFILE_VERSION,
            source_path=path,
            source_codec=probe.codec_name or probe.codec_tag or "UNKNOWN",
            source_size=path.stat().st_size,
            needs_proxy=classify_needs_proxy(probe.codec_name, probe.codec_tag),
            proxy_url=stable_proxy_url(digest),
            proxy_path=self.manager.proxy_path(digest),
        )
        self.manager._record_allowed(ident, run_id, episode_id, "video")
        return ident

    def ensure_proxy_file(self, source_sha256: str, profile_file: str) -> Path:
        return self.manager.ensure_proxy_file(source_sha256, profile_file)
