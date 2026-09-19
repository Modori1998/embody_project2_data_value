/* Read-only frame <-> table <-> video sync for G1 Audit Web. */

(function () {
  const strip = document.getElementById("frame-strip");
  if (!strip) {
    return;
  }
  const video = document.querySelector("video");
  const status = document.getElementById("strip-status");
  const playhead = document.getElementById("strip-playhead");
  const fps = Number(strip.dataset.fps || 20) || 20;
  const length = Math.max(Number(strip.dataset.length || 1), 1);
  const span = Math.max(length - 1, 1);

  function tokens(value) {
    return String(value || "")
      .split(/[\s|,]+/)
      .map((item) => item.trim())
      .filter((item) => item && item !== "EPISODE_START" && item !== "EPISODE_END");
  }

  function collectIds(el) {
    const out = [];
    ["id", "candidateId", "boundaryId", "segmentId", "candidateIds", "members"].forEach((key) => {
      out.push.apply(out, tokens(el.dataset[key] || ""));
    });
    return out;
  }

  function seekVideo(frame) {
    if (!video) {
      return;
    }
    const time = Number(frame) / fps;
    const jump = () => {
      video.currentTime = time;
    };
    if (video.readyState >= 1) {
      jump();
      return;
    }
    video.addEventListener("loadedmetadata", jump, { once: true });
    video.load();
  }

  function clampFrame(frame) {
    return Math.max(0, Math.min(span, Math.round(Number(frame) || 0)));
  }

  function setPlayhead(frame) {
    if (!playhead) {
      return;
    }
    playhead.style.left = (100 * Number(frame) / span).toFixed(3) + "%";
  }

  function updateFrameReadout(frame) {
    const safe = clampFrame(frame);
    const cur = document.getElementById("cur-frame");
    const timeEl = document.getElementById("cur-time");
    const jump = document.getElementById("jump-frame");
    if (cur) {
      cur.textContent = String(safe);
    }
    if (timeEl) {
      timeEl.textContent = (safe / fps).toFixed(2);
    }
    if (jump && document.activeElement !== jump) {
      jump.value = String(safe);
    }
  }

  function select(frame, ids) {
    const wanted = new Set(ids || []);
    document.querySelectorAll(".sync-on").forEach((el) => el.classList.remove("sync-on"));
    document.querySelectorAll(".sync-row").forEach((row) => {
      const rowFrame = row.dataset.frame;
      const start = row.dataset.startFrame;
      const end = row.dataset.endFrame;
      const rowIds = collectIds(row);
      const idHit = rowIds.some((id) => wanted.has(id));
      const frameHit = rowFrame !== undefined && String(rowFrame) === String(frame);
      const edgeHit = String(start) === String(frame) || String(end) === String(frame);
      if (idHit || frameHit || edgeHit) {
        row.classList.add("sync-on");
      }
    });
    document.querySelectorAll(".strip-col").forEach((col) => {
      col.classList.toggle("sync-on", String(col.dataset.frame) === String(frame));
    });
    const first = document.querySelector(".sync-row.sync-on");
    if (first) {
      first.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    setPlayhead(frame);
    updateFrameReadout(frame);
    seekVideo(frame);
    if (status) {
      const labels = Array.from(wanted).slice(0, 6).join(", ");
      status.textContent = "frame " + frame + (labels ? " · " + labels : "") + " · " + (frame / fps).toFixed(2) + "s";
    }
  }

  strip.addEventListener("click", (event) => {
    const mark = event.target.closest(".strip-mark");
    const col = event.target.closest(".strip-col");
    if (!col) {
      return;
    }
    const ids = mark ? collectIds(mark) : Array.from(col.querySelectorAll(".strip-mark")).flatMap(collectIds);
    select(col.dataset.frame, ids);
  });

  document.querySelectorAll(".sync-row").forEach((row) => {
    row.addEventListener("click", () => {
      const frame = row.dataset.frame || row.dataset.startFrame || "0";
      select(frame, collectIds(row));
    });
  });

  if (video) {
    video.addEventListener("timeupdate", () => {
      const frame = clampFrame(video.currentTime * fps);
      setPlayhead(frame);
      updateFrameReadout(frame);
    });
  }

  document.querySelectorAll("[data-frame-delta]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const current = Number((document.getElementById("cur-frame") || {}).textContent || 0);
      select(clampFrame(current + Number(btn.dataset.frameDelta || 0)), []);
    });
  });
  const jumpBtn = document.getElementById("btn-jump-frame");
  const jumpInput = document.getElementById("jump-frame");
  if (jumpBtn && jumpInput) {
    const jump = () => select(clampFrame(jumpInput.value), []);
    jumpBtn.addEventListener("click", jump);
    jumpInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        jump();
      }
    });
  }
  updateFrameReadout(0);
})();
