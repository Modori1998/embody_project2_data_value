"""G1 Audit Web FastAPI application, including Phase 6 Calibration Export."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from project2_g1.paths import PROJECT2_ROOT, ensure_project1_on_path

from .contract import CONTRACT_VERSION
from .calibration_export import (
    ExportBlocked,
    ExportValidationError,
    HumanCalibrationExportService,
    resolve_export_role,
)
from .media import g1_media_file_response, resolve_g1_media_file
from .registry import default_owner_db_path, default_registry_path
from .reviews import (
    BOUNDARY_DECISIONS,
    DEFAULT_REVIEWER,
    MISALIGNED_REASONS,
    MISSED_REASONS,
    REDUNDANT_REASONS,
    SIGNAL_DECISIONS,
    SIGNAL_NAMES,
    ReviewStore,
    ValidationFailed,
    build_episode_review_state,
    parse_form,
    predicted_frames,
)
from .service import G1AuditWebInput, InvalidAuditRunError, OwnerPathError
from .video_proxy import G1AuditVideoProxy
from .view import (
    QUEUE_FILTERS,
    AuditViewError,
    boundary_ids_by_episode,
    build_episode_view,
    decode_episode_id,
    encode_episode_id,
    filter_episodes,
    index_run_rows,
    quality_groups,
    run_header,
)
from .vocab import (
    PRIVILEGED_SUBPLOT_HINT,
    display_code,
    dropdown_option_label,
    signal_audit_question,
    signal_review_guide,
    ui_term,
)

ensure_project1_on_path()
from project1_benchmark.m07_audit_web_media import MediaAccessError  # noqa: E402
from project1_benchmark.m07_audit_web_video_proxy import (  # noqa: E402
    FFMPEG_RUNTIME_MISSING,
    VIDEO_PROXY_GENERATION_FAILED,
    VideoProxyError,
)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    templates.env.globals["ui_term"] = ui_term
    templates.env.globals["dropdown_option_label"] = dropdown_option_label
    templates.env.globals["display_code"] = display_code
    templates.env.globals["signal_audit_question"] = signal_audit_question
    templates.env.globals["signal_review_guide"] = signal_review_guide
    templates.env.globals["PRIVILEGED_SUBPLOT_HINT"] = PRIVILEGED_SUBPLOT_HINT
    templates.env.globals["encode_episode_id"] = encode_episode_id
    return templates


def _query_value(request: Request, name: str, default: str = "") -> str:
    return str(request.query_params.get(name) or default)


def create_app(
    *,
    project_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    owner_db_path: str | Path | None = None,
    proxy_cache_root: str | Path | None = None,
    web_input: G1AuditWebInput | None = None,
    video_proxy: G1AuditVideoProxy | None = None,
    reviewer: str = DEFAULT_REVIEWER,
    review_store: ReviewStore | None = None,
) -> FastAPI:
    root = Path(project_root or PROJECT2_ROOT).resolve()
    service = web_input or G1AuditWebInput(
        project_root=root,
        registry_path=registry_path or default_registry_path(root),
        owner_db_path=owner_db_path or default_owner_db_path(root),
    )
    cache = Path(proxy_cache_root or (Path(service.owner_db_path).parent / "video_proxy_cache"))
    proxy = video_proxy or G1AuditVideoProxy(cache)
    reviews = review_store or ReviewStore(service.owner_db_path, reviewer=reviewer)
    exporter = HumanCalibrationExportService(
        project_root=root,
        owner_db_path=reviews.sqlite_path,
    )
    templates = _templates()
    app = FastAPI(title="Project 2 G1 Audit Web", docs_url=None, redoc_url=None)
    app.state.web_input = service
    app.state.video_proxy = proxy
    app.state.review_store = reviews
    app.state.calibration_exporter = exporter

    def render(name: str, request: Request, status_code: int = 200, **context: Any) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name=name,
            context=context,
            status_code=status_code,
        )

    def filter_kwargs(request: Request) -> dict[str, str]:
        return {
            "filter_name": _query_value(request, "filter", "ALL"),
            "quality_group": _query_value(request, "quality_group"),
            "episode_query": _query_value(request, "episode_id"),
            "short_segment_count": _query_value(request, "short_segment_count"),
            "final_boundary_count": _query_value(request, "final_boundary_count"),
        }

    def keep_query(request: Request) -> str:
        parts = []
        for key in ("filter", "quality_group", "episode_id", "short_segment_count", "final_boundary_count"):
            value = _query_value(request, key)
            if value:
                parts.append(f"{key}={quote(value, safe='')}")
        return ("?" + "&".join(parts)) if parts else ""

    def bind_media(run_id: str, view) -> None:
        for item in view.media:
            if item.key != "video" or not item.present:
                continue
            ident = proxy.register_video(view.episode.video_path, run_id=run_id, episode_id=view.episode.episode_id)
            item.source_sha256 = ident.source_sha256
            item.needs_proxy = ident.needs_proxy
            item.proxy_profile_version = ident.proxy_profile_version
            if ident.needs_proxy:
                item.url = ident.proxy_url

    def run_progress(loaded: dict[str, Any]) -> dict[str, Any]:
        meta = loaded["run_meta"]
        return reviews.progress_for_run(
            run_id=str(loaded["run_id"]),
            signal_contract_hash=str(meta["signal_contract_hash"]),
            signal_contract_version=str(meta["signal_contract_version"]),
            boundary_ids_by_episode=boundary_ids_by_episode(loaded["episodes"]),
            current_run_id=str(loaded["run_id"]),
        )

    def review_page_context(
        request: Request,
        loaded: dict[str, Any],
        view,
        queue,
        kwargs: dict[str, str],
        *,
        overlay: dict[str, Any] | None = None,
        review_error: str = "",
        review_notice: str = "",
        active_tab: str = "p1",
    ) -> dict[str, Any]:
        meta = loaded["run_meta"]
        state = build_episode_review_state(
            reviews,
            run_id=str(loaded["run_id"]),
            episode_id=view.episode.episode_id,
            signal_contract_version=str(meta["signal_contract_version"]),
            signal_contract_hash=str(meta["signal_contract_hash"]),
            boundary_rows=view.boundaries,
            overlay=overlay,
            candidate_rows=view.candidates,
            final_member_semantics=str(loaded.get("final_member_semantics") or ""),
        )
        export_assessment = exporter.assess(loaded)
        return {
            "header": run_header(loaded),
            "final_member_semantics": str(loaded.get("final_member_semantics") or ""),
            "queue": queue,
            "view": view,
            "filters": QUEUE_FILTERS,
            "filter_name": kwargs["filter_name"],
            "quality_group": kwargs["quality_group"],
            "episode_query": kwargs["episode_query"],
            "short_segment_count": kwargs["short_segment_count"],
            "final_boundary_count": kwargs["final_boundary_count"],
            "quality_options": quality_groups(loaded["episodes"]),
            "query_suffix": keep_query(request),
            "review": state,
            "signal_decisions": SIGNAL_DECISIONS,
            "boundary_decisions": BOUNDARY_DECISIONS,
            "redundant_reasons": REDUNDANT_REASONS,
            "misaligned_reasons": MISALIGNED_REASONS,
            "missed_reasons": MISSED_REASONS,
            "signal_names": SIGNAL_NAMES,
            "review_error": review_error,
            "review_notice": review_notice,
            "active_tab": active_tab,
            "reviewer": reviews.reviewer,
            "export_assessment": export_assessment,
            "existing_exports": exporter.list_exports(source_run_id=str(loaded["run_id"])),
            "export_notice": _query_value(request, "exported"),
        }

    def load_episode_page(request: Request, run_id: str, episode_id: str):
        loaded = service.load_validated_run(unquote(run_id))
        kwargs = filter_kwargs(request)
        progress = run_progress(loaded)
        queue, view = build_episode_view(
            loaded,
            episode_id=decode_episode_id(unquote(episode_id)),
            progress_by_episode=progress,
            **kwargs,
        )
        bind_media(loaded["run_id"], view)
        return loaded, kwargs, queue, view

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        enabled = index_run_rows(service.list_effective_runs(include_disabled=False))
        disabled = index_run_rows(
            item
            for item in service.list_effective_runs(include_disabled=True)
            if not item.enabled
        )
        return render(
            "index.html",
            request,
            enabled_runs=enabled,
            disabled_runs=disabled,
            contract_version=CONTRACT_VERSION,
        )

    @app.get("/audit/{run_id}", response_model=None)
    def open_run(request: Request, run_id: str):
        try:
            loaded = service.load_validated_run(unquote(run_id))
            kwargs = filter_kwargs(request)
            progress = run_progress(loaded)
            queue = filter_episodes(
                loaded["episodes"],
                filter_name=kwargs["filter_name"],
                quality_group=kwargs["quality_group"],
                episode_id=kwargs["episode_query"],
                short_segment_count=kwargs["short_segment_count"],
                final_boundary_count=kwargs["final_boundary_count"],
                progress_by_episode=progress,
            )
        except AuditViewError as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="Invalid filter", errors=[str(exc)])
        except InvalidAuditRunError as exc:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="VALIDATION_FAILED",
                errors=exc.errors,
                run_id=exc.run_id,
            )
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return render("error.html", request, status, title="Run not available", errors=[str(exc)])
        if not loaded["episodes"]:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="EMPTY_RUN",
                errors=["run has no episodes"],
                run_id=unquote(run_id),
            )
        first = queue[0] if queue else loaded["episodes"][0]
        target = "/audit/{}/episode/{}{}".format(
            quote(loaded["run_id"], safe=""),
            encode_episode_id(first.episode_id),
            keep_query(request) or "?filter=ALL",
        )
        return RedirectResponse(url=target, status_code=303)

    @app.get("/audit/{run_id}/episode/{episode_id}", response_class=HTMLResponse)
    def audit_episode(request: Request, run_id: str, episode_id: str) -> HTMLResponse:
        try:
            loaded, kwargs, queue, view = load_episode_page(request, run_id, episode_id)
        except AuditViewError as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="Invalid episode", errors=[str(exc)])
        except InvalidAuditRunError as exc:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="VALIDATION_FAILED",
                errors=exc.errors,
                run_id=exc.run_id,
            )
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return render("error.html", request, status, title="Run not available", errors=[str(exc)])
        except (MediaAccessError, VideoProxyError) as exc:
            title = getattr(exc, "code", None) or "MEDIA_ERROR"
            if title == FFMPEG_RUNTIME_MISSING:
                title = FFMPEG_RUNTIME_MISSING
            return render("error.html", request, HTTP_400_BAD_REQUEST, title=str(title), errors=[str(exc)])
        notice = _query_value(request, "saved")
        return render(
            "audit.html",
            request,
            **review_page_context(
                request,
                loaded,
                view,
                queue,
                kwargs,
                review_notice="Review saved." if notice == "1" else "",
                active_tab=_query_value(request, "tab", "p1") or "p1",
            ),
        )

    @app.post("/audit/{run_id}/episode/{episode_id}/review", response_model=None)
    async def save_review(request: Request, run_id: str, episode_id: str):
        form = await request.form()
        payload = parse_form(form)
        active_tab = str(form.get("active_tab") or "p1")
        try:
            loaded, kwargs, queue, view = load_episode_page(request, run_id, episode_id)
            meta = loaded["run_meta"]
            frames = predicted_frames(view.boundaries)
            reviews.save_episode(
                run_id=str(loaded["run_id"]),
                episode_id=view.episode.episode_id,
                signal_contract_version=str(meta["signal_contract_version"]),
                signal_contract_hash=str(meta["signal_contract_hash"]),
                episode_length=int(view.episode.length),
                predicted=frames,
                signals=payload["signals"],
                boundaries=payload["boundaries"],
                added=payload["added"],
                episode_note=payload["episode_note"],
            )
        except ValidationFailed as exc:
            try:
                loaded, kwargs, queue, view = load_episode_page(request, run_id, episode_id)
            except Exception as inner:
                return render(
                    "error.html",
                    request,
                    HTTP_400_BAD_REQUEST,
                    title="VALIDATION_FAILED",
                    errors=exc.errors + [str(inner)],
                )
            return render(
                "audit.html",
                request,
                HTTP_400_BAD_REQUEST,
                **review_page_context(
                    request,
                    loaded,
                    view,
                    queue,
                    kwargs,
                    overlay=payload,
                    review_error="VALIDATION_FAILED: " + " | ".join(exc.errors),
                    active_tab=active_tab,
                ),
            )
        except AuditViewError as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="Invalid episode", errors=[str(exc)])
        except InvalidAuditRunError as exc:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="VALIDATION_FAILED",
                errors=exc.errors,
                run_id=exc.run_id,
            )
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return render("error.html", request, status, title="Run not available", errors=[str(exc)])
        except (MediaAccessError, VideoProxyError) as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="MEDIA_ERROR", errors=[str(exc)])
        suffix = keep_query(request)
        if payload["action"] == "save_next" and view.next_episode_id:
            target = "/audit/{}/episode/{}{}".format(
                quote(loaded["run_id"], safe=""),
                encode_episode_id(view.next_episode_id),
                suffix,
            )
            return RedirectResponse(url=target, status_code=303)
        joiner = "&" if suffix else "?"
        target = "/audit/{}/episode/{}{}{}saved=1&tab={}".format(
            quote(loaded["run_id"], safe=""),
            encode_episode_id(view.episode.episode_id),
            suffix,
            joiner,
            quote(active_tab, safe=""),
        )
        return RedirectResponse(url=target, status_code=303)

    @app.post("/audit/{run_id}/episode/{episode_id}/export", response_model=None)
    def create_calibration_export(request: Request, run_id: str, episode_id: str):
        try:
            loaded = service.load_validated_run(unquote(run_id))
            wanted = decode_episode_id(unquote(episode_id))
            if wanted not in loaded["episodes_by_id"]:
                raise AuditViewError(f"unknown episode_id: {wanted}")
            intended_role = resolve_export_role(loaded)
            if intended_role is None:
                raise ExportBlocked(["source identity is not eligible for Human Calibration Export"])
            result = exporter.create_export(loaded, intended_role=intended_role)
        except (ExportBlocked, ExportValidationError) as exc:
            errors = getattr(exc, "errors", [str(exc)])
            return render(
                "error.html", request, HTTP_400_BAD_REQUEST,
                title="EXPORT_BLOCKED", errors=errors, run_id=unquote(run_id),
            )
        except AuditViewError as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="Invalid episode", errors=[str(exc)])
        except InvalidAuditRunError as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="VALIDATION_FAILED", errors=exc.errors, run_id=exc.run_id)
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return render("error.html", request, status, title="Run not available", errors=[str(exc)])
        target = "/audit/{}/episode/{}?exported={}&tab=p1".format(
            quote(str(loaded["run_id"]), safe=""),
            encode_episode_id(wanted),
            quote(str(result["export_id"]), safe=""),
        )
        return RedirectResponse(url=target, status_code=303)

    @app.get("/media/{run_id}/{episode_id}/{media_key}", response_model=None)
    def media(request: Request, run_id: str, episode_id: str, media_key: str) -> Response:
        try:
            loaded = service.load_validated_run(unquote(run_id))
            wanted = decode_episode_id(unquote(episode_id))
            episode = loaded["episodes_by_id"].get(wanted)
            if episode is None:
                raise MediaAccessError(HTTP_404_NOT_FOUND, f"unknown episode_id: {wanted}")
            path = resolve_g1_media_file(loaded["run_root"], episode, unquote(media_key))
            return g1_media_file_response(path, request)
        except InvalidAuditRunError as exc:
            return Response("VALIDATION_FAILED: " + " | ".join(exc.errors), status_code=HTTP_400_BAD_REQUEST)
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return Response(str(exc), status_code=status)
        except MediaAccessError as exc:
            return Response(str(exc), status_code=exc.status_code)

    @app.get("/proxy/video/{source_sha256}/{profile_file}", response_model=None)
    def proxy_video(request: Request, source_sha256: str, profile_file: str) -> Response:
        try:
            path = proxy.ensure_proxy_file(unquote(source_sha256), unquote(profile_file))
            return g1_media_file_response(path, request)
        except VideoProxyError as exc:
            body = f"{exc.code}: {exc}"
            if exc.code == VIDEO_PROXY_GENERATION_FAILED:
                body = VIDEO_PROXY_GENERATION_FAILED + ": " + str(exc)
            return Response(body, status_code=exc.status_code)
        except OSError as exc:
            return Response(f"VIDEO_PROXY_ERROR: {exc}", status_code=HTTP_400_BAD_REQUEST)
        except MediaAccessError as exc:
            return Response(str(exc), status_code=exc.status_code)

    app.mount("/static", StaticFiles(directory=str(TEMPLATE_DIR)), name="static")
    return app
