"use strict";

const CATEGORIES = [
  "Groceries", "Dining", "Transport", "Shopping", "Entertainment",
  "Utilities", "Housing", "Health", "Insurance", "Travel", "Income",
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
  topCategory: document.getElementById("top-category"),
  topCategoryAmount: document.getElementById("top-category-amount"),
  donut: document.getElementById("donut"),
  donutTotal: document.getElementById("donut-total"),
  legend: document.getElementById("legend"),
  tooltip: document.getElementById("chart-tooltip"),
  tableBody: document.querySelector("#txn-table tbody"),
};

// Validated categorical palette (dark-surface hues), dataviz skill reference
// instance. Assigned by spend rank; a 9th+ category folds into OTHER_COLOR.
const PALETTE = [
  "#3987e5", "#d95926", "#199e70", "#c98500",
  "#d55181", "#008300", "#9085e9", "#e66767",
];
const OTHER_COLOR = "#898781";
const SVG_NS = "http://www.w3.org/2000/svg";

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

  renderDashboard();
  renderTable();
  els.results.hidden = false;
}

// Aggregate transactions into ranked, colored spending rows + totals.
function computeSummary() {
  const totals = {};
  const counts = {};
  let totalSpending = 0;
  let totalCredits = 0;
  for (const t of transactions) {
    if (t.amount >= 0) {
      totals[t.category] = (totals[t.category] || 0) + t.amount;
      counts[t.category] = (counts[t.category] || 0) + 1;
      totalSpending += t.amount;
    } else {
      totalCredits += -t.amount;
    }
  }

  let rows = Object.keys(totals)
    .map((category) => ({
      category,
      total: Math.round(totals[category] * 100) / 100,
      count: counts[category],
    }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total);

  // Fold everything past the palette size into a single neutral slice.
  if (rows.length > PALETTE.length) {
    const head = rows.slice(0, PALETTE.length - 1);
    const tail = rows.slice(PALETTE.length - 1);
    head.push({
      category: "Other categories",
      total: Math.round(tail.reduce((s, r) => s + r.total, 0) * 100) / 100,
      count: tail.reduce((s, r) => s + r.count, 0),
      isFolded: true,
    });
    rows = head;
  }

  rows.forEach((r, i) => {
    r.color = r.isFolded ? OTHER_COLOR : PALETTE[i];
    r.pct = totalSpending > 0 ? (r.total / totalSpending) * 100 : 0;
  });

  return {
    rows,
    totalSpending: Math.round(totalSpending * 100) / 100,
    totalCredits: Math.round(totalCredits * 100) / 100,
  };
}

function renderDashboard() {
  const { rows, totalSpending, totalCredits } = computeSummary();

  els.totalSpending.textContent = money(totalSpending);
  els.totalCredits.textContent = totalCredits > 0 ? `+${money(totalCredits)}` : money(0);
  els.totalCount.textContent = String(transactions.length);
  els.donutTotal.textContent = money(totalSpending);

  if (rows.length) {
    els.topCategory.textContent = rows[0].category;
    els.topCategoryAmount.textContent = `${money(rows[0].total)} · ${rows[0].pct.toFixed(0)}%`;
  } else {
    els.topCategory.textContent = "—";
    els.topCategoryAmount.textContent = "";
  }

  renderDonut(rows, totalSpending);
  renderLegend(rows);
}

function renderDonut(rows, totalSpending) {
  els.donut.innerHTML = "";
  if (!rows.length || totalSpending <= 0) return;

  const r = 45;
  const cx = 60;
  const cy = 60;
  const circumference = 2 * Math.PI * r;
  const gap = rows.length > 1 ? 2 : 0; // surface gap between segments (viewBox units)
  let offset = 0;

  rows.forEach((row) => {
    const frac = row.total / totalSpending;
    const seg = Math.max(frac * circumference - gap, 0.5);
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", r);
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", row.color);
    circle.setAttribute("stroke-width", "16");
    circle.setAttribute("stroke-dasharray", `${seg} ${circumference - seg}`);
    circle.setAttribute("stroke-dashoffset", `${-offset}`);
    circle.dataset.category = row.category;

    circle.addEventListener("mouseenter", (e) => {
      dimSiblings(circle, true);
      showTooltip(e, row);
    });
    circle.addEventListener("mousemove", (e) => moveTooltip(e));
    circle.addEventListener("mouseleave", () => {
      dimSiblings(circle, false);
      hideTooltip();
    });

    els.donut.appendChild(circle);
    offset += frac * circumference;
  });
}

function renderLegend(rows) {
  els.legend.innerHTML = "";
  if (!rows.length) {
    els.legend.innerHTML = '<p class="hint">No spending to summarize.</p>';
    return;
  }
  rows.forEach((row) => {
    const el = document.createElement("div");
    el.className = "legend-row";
    el.innerHTML = `
      <span class="legend-swatch" style="background:${row.color}"></span>
      <span class="legend-name" title="${escapeHtml(row.category)}">${escapeHtml(row.category)}
        <span class="legend-count">· ${row.count}</span></span>
      <span class="legend-pct">${row.pct.toFixed(1)}%</span>
      <span class="legend-amt">${money(row.total)}</span>`;
    el.addEventListener("mouseenter", (e) => {
      const circle = els.donut.querySelector(`circle[data-category="${cssEscape(row.category)}"]`);
      if (circle) dimSiblings(circle, true);
      showTooltip(e, row);
    });
    el.addEventListener("mousemove", (e) => moveTooltip(e));
    el.addEventListener("mouseleave", () => {
      undimAll();
      hideTooltip();
    });
    els.legend.appendChild(el);
  });
}

// --- donut hover helpers ----------------------------------------------------
function dimSiblings(active, on) {
  els.donut.querySelectorAll("circle").forEach((c) => {
    c.classList.toggle("dim", on && c !== active);
  });
}
function undimAll() {
  els.donut.querySelectorAll("circle").forEach((c) => c.classList.remove("dim"));
}
function showTooltip(e, row) {
  els.tooltip.innerHTML =
    `<div class="tt-cat">${escapeHtml(row.category)}</div>` +
    `<div class="tt-sub">${money(row.total)} · ${row.pct.toFixed(1)}% · ${row.count} txn</div>`;
  els.tooltip.hidden = false;
  moveTooltip(e);
}
function moveTooltip(e) {
  const pad = 14;
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  const rect = els.tooltip.getBoundingClientRect();
  if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - pad;
  els.tooltip.style.left = `${x}px`;
  els.tooltip.style.top = `${y}px`;
}
function hideTooltip() {
  els.tooltip.hidden = true;
}
function cssEscape(s) {
  return s.replace(/"/g, '\\"');
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
  renderDashboard();
  renderTable();
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}
