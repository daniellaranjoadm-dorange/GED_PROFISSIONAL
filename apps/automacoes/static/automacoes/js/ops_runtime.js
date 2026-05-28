/**
 * OPS Runtime Enterprise Console
 * Live Event Stream, filters, counters, deduplication and timeline grouping.
 */

(function() {
  const feed = document.getElementById("ops-live-feed");
  const statusBadge = document.getElementById("ops-live-status");
  const insightBox = document.getElementById("ops-live-insight");
  const filterButtons = Array.from(document.querySelectorAll(".ops-live-filter"));

  if (!feed) return;

  const endpoint = feed.dataset.endpoint;

  let activeFilter = "ALL";
  let lastEvents = [];

  function escapeHTML(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function normalizeSeverity(status) {
    const value = String(status || "INFO").toUpperCase();

    if (["CRITICAL", "CRÍTICO", "CRITICO", "FATAL"].includes(value)) return "CRITICAL";
    if (["ERRO", "ERROR", "FALHA", "FAILED"].includes(value)) return "ERROR";
    if (["WARNING", "WARN", "ATENÇÃO", "ATENCAO", "ALERTA"].includes(value)) return "WARNING";
    if (["INICIADO", "PROCESSANDO", "RUNNING", "RUN"].includes(value)) return "RUN";
    if (["SUCESSO", "SUCCESS", "OK"].includes(value)) return "OK";

    return "INFO";
  }

  function relativeTime(value) {
    if (!value) return "";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

    if (seconds < 10) return "agora";
    if (seconds < 60) return `há ${seconds}s`;

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `há ${minutes} min`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `há ${hours}h`;

    const days = Math.floor(hours / 24);
    return `há ${days}d`;
  }

  function render(events) {
    if (!Array.isArray(events)) return;

    feed.innerHTML = "";

    events.forEach((evento) => {
      const severity = normalizeSeverity(
        evento.severity ||
        evento.status ||
        evento.level
      );

      const title =
        evento.title ||
        evento.titulo ||
        evento.event ||
        "Evento operacional";

      const message =
        evento.message ||
        evento.description ||
        evento.status ||
        "Runtime ativo";

      const timestamp =
        evento.timestamp ||
        evento.created_at ||
        "";

      const div = document.createElement("div");
      div.className = "ops-live-event";

      div.innerHTML = `
        <div class="ops-live-title">
          ${escapeHTML(title)}
          <span class="ops-live-severity">${severity}</span>
        </div>

        <div class="ops-live-message">
          ${escapeHTML(message)}
        </div>

        <div class="ops-live-time">
          ${relativeTime(timestamp)}
        </div>
      `;

      feed.appendChild(div);
    });
  }

  async function refreshLiveEvents() {
    try {
      const response = await fetch(endpoint, {
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        },
        cache: "no-store"
      });

      const payload = await response.json();

      const events =
        payload.events ||
        payload.data ||
        [];

      render(events);

      if (insightBox) {
        insightBox.innerText =
          payload.insight ||
          "Runtime operacional sem falhas recentes.";
      }

      if (statusBadge) {
        statusBadge.innerText = "Live";
      }

    } catch (error) {
      console.error(error);

      if (statusBadge) {
        statusBadge.innerText = "Offline";
      }
    }
  }

  refreshLiveEvents();

  setInterval(refreshLiveEvents, 10000);

})();


