/**
 * @file dashboard.js
 * Lógica do cliente web para o Dashboard de Risco e Simulador AegisGate.
 * Utiliza Vanilla JavaScript (ES6+), Fetch API e Chart.js local.
 */

// Instâncias globais de gráficos para atualização dinâmica
let statusChartInstance = null;
let reasonsChartInstance = null;
let currentReviewTransactionId = null;

// -----------------------------------------------------------------
// Inicialização no carregamento da página
// -----------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initLiveClock();
  fetchMetrics();
  fetchTransactions();

  // Listeners de filtro e atualização
  const statusFilter = document.getElementById("status-filter");
  if (statusFilter) {
    statusFilter.addEventListener("change", (e) => {
      fetchTransactions(e.target.value);
    });
  }

  const btnRefresh = document.getElementById("btn-refresh-tx");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      fetchMetrics();
      fetchTransactions(statusFilter ? statusFilter.value : "");
    });
  }

  // Listener de abertura do modal de simulação
  const btnOpenSim = document.getElementById("btn-open-simulator");
  const modalSim = document.getElementById("modal-simulator");
  const btnCloseSim = document.getElementById("btn-close-simulator");

  if (btnOpenSim && modalSim) {
    btnOpenSim.addEventListener("click", () => {
      modalSim.classList.add("active");
    });
  }

  if (btnCloseSim && modalSim) {
    btnCloseSim.addEventListener("click", () => {
      modalSim.classList.remove("active");
    });
  }

  // Listener do modal de deliberação manual
  const modalReview = document.getElementById("modal-review");
  const btnCloseReview = document.getElementById("btn-close-review");
  const btnCancelReview = document.getElementById("btn-cancel-review");

  if (btnCloseReview && modalReview) {
    btnCloseReview.addEventListener("click", () => modalReview.classList.remove("active"));
  }
  if (btnCancelReview && modalReview) {
    btnCancelReview.addEventListener("click", () => modalReview.classList.remove("active"));
  }
});

// -----------------------------------------------------------------
// Relógio UTC em tempo real
// -----------------------------------------------------------------
function initLiveClock() {
  const clockEl = document.getElementById("live-clock");
  if (!clockEl) return;
  const update = () => {
    const now = new Date();
    clockEl.textContent = now.toUTCString().replace("GMT", "UTC");
  };
  update();
  setInterval(update, 1000);
}

// -----------------------------------------------------------------
// 1. Consulta e Renderização de Métricas
// -----------------------------------------------------------------
async function fetchMetrics() {
  try {
    const res = await fetch("/api/v1/dashboard/metrics");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Atualiza os Cards de KPIs
    document.getElementById("kpi-total-amount").textContent = 
      new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(data.total_amount);
    
    document.getElementById("kpi-total-tx").textContent = data.total_transactions;
    document.getElementById("kpi-approval-rate").textContent = `${data.approval_rate}%`;
    document.getElementById("kpi-blocked-rate").textContent = `${data.blocked_rate}%`;
    document.getElementById("kpi-avg-score").textContent = data.average_risk_score;

    // Renderiza / Atualiza Gráficos
    renderStatusChart(data.approved_count, data.review_count, data.blocked_count);
    renderReasonsChart(data.top_reasons);
  } catch (err) {
    console.error("Erro ao carregar métricas do dashboard:", err);
  }
}

// -----------------------------------------------------------------
// 2. Gráficos com Chart.js (Dark Mode)
// -----------------------------------------------------------------
function renderStatusChart(approved, review, blocked) {
  const canvas = document.getElementById("chart-status");
  if (!canvas || typeof Chart === "undefined") return;

  const chartData = {
    labels: ["Aprovado", "Em Revisão", "Bloqueado"],
    datasets: [
      {
        data: [approved, review, blocked],
        backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
        borderColor: "#111827",
        borderWidth: 2,
        hoverOffset: 6,
      },
    ],
  };

  if (statusChartInstance) {
    statusChartInstance.data = chartData;
    statusChartInstance.update();
  } else {
    statusChartInstance = new Chart(canvas, {
      type: "doughnut",
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#9ca3af", font: { family: "Inter", size: 12 }, padding: 16 },
          },
        },
        cutout: "68%",
      },
    });
  }
}

function renderReasonsChart(topReasons) {
  const canvas = document.getElementById("chart-reasons");
  if (!canvas || typeof Chart === "undefined") return;

  const labels = Object.keys(topReasons || {});
  const values = Object.values(topReasons || {});

  const chartData = {
    labels: labels.length ? labels : ["Nenhuma anomalia"],
    datasets: [
      {
        label: "Detecções",
        data: values.length ? values : [0],
        backgroundColor: "rgba(99, 102, 241, 0.6)",
        borderColor: "#818cf8",
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  };

  if (reasonsChartInstance) {
    reasonsChartInstance.data = chartData;
    reasonsChartInstance.update();
  } else {
    reasonsChartInstance = new Chart(canvas, {
      type: "bar",
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: {
            ticks: { color: "#9ca3af", font: { size: 10 } },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
          },
          y: {
            ticks: { color: "#9ca3af", stepSize: 1 },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            beginAtZero: true,
          },
        },
      },
    });
  }
}

