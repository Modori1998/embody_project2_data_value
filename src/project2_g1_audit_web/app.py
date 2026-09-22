"""G1 Audit Web FastAPI application, including Phase 6 Calibration Export."""

from __future__ import annotations

import os
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
from .scoring_view import (
    ScoringUnavailable,
    build_episode_comparison,
    build_run_overview,
    load_bundle,
)
from .service import G1AuditWebInput, InvalidAuditRunError, OwnerPathError
from .unblinded import (
    C12_EXPLANATION_ZH,
    P12_EXPLANATION_ZH,
    UNBLIND_SOURCE_RELPATH,
    UNBLINDED_REVIEWER,
    UnblindedError,
    UnblindedNotApplicable,
    build_unblinded_join,
)
from .video_proxy import G1AuditVideoProxy
from .input import load_csv_rows
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

#: Kill switch for the owner-only unblinded review mode. The unblinded route is
#: additionally gated on ``run_stage == DESIGN_DIAGNOSTIC`` and on a strict
#: 20/20 join against the frozen internal selection table.
UNBLINDED_ENV_FLAG = "G1_AUDIT_WEB_UNBLINDED_OWNER_REVIEW"

#: Re-review labels offered in the unblinded mode. NOT_REVIEWED is deliberately
#: excluded: this mode exists to re-decide, not to erase a decision.
UNBLINDED_DECISIONS = tuple(item for item in BOUNDARY_DECISIONS if item != "NOT_REVIEWED")


