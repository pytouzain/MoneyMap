"use strict";

const CATEGORIES = [
  "Groceries", "Dining", "Transport", "Shopping", "Entertainment",
  "Utilities", "Housing", "Health", "Travel", "Income",
  "Fees & Interest", "Transfers", "Other",
];

const els = {
  form: document.getElementById("upload-form"),
  fileInput: document.getElementById("file-input"),
  dropzone: document.getElementById("dropzone"),
  fileName: document.getElementById("file-name"),
  analyzeBtn: document.getElementById("analyze-btn"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  totalSpending: document.getElementById("total-spending"),
  totalCredits: document.getElementById("total-credits"),
  totalCount: document.getElementById("total-count"),
  chart: document.getElementById("chart"),
  tableBody: document.querySelector("#txn-table tbody"),
};

let transactions = [];

const money = (n) =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(n);

// --- file selection ---------------------------------------------------------
function setFile(file) {
  if (!file) return;
  els.fileInput.files = createFileList(file);
  els.fileName.textContent = `Selected: ${file.name}`;
  els.fileName.hidden = false;
  els.analyzeBtn.disabled = false;
}

// Assigning to input.files requires a DataTransfer-backed FileList.
function createFileList(file) {
  const dt = new DataTransfer();
  dt.items.add(file);
  return dt.files;
}

els.fileInput.addEventListener("change", () => setFile(els.fileInput.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  els.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    els.dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((ev) =>
  els.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("dragover");
  })
);
els.dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) setFile(file);
});

// --- submit / analyze -------------------------------------------------------
els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = els.fileInput.files[0];
  if (!file) return;

  showStatus("loading", "Analyzing your statement…");
  els.analyzeBtn.disabled = true;
  els.results.hidden = true;

  try {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/analyze", { method: "POST", body });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong analyzing the file.");
    }
    render(data);
  } catch (err) {
    showStatus("error", err.message);
  } finally {
    els.analyzeBtn.disabled = false;
  }
});

function showStatus(kind, text) {
  els.status.className = `status ${kind}`;
  els.status.textContent = text;
  els.status.hidden = false;
}

// --- render -----------------------------------------------------------------
function render(data) {
  transactions = data.transactions;

  const messages = [];
  if (data.warnings && data.warnings.length) messages.push(...data.warnings);
  if (data.llm_used) messages.push("Some categories were filled in by the AI categorizer.");
  if (messages.length) {
    showStatus("", messages.join(" "));
  } else {
    els.status.hidden = true;
  }

  els.totalSpending.textContent = money(data.total_spending);
  els.totalCredits.textContent = money(data.total_credits);
  els.totalCount.textContent = String(transactions.length);

  renderChart(data.summary);
  renderTable();
  els.results.hidden = false;
}

function renderChart(summary) {
  els.chart.innerHTML = "";
  if (!summary.length) {
    els.chart.innerHTML = '<p class="hint">No spending to chart.</p>';
    return;
  }
  const max = Math.max(...summary.map((s) => s.total));
  for (const s of summary) {
    const row = document.createElement("div");
    row.className = "bar-row";
    const pct = max > 0 ? (s.total / max) * 100 : 0;
    row.innerHTML = `
      <div class="bar-label" title="${escapeHtml(s.category)}">${escapeHtml(s.category)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-value">${money(s.total)}</div>`;
    els.chart.appendChild(row);
  }
}

function renderTable() {
  els.tableBody.innerHTML = "";
  transactions.forEach((txn, i) => {
    const tr = document.createElement("tr");
    const isCredit = txn.amount < 0;
    const amountText = isCredit ? `+${money(-txn.amount)}` : money(txn.amount);

    const dateTd = document.createElement("td");
    dateTd.textContent = txn.date || "—";

    const descTd = document.createElement("td");
    descTd.textContent = txn.description;

    const amtTd = document.createElement("td");
    amtTd.className = "num" + (isCredit ? " credit" : "");
    amtTd.textContent = amountText;

    const catTd = document.createElement("td");
    catTd.appendChild(buildCategorySelect(txn, i));

    const srcTd = document.createElement("td");
    srcTd.innerHTML = `<span class="badge ${txn.source}">${txn.source}</span>`;

    tr.append(dateTd, descTd, amtTd, catTd, srcTd);
    els.tableBody.appendChild(tr);
  });
}

function buildCategorySelect(txn, index) {
  const select = document.createElement("select");
  select.className = "cat-select";
  for (const cat of CATEGORIES) {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    if (cat === txn.category) opt.selected = true;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => {
    transactions[index].category = select.value;
    transactions[index].source = "user";
    // Recompute the summary locally from the edited transactions.
    recomputeAndRerender();
  });
  return select;
}

function recomputeAndRerender() {
  const totals = {};
  let totalSpending = 0;
  let totalCredits = 0;
  for (const t of transactions) {
    if (t.amount >= 0) {
      totals[t.category] = (totals[t.category] || 0) + t.amount;
      totalSpending += t.amount;
    } else {
      totalCredits += -t.amount;
    }
  }
  const summary = Object.entries(totals)
    .map(([category, total]) => ({ category, total: Math.round(total * 100) / 100 }))
    .filter((s) => s.total > 0)
    .sort((a, b) => b.total - a.total);

  els.totalSpending.textContent = money(Math.round(totalSpending * 100) / 100);
  els.totalCredits.textContent = money(Math.round(totalCredits * 100) / 100);
  renderChart(summary);
  renderTable();
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}
