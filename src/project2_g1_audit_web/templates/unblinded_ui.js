/* Owner unblinded review: focus the diagnostic frame + conditional fields.
 *
 * Two independent, self-guarding blocks:
 *   1. episode page  (#unblinded-media)   -- reuses audit_sync.js for the
 *      frame <-> video <-> strip sync, and only adds the initial focus on the
 *      diagnostic boundary frame plus the conditional review fields.
 *   2. matched-pair page (#unblinded-pair-media) -- two side-by-side videos, so
 *      audit_sync.js is deliberately NOT loaded there (it binds the first
 *      <video> and single-id strip anchors). Each arm seeks itself instead.
 *
 * The blind page never loads this file.
 */

(function () {
  // The video elements use preload="none", so metadata is never fetched until
  // something asks for it. Mirrors the proven seek path in audit_sync.js:
  // register the listener, then force video.load().
  function seekWhenReady(video, frame, fps) {
    if (!video) {
      return;
    }
    const jump = () => {
      video.currentTime = frame / fps;
    };
    if (video.readyState >= 1) {
      jump();
      return;
    }
    video.addEventListener("loadedmetadata", jump, { once: true });
    video.load();
  }

  // -- 1. episode page ------------------------------------------------------
  const media = document.getElementById("unblinded-media");
  if (media) {
    const strip = document.getElementById("frame-strip");
    const video = media.querySelector("video");
    const focus = Number(media.dataset.focusFrame || 0);

    // Clicking a strip column is handled by audit_sync.js, which seeks the
    // video, moves the playhead and updates the readout. Reuse that single
    // code path rather than duplicating the seek arithmetic here.
    const focusFrame = () => {
      if (!strip) {
        return;
      }
      const col = strip.querySelector('.strip-col[data-frame="' + focus + '"]');
      if (col) {
        col.click();
        return;
      }
      // Fallback: the focus frame has no marker column (should not happen for a
      // joined diagnostic event, since its boundary is a final boundary).
      seekWhenReady(video, focus, Number(strip.dataset.fps || 20) || 20);
    };

    const focusBtn = document.getElementById("btn-focus-frame");
    if (focusBtn) {
      focusBtn.addEventListener("click", focusFrame);
    }

    // Land on the diagnostic boundary frame: the owner should see the case,
    // not frame 0.
    focusFrame();
  }

  // -- 2. matched-pair page -------------------------------------------------
  const pairRoot = document.getElementById("unblinded-pair-media");
  if (pairRoot) {
    pairRoot.querySelectorAll("[data-pair-arm]").forEach((armEl) => {
      const arm = armEl.dataset.pairArm;
      const video = armEl.querySelector("video");
      const fps = Number(armEl.dataset.fps || 20) || 20;
      const focus = Number(armEl.dataset.focusFrame || 0);
      const cur = document.getElementById("ub-pair-cur-frame-" + arm.toLowerCase());
      const timeEl = document.getElementById("ub-pair-cur-time-" + arm.toLowerCase());

      const paint = (frame) => {
        const safe = Math.max(0, Math.round(frame));
        if (cur) {
          cur.textContent = String(safe);
        }
        if (timeEl) {
          timeEl.textContent = (safe / fps).toFixed(2);
        }
      };

      const seek = () => {
        paint(focus);
        seekWhenReady(video, focus, fps);
      };

      const btn = document.getElementById("btn-pair-focus-" + arm.toLowerCase());
      if (btn) {
        btn.addEventListener("click", seek);
      }
      if (video) {
        video.addEventListener("timeupdate", () => paint(video.currentTime * fps));
      }
      seek();
    });
  }

  // -- conditional reason_code / corrected_frame ----------------------------
  const form = document.getElementById("unblinded-review-form");
  if (!form) {
    return;
  }

  const syncConditionalFields = () => {
    const select = form.querySelector("[data-bound-decision]");
    if (!select) {
      return;
    }
    const decision = select.value;
    form.querySelectorAll(".cond-reason").forEach((el) => {
      el.classList.toggle("hidden", decision !== "REDUNDANT" && decision !== "MISALIGNED");
    });
    form.querySelectorAll(".cond-frame").forEach((el) => {
      el.classList.toggle("hidden", decision !== "MISALIGNED");
    });
    const reason = form.querySelector("[data-reason-for]");
    if (reason) {
      reason.querySelectorAll("option[data-for]").forEach((opt) => {
        const show = opt.dataset.for === decision;
        opt.hidden = !show;
        opt.disabled = !show;
      });
      const chosen = reason.selectedOptions[0];
      if (chosen && chosen.disabled) {
        reason.value = "";
      }
    }
  };

  syncConditionalFields();
  const decision = form.querySelector("[data-bound-decision]");
  if (decision) {
    decision.addEventListener("change", syncConditionalFields);
  }
})();