def unblinded_owner_review_enabled(explicit: bool | None = None) -> bool:
    """Owner-only unblinded mode. On by default for the local owner web."""

    if explicit is not None:
        return bool(explicit)
    raw = os.environ.get(UNBLINDED_ENV_FLAG, "1")
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


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
    unblinded_review_store: ReviewStore | None = None,
    unblinded_owner_review: bool | None = None,
    unblind_source_path: str | Path | None = None,
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
    # Same append-only SSOT, distinct reviewer identity: provenance of every
    # boundary revision stays derivable without a schema change.
    unblinded_reviews = unblinded_review_store or ReviewStore(
        reviews.sqlite_path, reviewer=UNBLINDED_REVIEWER
    )
    unblinded_enabled = unblinded_owner_review_enabled(unblinded_owner_review)
    unblind_source = Path(unblind_source_path or (root / UNBLIND_SOURCE_RELPATH))
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

    # ------------------------------------------------------------------
    # Owner-only unblinded review mode (additive; DESIGN_DIAGNOSTIC only)
    # ------------------------------------------------------------------

    def unblinded_gate(request: Request, run_id: str):
        """Return an error response when the unblinded mode must not open."""

        if not unblinded_enabled:
            return render(
                "error.html",
                request,
                HTTP_403_FORBIDDEN,
                title="UNBLINDED_DISABLED",
                errors=[
                    f"owner unblinded review is disabled (set {UNBLINDED_ENV_FLAG}=1 to enable)"
                ],
                run_id=unquote(run_id),
            )
        return None

    def load_unblinded(request: Request, run_id: str):
        """Resolve the strict join, or an error response to render instead."""

        try:
            loaded = service.load_validated_run(unquote(run_id))
            join = build_unblinded_join(
                loaded=loaded,
                source_path=unblind_source,
                boundary_history=unblinded_reviews.boundary_history_for_run(
                    run_id=str(loaded["run_id"])
                ),
            )
        except UnblindedNotApplicable as exc:
            return None, None, render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="UNBLINDED_NOT_APPLICABLE",
                errors=exc.errors,
                run_id=unquote(run_id),
            )
        except UnblindedError as exc:
            return None, None, render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="UNBLINDED_JOIN_FAILED",
                errors=exc.errors,
                run_id=unquote(run_id),
            )
        except InvalidAuditRunError as exc:
            return None, None, render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="VALIDATION_FAILED",
                errors=exc.errors,
                run_id=exc.run_id,
            )
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return None, None, render(
                "error.html", request, status, title="Run not available", errors=[str(exc)]
            )
        return loaded, join, None

    def load_unblinded_view(loaded: dict[str, Any], event):
        """Build the episode view (media + frame axis) for an unblinded event.

        The unblinded page describes exactly the same episode, over exactly the
        same frame axis, as the blind page. Both therefore go through
        ``build_episode_view``; only the surrounding chrome differs. Media is
        bound here so the video proxy is registered for the owner as well.
        """

        _, view = build_episode_view(loaded, episode_id=event.episode_id)
        bind_media(str(loaded["run_id"]), view)
        return view

    def unblinded_page_context(
        loaded: dict[str, Any],
        join,
        event,
        *,
        view=None,
        review_error: str = "",
        review_notice: str = "",
    ) -> dict[str, Any]:
        previous_event, next_event = join.neighbour(event.episode_id)
        counterpart = next(
            (
                item
                for item in join.events
                if item.pair_id == event.pair_id and item.episode_id != event.episode_id
            ),
            None,
        )
        return {
            "header": run_header(loaded),
            "join": join,
            "event": event,
            "view": view,
            "focus_frame": event.event_frame,
            "counterpart": counterpart,
            "previous_event": previous_event,
            "next_event": next_event,
            "event_index": join.index_of(event.episode_id) + 1,
            "current_corrected_frame": event.current_corrected_frame,
            "boundary_decisions": UNBLINDED_DECISIONS,
            "redundant_reasons": REDUNDANT_REASONS,
            "misaligned_reasons": MISALIGNED_REASONS,
            "c12_explanation_zh": C12_EXPLANATION_ZH,
            "p12_explanation_zh": P12_EXPLANATION_ZH,
            "review_error": review_error,
            "review_notice": review_notice,
        }

    @app.get("/audit/{run_id}/unblinded", response_model=None)
    def open_unblinded(request: Request, run_id: str):
        gated = unblinded_gate(request, run_id)
        if gated is not None:
            return gated
        loaded, join, failure = load_unblinded(request, run_id)
        if failure is not None:
            return failure
        if not join.events:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="EMPTY_UNBLINDED_JOIN",
                errors=["no diagnostic events joined"],
                run_id=unquote(run_id),
            )
        first = join.events[0]
        target = "/audit/{}/unblinded/episode/{}".format(
            quote(str(loaded["run_id"]), safe=""), encode_episode_id(first.episode_id)
        )
        return RedirectResponse(url=target, status_code=303)

    @app.get("/audit/{run_id}/unblinded/episode/{episode_id}", response_class=HTMLResponse)
    def unblinded_episode(request: Request, run_id: str, episode_id: str) -> HTMLResponse:
        gated = unblinded_gate(request, run_id)
        if gated is not None:
            return gated
        loaded, join, failure = load_unblinded(request, run_id)
        if failure is not None:
            return failure
        wanted = decode_episode_id(unquote(episode_id))
        event = join.event(wanted)
        if event is None:
            return render(
                "error.html",
                request,
                HTTP_404_NOT_FOUND,
                title="UNKNOWN_UNBLINDED_EVENT",
                errors=[f"episode_id is not one of the joined diagnostic events: {wanted}"],
                run_id=unquote(run_id),
            )
        notice = _query_value(request, "saved")
        try:
            view = load_unblinded_view(loaded, event)
        except (AuditViewError, MediaAccessError, VideoProxyError) as exc:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="UNBLINDED_MEDIA_ERROR",
                errors=[str(exc)],
                run_id=unquote(run_id),
            )
        return render(
            "unblinded.html",
            request,
            **unblinded_page_context(
                loaded,
                join,
                event,
                view=view,
                review_notice="Owner unblinded review appended." if notice == "1" else "",
            ),
        )

    @app.get("/audit/{run_id}/unblinded/pair/{pair_id}", response_class=HTMLResponse)
    def unblinded_pair(request: Request, run_id: str, pair_id: str) -> HTMLResponse:
        gated = unblinded_gate(request, run_id)
        if gated is not None:
            return gated
        loaded, join, failure = load_unblinded(request, run_id)
        if failure is not None:
            return failure
        pair = join.pair(unquote(pair_id))
        if pair is None:
            return render(
                "error.html",
                request,
                HTTP_404_NOT_FOUND,
                title="UNKNOWN_MATCHED_PAIR",
                errors=[f"pair_id is not one of the joined pairs: {unquote(pair_id)}"],
                run_id=unquote(run_id),
            )
        index = next(
            (i for i, item in enumerate(join.pairs) if item.pair_id == pair.pair_id), 0
        )
        try:
            view_a = load_unblinded_view(loaded, pair.arm_a)
            view_b = load_unblinded_view(loaded, pair.arm_b)
        except (AuditViewError, MediaAccessError, VideoProxyError) as exc:
            return render(
                "error.html",
                request,
                HTTP_400_BAD_REQUEST,
                title="UNBLINDED_MEDIA_ERROR",
                errors=[str(exc)],
                run_id=unquote(run_id),
            )
        return render(
            "unblinded_pair.html",
            request,
            header=run_header(loaded),
            join=join,
            pair=pair,
            pair_index=index + 1,
            view_a=view_a,
            view_b=view_b,
            previous_pair=join.pairs[index - 1] if index > 0 else None,
            next_pair=join.pairs[index + 1] if index + 1 < len(join.pairs) else None,
        )

    @app.post("/audit/{run_id}/unblinded/episode/{episode_id}/review", response_model=None)
    async def save_unblinded_review(request: Request, run_id: str, episode_id: str):
        gated = unblinded_gate(request, run_id)
        if gated is not None:
            return gated
        form = await request.form()
        loaded, join, failure = load_unblinded(request, run_id)
        if failure is not None:
            return failure
        wanted = decode_episode_id(unquote(episode_id))
        event = join.event(wanted)
        if event is None:
            return render(
                "error.html",
                request,
                HTTP_404_NOT_FOUND,
                title="UNKNOWN_UNBLINDED_EVENT",
                errors=[f"episode_id is not one of the joined diagnostic events: {wanted}"],
                run_id=unquote(run_id),
            )
        episode = loaded["episodes_by_id"][wanted]
        try:
            unblinded_reviews.save_boundary_review(
                run_id=str(loaded["run_id"]),
                episode_id=wanted,
                predicted={event.boundary_id: event.run_boundary_frame},
                boundary_id=event.boundary_id,
                decision=str(form.get("ub_decision") or ""),
                episode_length=int(episode.length),
                reason_code=str(form.get("ub_reason_code") or ""),
                corrected_frame=str(form.get("ub_corrected_frame") or ""),
                comment=str(form.get("ub_comment") or ""),
            )
        except ValidationFailed as exc:
            return render(
                "unblinded.html",
                request,
                HTTP_400_BAD_REQUEST,
                **unblinded_page_context(
                    loaded,
                    join,
                    event,
                    review_error="VALIDATION_FAILED: " + " | ".join(exc.errors),
                ),
            )
        target = "/audit/{}/unblinded/episode/{}?saved=1".format(
            quote(str(loaded["run_id"]), safe=""), encode_episode_id(wanted)
        )
        return RedirectResponse(url=target, status_code=303)

    @app.get("/audit/{run_id}/scoring", response_class=HTMLResponse)
    def scoring_overview(request: Request, run_id: str):
        try:
            loaded = service.load_validated_run(unquote(run_id))
            bundle = load_bundle(service.project_root, str(loaded["run_id"]))
            overview = build_run_overview(bundle, loaded["episodes"])
        except ScoringUnavailable as exc:
            return render(
                "error.html", request, HTTP_400_BAD_REQUEST,
                title="SCORING_UNAVAILABLE", errors=[str(exc)], run_id=unquote(run_id),
            )
        except InvalidAuditRunError as exc:
            return render(
                "error.html", request, HTTP_400_BAD_REQUEST,
                title="VALIDATION_FAILED", errors=exc.errors, run_id=exc.run_id,
            )
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return render("error.html", request, status, title="Run not available", errors=[str(exc)])
        return render(
            "scoring.html",
            request,
            header=run_header(loaded),
            overview=overview,
        )

    @app.get("/audit/{run_id}/scoring/{episode_id}", response_class=HTMLResponse)
    def scoring_episode(request: Request, run_id: str, episode_id: str):
        try:
            loaded = service.load_validated_run(unquote(run_id))
            wanted = decode_episode_id(unquote(episode_id))
            episode = loaded["episodes_by_id"].get(wanted)
            if episode is None:
                raise AuditViewError(f"unknown episode_id: {wanted}")
            bundle = load_bundle(service.project_root, str(loaded["run_id"]))
            boundaries = load_csv_rows(episode.boundaries_path)
            comparison = build_episode_comparison(
                bundle,
                episode_id=wanted,
                boundaries=boundaries,
                length=int(episode.length),
            )
        except ScoringUnavailable as exc:
            return render(
                "error.html", request, HTTP_400_BAD_REQUEST,
                title="SCORING_UNAVAILABLE", errors=[str(exc)], run_id=unquote(run_id),
            )
        except AuditViewError as exc:
            return render("error.html", request, HTTP_400_BAD_REQUEST, title="Invalid episode", errors=[str(exc)])
        except InvalidAuditRunError as exc:
            return render(
                "error.html", request, HTTP_400_BAD_REQUEST,
                title="VALIDATION_FAILED", errors=exc.errors, run_id=exc.run_id,
            )
        except OwnerPathError as exc:
            status = HTTP_403_FORBIDDEN if "DISABLED_BY_OWNER" in str(exc) else HTTP_404_NOT_FOUND
            return render("error.html", request, status, title="Run not available", errors=[str(exc)])
        episode_links = [
            {"episode_id": ep.episode_id, "quality_group": str(getattr(ep, "quality_group", "") or "")}
            for ep in loaded["episodes"]
        ]
        return render(
            "scoring_episode.html",
            request,
            header=run_header(loaded),
            comparison=comparison,
            episode=episode,
            episode_links=episode_links,
            current_episode_id=wanted,
        )

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
