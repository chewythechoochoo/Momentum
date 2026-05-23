// Read-only dashboard. Reads dashboard/data.json only. No write/network/state.
const DATA_URL = "data.json?t=" + Date.now();

// One color per theme key — used for chart pills, row dots, and feed avatars.
const THEME_COLORS = {
  ai_compute:             "#7B5CFF",
  ev_clean_transport:     "#4A6FFF",
  clean_energy:           "#1F1F1F",
  oil_gas:                "#E5343C",
  defense:                "#FF7A4D",
  biotech:                "#2E9C5C",
  cybersecurity:          "#00A3FF",
  financials:             "#9CA0A6",
  consumer_discretionary: "#C724B1",
  semiconductors_ex_ai:   "#FFB400",
};
const color = (key) => THEME_COLORS[key] || "#0a0a0a";
const $ = (sel) => document.querySelector(sel);

const fmtUsd = (v) => {
  if (v == null || isNaN(v)) return "—";
  const sign = v < 0 ? "−" : "";
  return sign + "$" + Math.abs(v).toLocaleString("en-US", {
    maximumFractionDigits: 2, minimumFractionDigits: 2,
  });
};
const fmtPct = (v) => (v == null ? "—" : (v * 100).toFixed(2) + "%");
const fmtPctSigned = (v) => {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return sign + (v * 100).toFixed(2) + "%";
};
const fmtNum = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));
const titleize = (k) => (k || "").replace(/_/g, " ").toUpperCase();

const state = {
  data: null,
  tab: "decisions",
  mode: "score",      // score | weight
  actionFilter: "ALL",
};