// ==========================================================
// LD PROGRESS RUNTIME UI
// ==========================================================
(function () {
  const panel = document.getElementById("ld-progress-panel");
  if (!panel) return;

  const endpoint = panel.dataset.progressEndpoint;
  if (!endpoint) return;

  const fill = document.getElementById("ld-progress-fill");
  const percent = document.getElementById("ld-progress-percent");
  const step = document.getElementById("ld-progress-step");
  const message = document.getElementById("ld-progress-message");
  const badge = document.getElementById("ld-progress-badge");
  const loadingAlert = document.getElementById("loading-alert");

  function setVisible(visible) {
    panel.classList.toggle("d-none", !visible);
  }

  function updateUI(data) {
    const status = String(data.status || "idle").toLowerCase();
    const pct = Math.max(0, Math.min(100, parseInt(data.percentual || 0, 10)));

    if (fill) fill.style.width = pct + "%";
    if (percent) percent.textContent = pct + "%";
    if (step) step.textContent = data.etapa || "Aguardando execução.";
    if (message) message.textContent = data.mensagem || data.etapa || "Aguardando execução da Atualização LD.";
    if (badge) {
      badge.textContent = status.toUpperCase();
      badge.classList.remove("ops-status-ok", "ops-status-warn", "ops-status-risk");
      if (status === "done") badge.classList.add("ops-status-ok");
      else if (status === "error" || status === "blocked") badge.classList.add("ops-status-risk");
      else if (status === "running") badge.classList.add("ops-status-warn");
    }

    const shouldShow = status === "running" || status === "done" || status === "error" || status === "blocked";
    setVisible(shouldShow);

    if (loadingAlert) {
      loadingAlert.classList.toggle("d-none", status !== "running");
    }
  }

  async function fetchProgress() {
    try {
      const response = await fetch(endpoint, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        cache: "no-store"
      });
      if (!response.ok) return;
      const data = await response.json();
      updateUI(data);
    } catch (error) {
      // Mantém a tela silenciosa para não poluir o console em ambiente de rede instável.
    }
  }

  document.querySelectorAll(".ged-action-form").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (form.dataset.automationName === "Atualização LD") {
        setVisible(true);
        updateUI({
          status: "running",
          percentual: 1,
          etapa: "Atualização LD iniciada.",
          mensagem: "Processamento iniciado. A tela será liberada e o progresso continuará aqui."
        });
      }
    });
  });

  fetchProgress();
  setInterval(fetchProgress, 2000);
})();


// ==========================================================
// AUTOMATION EXECUTION OVERLAY — ENTERPRISE PANEL
// ==========================================================
(function () {
  const overlay = document.getElementById("automation-exec-overlay");
  if (!overlay) return;

  const title = document.getElementById("automation-exec-title");
  const subtitle = document.getElementById("automation-exec-subtitle");
  const fill = document.getElementById("automation-exec-fill");
  const percent = document.getElementById("automation-exec-percent");
  const message = document.getElementById("automation-exec-message");
  const steps = Array.from(document.querySelectorAll(".automation-exec-step"));

  let progressTimer = null;
  let currentProgress = 3;

  function setOverlayVisible(visible) {
    overlay.classList.toggle("is-visible", visible);
    overlay.setAttribute("aria-hidden", visible ? "false" : "true");
  }

  function setProgress(value, text) {
    currentProgress = Math.max(3, Math.min(96, parseInt(value || 3, 10)));

    if (fill) fill.style.width = currentProgress + "%";
    if (percent) percent.textContent = currentProgress + "%";
    if (message && text) message.textContent = text;

    const activeStep =
      currentProgress >= 82 ? 4 :
      currentProgress >= 58 ? 3 :
      currentProgress >= 28 ? 2 : 1;

    steps.forEach((step, index) => {
      const stepNumber = index + 1;
      step.classList.toggle("is-active", stepNumber === activeStep);
      step.classList.toggle("is-done", stepNumber < activeStep);

      const marker = step.querySelector(".automation-exec-spinner, .automation-exec-check");
      if (marker && stepNumber < activeStep) {
        marker.className = "automation-exec-check";
      } else if (marker && stepNumber >= activeStep) {
        marker.className = "automation-exec-spinner";
      }
    });
  }

  function startProgress(automationName) {
    clearInterval(progressTimer);
    currentProgress = 3;
    setProgress(3, "Preparando execução...");

    progressTimer = setInterval(() => {
      let increment = 3;
      if (currentProgress > 35) increment = 2;
      if (currentProgress > 65) increment = 1;
      if (currentProgress > 86) increment = 0;

      if (increment > 0) {
        setProgress(
          currentProgress + increment,
          `${automationName} em execução. Processando dados operacionais...`
        );
      }
    }, 900);
  }

  function showForForm(form) {
    const automationName =
      form.dataset.automationName ||
      form.getAttribute("data-automation-name") ||
      form.querySelector("[data-automation-name]")?.dataset.automationName ||
      "Automação";

    if (title) title.textContent = `Executando ${automationName}`;
    if (subtitle) {
      subtitle.textContent =
        "Mantenha esta janela aberta. O GED está processando a rotina solicitada e atualizará o painel ao finalizar.";
    }

    setOverlayVisible(true);
    startProgress(automationName);
  }

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", function () {
      const submitButton = form.querySelector("button[type='submit']");
      const isAutomationForm =
        form.classList.contains("ged-action-form") ||
        form.closest(".ops-card") ||
        form.closest(".ops-automation-card") ||
        form.dataset.automationName ||
        submitButton;

      if (!isAutomationForm) return;
      showForForm(form);
    });
  });

  window.addEventListener("pageshow", function () {
    clearInterval(progressTimer);
    setOverlayVisible(false);
  });
})();
