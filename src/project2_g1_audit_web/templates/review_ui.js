/* P1/P2 review tabs, conditional fields, add-missed. Layout-preserving. */

(function () {
  const form = document.getElementById("review-form");
  if (!form) {
    return;
  }
  const tabInput = document.getElementById("active-tab");
  const unsaved = document.getElementById("unsaved-flag");

  function markUnsaved() {
    if (unsaved) {
      unsaved.classList.remove("hidden");
    }
  }

  function showTab(name) {
    const wanted = name || "p1";
    document.querySelectorAll("#review-tabs [data-tab]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === wanted);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.panel !== wanted);
    });
    const workspace = document.getElementById("audit-workspace");
    if (workspace) {
      workspace.dataset.mode = wanted;
    }
    if (tabInput) {
      tabInput.value = wanted;
    }
  }

  document.querySelectorAll("#review-tabs [data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => showTab(btn.dataset.tab));
  });
  showTab((tabInput && tabInput.value) || "p1");

  function syncBoundaryCard(card) {
    const select = card.querySelector("[data-bound-decision]");
    if (!select) {
      return;
    }
    const decision = select.value;
    card.dataset.decision = decision;
    const showReason = decision === "REDUNDANT" || decision === "MISALIGNED";
    card.querySelectorAll(".cond-reason").forEach((el) => el.classList.toggle("hidden", !showReason));
    card.querySelectorAll(".cond-frame").forEach((el) => el.classList.toggle("hidden", decision !== "MISALIGNED"));
    const reason = card.querySelector("[data-reason-for]");
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
  }

  document.querySelectorAll(".review-card").forEach((card) => {
    syncBoundaryCard(card);
    const select = card.querySelector("[data-bound-decision]");
    if (select) {
      select.addEventListener("change", () => {
        syncBoundaryCard(card);
        markUnsaved();
      });
    }
  });

  document.querySelectorAll("[data-signal-decision]").forEach((select) => {
    const row = select.closest(".signal-row");
    const paint = () => {
      if (row) {
        row.classList.toggle("needs-comment", select.value === "FAIL" || select.value === "UNCERTAIN");
      }
    };
    paint();
    select.addEventListener("change", () => {
      paint();
      markUnsaved();
    });
  });

  const missedList = document.getElementById("missed-list");
  const missedTpl = document.getElementById("missed-template");
  const addBtn = document.getElementById("btn-add-missed");
  if (missedList && missedTpl && addBtn) {
    addBtn.addEventListener("click", () => {
      const index = missedList.querySelectorAll(".missed-row").length;
      const node = missedTpl.content.cloneNode(true);
      const article = node.querySelector(".missed-row");
      article.querySelector("strong").textContent = "HUMAN_ADD_new";
      article.querySelectorAll("[data-name]").forEach((el) => {
        el.name = "missed_" + index + "_" + el.dataset.name;
      });
      missedList.appendChild(node);
      markUnsaved();
    });
  }

  form.addEventListener("input", markUnsaved);
  form.addEventListener("change", markUnsaved);
})();