async function load() {
  try {
    const r = await fetch(DATA_URL, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    state.data = await r.json();
  } catch (e) {
    $("#meta-strip").innerHTML =
      `<span class="paper-pill">PAPER</span><span>FAILED TO LOAD data.json — ${e.message}</span>`;
    return;
  }
  renderAll();
}

function renderAll() {
  renderMeta();
  renderTicker();
  renderHighlight();
  renderChart();
  renderFeed();
}

/* ---------- meta strip ---------- */
function renderMeta() {
  const d = state.data;
  const market = d.market_open ? "MARKET OPEN" : "MARKET CLOSED";
  $("#meta-strip").innerHTML = `
    <span class="paper-pill">${d.mode || "PAPER"}</span>
    <span>GENERATED <strong>${d.generated_at_utc || "—"}</strong> UTC</span>
    <span class="dot-sep">│</span>
    <span>CYCLE #${d.cycle_count ?? 0}</span>
    <span class="dot-sep">│</span>
    <span>${market}</span>
    <span class="dot-sep">│</span>
    <span>ENDPOINT ${d.endpoint || "alpaca-paper"}</span>
    <span class="dot-sep">│</span>
    <span>MIN INTERVAL ${d.config?.min_run_interval_minutes ?? 14}M</span>
  `;
}

/* ---------- ticker row ---------- */
function renderTicker() {
  const a = state.data.account;
  const cells = [
    ["EQUITY",          a ? fmtUsd(a.equity)          : "—"],
    ["CASH",            a ? fmtUsd(a.cash)            : "—"],
    ["BUYING POWER",    a ? fmtUsd(a.buying_power)    : "—"],
    ["PORTFOLIO VALUE", a ? fmtUsd(a.portfolio_value) : "—"],
    ["POSITIONS",       String(state.data.positions?.length ?? 0)],
    ["THEMES SCORED",   String(state.data.themes?.length ?? 0)],
    ["DECISIONS",       String(state.data.decisions?.length ?? 0)],
  ];
  $("#ticker-row").innerHTML = cells.map(([l, v]) =>
    `<div class="ticker"><div class="lbl">${l}</div><div class="val num">${v}</div></div>`
  ).join("");
}

/* ---------- highlight band ---------- */
function renderHighlight() {
  const themes = state.data.themes || [];
  const band = $("#highlight-band");
  if (themes.length < 1) { band.innerHTML = ""; return; }
  const sorted = [...themes].sort((a, b) => b.score - a.score);
  const top = sorted[0];
  const bot = sorted[sorted.length - 1];
  band.innerHTML = `
    <div class="highlight up">
      <span>STRONGEST</span>
      <span class="h-dot" style="background:${color(top.key)}"></span>
      <span class="h-name">${top.name?.toUpperCase() || titleize(top.key)}</span>
      <span class="h-score">${fmtNum(top.score, 2)}</span>
      <span class="h-pill">TARGET ${fmtPct(top.weight)} · ${(top.band || "").toUpperCase()}</span>
    </div>
    <div class="highlight down">
      <span>WEAKEST</span>
      <span class="h-dot" style="background:${color(bot.key)}"></span>
      <span class="h-name">${bot.name?.toUpperCase() || titleize(bot.key)}</span>
      <span class="h-score">${fmtNum(bot.score, 2)}</span>
      <span class="h-pill">TARGET ${fmtPct(bot.weight)} · ${(bot.band || "").toUpperCase()}</span>
    </div>
  `;
}

/* ---------- chart ---------- */
function renderChart() {
  const themes = [...(state.data.themes || [])].sort((a, b) => b.score - a.score);
  const grid = $("#theme-chart");
  // Preserve the grid-vertical lines, replace everything else.
  grid.innerHTML =
    `<div class="grid-vertical"><span></span><span></span><span></span><span></span></div>`;

  const maxWeight = Math.max(0.001, ...themes.map(t => t.weight || 0));

  for (const t of themes) {
    let widthPct, pillLabel;
    if (state.mode === "score") {
      widthPct = Math.max(0, Math.min(100, t.score));
      pillLabel = fmtNum(t.score, 2);
    } else {
      widthPct = Math.max(0, Math.min(100, ((t.weight || 0) / maxWeight) * 100));
      pillLabel = fmtPct(t.weight);
    }
    const c = color(t.key);
    const c_comp = t.components || {};
    const row = document.createElement("div");
    row.className = "theme-row";
    row.style.setProperty("--themecolor", c);
    row.innerHTML = `
      <span class="row-label"><span class="dot"></span>${(t.name || titleize(t.key)).toUpperCase()}</span>
      <div class="track">
        <div class="bar" style="width:${widthPct}%"></div>
      </div>
      <span class="row-pill">${pillLabel}</span>
      <div class="row-components">
        <span>MOM ${fmtNum(c_comp.momentum, 0)}</span>
        <span>SEN ${fmtNum(c_comp.sentiment, 0)}</span>
        <span>VOL ${fmtNum(c_comp.volume, 0)}</span>
        <span>POL ${fmtNum(c_comp.policy, 0)}</span>
        <span class="vp">−${fmtNum(c_comp.volatility_penalty, 0)} VOL PEN</span>
        <span class="band">${(t.band || "—").toUpperCase()} · CONF ${fmtNum(t.confidence, 2)}</span>
      </div>
    `;
    grid.appendChild(row);
  }

  $("#x-axis-label").textContent = state.mode === "score"
    ? "THEME SCORE (0–100)"
    : "TARGET WEIGHT (NORMALIZED TO STRONGEST THEME)";
}

/* ---------- feed ---------- */
function renderFeed() {
  const body = $("#feed-body");
  const d = state.data;
  const filterEl = $("#filter-action");
  filterEl.parentElement.style.display = state.tab === "decisions" ? "" : "none";

  let html = "";
  let count = 0;

  if (state.tab === "decisions") {
    const items = (d.decisions || []).filter(x =>
      state.actionFilter === "ALL" || x.action === state.actionFilter);
    count = items.length;
    html = items.length ? items.map(decisionCard).join("") : emptyCard("No decisions this cycle.");
  } else if (state.tab === "positions") {
    const items = d.positions || [];
    count = items.length;
    html = items.length ? items.map(positionCard).join("") : emptyCard("No open positions.");
  } else if (state.tab === "executions") {
    const items = d.executions || [];
    count = items.length;
    html = items.length ? items.map(executionCard).join("") : emptyCard("No executions this cycle.");
  } else if (state.tab === "readme") {
    html = readmeBlock(d);
  }
  body.innerHTML = html;
  $("#feed-count").textContent = state.tab === "readme"
    ? ""
    : `SHOWING ${count} ${state.tab.toUpperCase()}`;
}

function decisionCard(x) {
  const c = color(x.theme_key);
  const wDelta = (x.target_weight || 0) - (x.current_weight || 0);
  const cls = wDelta > 0 ? "pos" : wDelta < 0 ? "neg" : "";
  return `
    <div class="feed-card" style="--themecolor:${c}">
      <div class="head">
        <span class="who">
          <span class="who-dot"></span>
          <span class="action-tag ${x.action}">${x.action}</span>
          <strong>${x.symbol}</strong>
          <span style="color:var(--muted)">${titleize(x.theme_key)}</span>
        </span>
        <time>CYCLE #${state.data.cycle_count ?? 0}</time>
      </div>
      <div class="kv"><span class="k">target weight:</span> <span class="num">${fmtPct(x.target_weight)}</span> &nbsp;→&nbsp;
        <span class="k">current:</span> <span class="num">${fmtPct(x.current_weight)}</span></div>
      <div class="kv"><span class="k">notional Δ:</span> <span class="num">${fmtUsd(x.notional_delta)}</span></div>
      <div class="kv"><span class="k">reason:</span> ${escapeHtml(x.reason || "")}</div>
      ${(x.factors || []).length
        ? `<div class="kv"><span class="k">factors:</span> ${x.factors.map(escapeHtml).join(" · ")}</div>`
        : ""}
      <div class="delta-line ${cls}">
        <span class="label">WEIGHT Δ</span>
        <span class="num">${fmtPctSigned(wDelta)}</span>
      </div>
    </div>`;
}

function positionCard(p) {
  const cls = p.unrealized_pl > 0 ? "pos" : p.unrealized_pl < 0 ? "neg" : "";
  return `
    <div class="feed-card">
      <div class="head">
        <span class="who"><span class="who-dot" style="background:#0a0a0a"></span><strong>${p.symbol}</strong>
          <span style="color:var(--muted)">QTY ${fmtNum(p.qty, 4)}</span></span>
        <time>WEIGHT ${fmtPct(p.weight)}</time>
      </div>
      <div class="kv"><span class="k">price:</span> <span class="num">${fmtUsd(p.avg_entry_price)}</span> &nbsp;→&nbsp;
        <span class="num">${fmtUsd(p.current_price)}</span></div>
      <div class="kv"><span class="k">market value:</span> <span class="num">${fmtUsd(p.market_value)}</span></div>
      <div class="delta-line ${cls}">
        <span class="label">NET P&amp;L</span>
        <span class="num">${fmtUsd(p.unrealized_pl)} (${fmtPctSigned(p.unrealized_plpc)})</span>
      </div>
    </div>`;
}

function executionCard(e) {
  const wDelta = (e.target_weight || 0) - (e.current_weight || 0);
  const c = color(e.theme_key);
  return `
    <div class="feed-card" style="--themecolor:${c}">
      <div class="head">
        <span class="who"><span class="who-dot"></span>
          <span class="action-tag ${e.action}">${e.action}</span>
          <strong>${e.symbol}</strong></span>
        <time>${e.executed ? "EXECUTED" : (e.note || "DRY RUN").toUpperCase()}</time>
      </div>
      <div class="kv"><span class="k">notional Δ:</span> <span class="num">${fmtUsd(e.notional_delta)}</span></div>
      <div class="kv"><span class="k">reason:</span> ${escapeHtml(e.reason || "")}</div>
      ${e.order
        ? `<div class="kv"><span class="k">order id:</span> ${escapeHtml(String(e.order.id))} · ${escapeHtml(String(e.order.status))}</div>`
        : ""}
      ${e.error
        ? `<div class="delta-line neg"><span class="label">ERROR</span> ${escapeHtml(e.error)}</div>`
        : `<div class="delta-line ${wDelta >= 0 ? "pos" : "neg"}"><span class="label">WEIGHT Δ</span> ${fmtPctSigned(wDelta)}</div>`}
    </div>`;
}

function readmeBlock(d) {
  const r = d.config?.risk || {};
  const w = d.config?.weights || {};
  const fmtR = (v, d = 0) => v == null ? "—" : (v * 100).toFixed(d) + "%";
  return `<div class="readme-card"><span class="prompt">$</span> cat README.TXT

MOMENTUM — paper-trading news + momentum theme-rotation agent.
Runs every 15 minutes on GitHub Actions. Refuses any live-money config.

SCORING (weights from data.json)
  theme_score = ${w.momentum}·momentum + ${w.sentiment}·sentiment + ${w.volume}·volume + ${w.policy}·policy
                − volatility_penalty (0..30)
  confidence  = 0.6·valid_feature_share + 0.4·min(1, news_count/8)
  final_weight = band_target_weight × (0.5 + 0.5·confidence)

SCORE BANDS → TARGET WEIGHT PER THEME
  70+      strong_buy      15–20 %
  55–69    buy             10–15 %
  40–54    starter          5–10 %
  35–39    hold_small       2–5 %
  <35      exit_or_avoid    0 %

RISK CAPS
  max theme weight ......... ${fmtR(r.max_theme_weight)}
  max ticker weight ........ ${fmtR(r.max_ticker_weight)}
  max new buys per cycle ... ${r.max_new_buys_per_cycle ?? "—"}
  stop-loss range .......... ${fmtR(r.stop_loss_pct_range?.[0])} – ${fmtR(r.stop_loss_pct_range?.[1])}
  min price ................ $${r.min_price ?? "—"}
  min avg daily volume ..... ${(r.min_avg_daily_volume ?? 0).toLocaleString()}
  reduce below score ....... ${r.reduce_below_score ?? "—"}
  exit below score ......... ${r.exit_below_score ?? "—"}
  cash buffer .............. ${fmtR(r.cash_buffer_pct)}

SAFETY
  - PAPER endpoint only. ALPACA_PAPER=true required.
  - ALPACA_BASE_URL containing 'api.alpaca.markets' or 'live' is rejected.
  - 'AK…' prefixed keys are rejected (live keys).
  - ${d.config?.min_run_interval_minutes ?? 14}-minute cycle floor enforced server-side.
  - No margin, no shorts, no options, no penny stocks, no illiquid tickers.

SOURCE
  github.com/chewythechoochoo/Momentum
</div>`;
}

function emptyCard(msg) {
  return `<div class="feed-card" style="color:var(--muted)">${msg}</div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

/* ---------- event wiring ---------- */
document.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (tab) {
    state.tab = tab.dataset.tab;
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
    renderFeed();
  }
  const tog = e.target.closest("#mode-toggle button");
  if (tog) {
    state.mode = tog.dataset.mode;
    document.querySelectorAll("#mode-toggle button")
      .forEach(b => b.classList.toggle("active", b === tog));
    renderChart();
  }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "filter-action") {
    state.actionFilter = e.target.value;
    renderFeed();
  }
});

load();