// -----------------------------------------------------------------
// 3. Consulta de Transações Recentes
// -----------------------------------------------------------------
async function fetchTransactions(statusFilter = "") {
  const tbody = document.getElementById("transactions-tbody");
  if (!tbody) return;

  try {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 2rem;">Carregando dados...</td></tr>`;

    let url = `/api/v1/dashboard/transactions?limit=15&offset=0`;
    if (statusFilter) {
      url += `&status=${encodeURIComponent(statusFilter)}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.transactions || data.transactions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 2rem;">Nenhuma transação encontrada. Clique em "Simular Checkout" para testar!</td></tr>`;
      return;
    }

    tbody.innerHTML = data.transactions
      .map((tx) => {
        let scoreClass = "score-low";
        if (tx.risk_score >= 85) scoreClass = "score-high";
        else if (tx.risk_score >= 60) scoreClass = "score-medium";

        const reasonsHtml = tx.reasons.length
          ? tx.reasons.map((r) => `<span class="reason-tag">${r}</span>`).join("")
          : `<span style="color: var(--text-muted); font-size: 0.75rem;">Nenhuma anomalia</span>`;

        const statusClass = tx.status.replace(" ", "-");

        const actionHtml =
          tx.status === "Em Revisão"
            ? `<button class="btn-action-review" onclick="openReviewModal('${tx.id}', '${tx.risk_score}')">Revisar</button>`
            : `<span style="font-size:0.75rem; color:var(--text-muted);">-</span>`;

        const formattedDate = new Date(tx.created_at).toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        return `
          <tr>
            <td><span class="tx-id-badge">${tx.id.substring(0, 14)}...</span></td>
            <td style="font-weight: 600; color: #fff;">
              R$ ${tx.amount.toFixed(2)}
            </td>
            <td>
              <div style="color: var(--text-primary);">${tx.customer_name_masked}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">${tx.customer_cpf_masked}</div>
            </td>
            <td>
              <span class="score-pill ${scoreClass}">${tx.risk_score}</span>
            </td>
            <td>
              <span class="status-badge ${statusClass}">${tx.status}</span>
            </td>
            <td>
              <div class="reasons-tags">${reasonsHtml}</div>
            </td>
            <td>${actionHtml}</td>
          </tr>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Erro ao carregar transações:", err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--status-blocked); padding: 2rem;">Falha ao carregar transações.</td></tr>`;
  }
}

// -----------------------------------------------------------------
// 4. Simulador de Checkout (1-Click Presets)
// -----------------------------------------------------------------
async function runSimulation(scenario) {
  const resultPanel = document.getElementById("sim-result-panel");
  if (!resultPanel) return;

  resultPanel.style.display = "flex";
  resultPanel.innerHTML = `<div style="color: var(--text-secondary); text-align:center; padding: 1rem;">Processando inferência pelo motor de IA...</div>`;

  try {
    const res = await fetch("/api/v1/dashboard/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    let statusColor = "var(--status-approved)";
    if (data.status === "Em Revisão") statusColor = "var(--status-review)";
    if (data.status === "Bloqueado") statusColor = "var(--status-blocked)";

    resultPanel.innerHTML = `
      <div style="font-weight: 600; color: #fff; font-size: 0.95rem; border-bottom: 1px solid var(--border-subtle); padding-bottom: 0.5rem;">
        Resultado da Inferência em Tempo Real
      </div>
      <div class="sim-metric-row">
        <span style="color: var(--text-muted); font-size: 0.85rem;">Status Deliberado:</span>
        <span class="status-badge ${data.status.replace(" ", "-")}">${data.status}</span>
      </div>
      <div class="sim-metric-row">
        <span style="color: var(--text-muted); font-size: 0.85rem;">Score de Risco IA:</span>
        <span style="font-size: 1.1rem; font-weight: 700; color: ${statusColor};">${data.score} / 100</span>
      </div>
      <div class="sim-metric-row">
        <span style="color: var(--text-muted); font-size: 0.85rem;">Comprador (LGPD):</span>
        <span style="font-size: 0.85rem; color: #fff;">${data.customer_name_masked}</span>
      </div>
      <div>
        <span style="color: var(--text-muted); font-size: 0.85rem;">Justificativas (Explicabilidade LGPD):</span>
        <div class="reasons-tags" style="margin-top: 0.4rem;">
          ${
            data.reasons.length
              ? data.reasons.map((r) => `<span class="reason-tag">${r}</span>`).join("")
              : '<span style="color: var(--status-approved); font-size:0.75rem;">Nenhuma regra violada (Aprovado com segurança)</span>'
          }
        </div>
      </div>
    `;

    // Atualiza imediatamente os dados do painel em background
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    console.error("Erro na simulação:", err);
    resultPanel.innerHTML = `<div style="color: var(--status-blocked); padding: 1rem;">Erro ao executar simulação: ${err.message}</div>`;
  }
}

// -----------------------------------------------------------------
// 5. Deliberação Manual de Analista de Risco
// -----------------------------------------------------------------
function openReviewModal(txId, score) {
  currentReviewTransactionId = txId;
  const modal = document.getElementById("modal-review");
  const targetIdEl = document.getElementById("review-tx-id");
  const targetScoreEl = document.getElementById("review-tx-score");

  if (targetIdEl) targetIdEl.textContent = txId;
  if (targetScoreEl) targetScoreEl.textContent = score;
  if (modal) modal.classList.add("active");
}

async function submitManualReview(decision) {
  if (!currentReviewTransactionId) return;

  const noteInput = document.getElementById("review-note");
  const note = noteInput && noteInput.value.trim() ? noteInput.value.trim() : "Deliberação manual realizada pelo analista de fraude.";

  try {
    const res = await fetch(`/api/v1/dashboard/transactions/${currentReviewTransactionId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        new_status: decision,
        analyst_note: note,
      }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || `Erro HTTP ${res.status}`);
    }

    const modal = document.getElementById("modal-review");
    if (modal) modal.classList.remove("active");
    if (noteInput) noteInput.value = "";

    // Atualiza o dashboard
    fetchMetrics();
    fetchTransactions();
  } catch (err) {
    alert(`Falha ao deliberar transação: ${err.message}`);
  }
}
