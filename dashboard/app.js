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
  mode: "score",         // score | weight
  actionFilter: "ALL",
  equityRange: "all",    // all | 72h | 24h
};

const NEWS_PIXELS_PER_SECOND = 70;   // marquee scroll speed

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
  renderNewsStrip();
  renderTicker();
  renderHighlight();
  renderEquityChart();
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
  // EQUITY is the canonical "current portfolio value" — flag it as .live
  // so the dot pulses green and the number breathes gently.
  $("#ticker-row").innerHTML = cells.map(([l, v]) => {
    const cls = "ticker" + (l === "EQUITY" ? " live" : "");
    return `<div class="${cls}"><div class="lbl">${l}</div><div class="val num">${v}</div></div>`;
  }).join("");
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

/* ---------- breaking-news strip (continuous scrolling marquee) ---------- */
function renderNewsStrip() {
  const strip = $("#news-strip");
  const track = $("#news-track");
  const items = (state.data.breaking_news || []).slice(0, 20);
  if (!items.length) {
    strip.hidden = true;
    track.innerHTML = "";
    return;
  }
  strip.hidden = false;

  // Build one rendered pass of all headlines, then duplicate it so the
  // CSS animation can loop seamlessly by translating -50%.
  const renderPass = () => items.map(it => {
    const s = Number(it.sentiment_score || 0);
    const sentCls = s > 0.05 ? "pos" : s < -0.05 ? "neg" : "neu";
    return `
      <a class="news-item" href="${escapeHtml(it.url || "#")}" target="_blank" rel="noopener">
        <span class="news-source">${escapeHtml(it.source || "")}</span>
        <span class="news-headline">${escapeHtml(it.headline || "")}</span>
        ${it.is_policy ? `<span class="news-policy">POLICY</span>` : ""}
        <span class="news-sentiment ${sentCls}" title="sentiment ${s.toFixed(2)}"></span>
        <span class="news-time">${timeAgo(it.published_utc)}</span>
      </a>
      <span class="news-sep" aria-hidden="true">·</span>
    `;
  }).join("");
  track.innerHTML = renderPass() + renderPass();

  // Calibrate scroll duration so speed stays roughly constant whether the
  // cycle returned 4 headlines or 20.
  requestAnimationFrame(() => {
    const halfWidth = track.scrollWidth / 2;
    const seconds = Math.max(40, Math.round(halfWidth / NEWS_PIXELS_PER_SECOND));
    track.style.setProperty("--news-duration", `${seconds}s`);
  });
}

function timeAgo(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "";
  const sec = Math.max(0, (Date.now() - t) / 1000);
  if (sec < 60)     return `${Math.floor(sec)}S AGO`;
  if (sec < 3600)   return `${Math.floor(sec / 60)}M AGO`;
  if (sec < 86400)  return `${Math.floor(sec / 3600)}H AGO`;
  return `${Math.floor(sec / 86400)}D AGO`;
}

/* ---------- equity line chart (SVG, vanilla) ---------- */
const EQUITY_COLOR = "#7B5CFF";

function renderEquityChart() {
  const root = $("#equity-chart");
  const meta = $("#equity-meta");
  const raw = state.data.equity_history || [];
  const all = raw
    .map(h => ({ t: new Date(h.t), v: Number(h.v) }))
    .filter(p => !isNaN(p.t) && !isNaN(p.v))
    .sort((a, b) => a.t - b.t);

  let points = all;
  if (state.equityRange === "72h" || state.equityRange === "24h") {
    const hrs = state.equityRange === "72h" ? 72 : 24;
    const cutoff = (all.length ? all[all.length - 1].t.getTime() : Date.now()) - hrs * 3600_000;
    points = all.filter(p => p.t.getTime() >= cutoff);
  }

  if (points.length < 2) {
    root.innerHTML =
      `<div class="equity-empty">EQUITY HISTORY WILL APPEAR AFTER A FEW CYCLES &nbsp;·&nbsp; CURRENT: ${all.length} POINT${all.length === 1 ? "" : "S"}</div>`;
    meta.textContent = "";
    return;
  }

  // viewBox layout
  const W = 1400, H = 340;
  const padL = 84, padR = 168, padT = 24, padB = 44;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const t0 = points[0].t.getTime();
  const t1 = points[points.length - 1].t.getTime();
  const tSpan = Math.max(1, t1 - t0);

  const vMin = Math.min(...points.map(p => p.v));
  const vMax = Math.max(...points.map(p => p.v));
  const vPad = Math.max((vMax - vMin) * 0.18, vMax * 0.005);
  const niceStep = niceTickStep((vMax + vPad - (vMin - vPad)) / 5);
  const yMin = Math.floor((vMin - vPad) / niceStep) * niceStep;
  const yMax = Math.ceil((vMax + vPad) / niceStep) * niceStep;
  const ySpan = Math.max(yMax - yMin, niceStep);

  const x = (t) => padL + ((t.getTime() - t0) / tSpan) * innerW;
  const y = (v) => padT + (1 - (v - yMin) / ySpan) * innerH;

  // Tick lines
  const yTicks = [];
  for (let v = yMin; v <= yMax + 0.001; v += niceStep) yTicks.push(Math.round(v));
  const xTicks = [];
  const xCount = 5;
  for (let i = 0; i <= xCount; i++) xTicks.push(new Date(t0 + (tSpan * i) / xCount));

  const path = points.map((p, i) =>
    `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");

  const startV = points[0].v;
  const startY = y(startV);
  const last = points[points.length - 1];
  const lastX = x(last.t);
  const lastY = y(last.v);
  const pillW = 120, pillH = 26;
  const pillX = Math.min(lastX + 14, W - padR + 30);
  const pillY = clamp(lastY - pillH / 2, padT, H - padB - pillH);

  const delta = last.v - startV;
  const pct = (delta / startV) * 100;
  const deltaCls = delta >= 0 ? "pos" : "neg";

  meta.innerHTML = `· LATEST <strong>${fmtUsd(last.v)}</strong> · Δ <span style="color:${delta >= 0 ? "#15994d" : "#d23030"}">${fmtUsdSigned(delta)} (${fmtPctSignedDirect(pct)})</span> · ${points.length} POINTS`;

  const svg = `
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      <!-- y grid + labels -->
      ${yTicks.map(v => `
        <line class="eq-grid-line" x1="${padL}" x2="${W - padR}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>
        <text class="eq-y-label" x="${padL - 10}" y="${(y(v) + 3.5).toFixed(1)}" text-anchor="end">$${v.toLocaleString()}</text>
      `).join("")}

      <!-- x grid + labels -->
      ${xTicks.map((d, i) => {
        const xp = padL + (i / xCount) * innerW;
        return `
          <line class="eq-x-tick" x1="${xp.toFixed(1)}" x2="${xp.toFixed(1)}" y1="${padT}" y2="${H - padB}"/>
          <text class="eq-x-label" x="${xp.toFixed(1)}" y="${H - padB + 18}" text-anchor="middle">${fmtAxisDate(d)}</text>
        `;
      }).join("")}

      <!-- baseline (starting equity) -->
      <line class="eq-baseline" x1="${padL}" x2="${W - padR}" y1="${startY.toFixed(1)}" y2="${startY.toFixed(1)}"/>
      <text class="eq-baseline-label" x="${(W - padR - 6).toFixed(1)}" y="${(startY - 4).toFixed(1)}" text-anchor="end">START $${Math.round(startV).toLocaleString()}</text>

      <!-- watermark (sits below the line) -->
      <text class="eq-watermark" x="${padL + 8}" y="${(H - padB - 8).toFixed(1)}">Momentum</text>

      <!-- equity trace -->
      <path class="eq-line" d="${path}" stroke="${EQUITY_COLOR}"/>

      <!-- connector + end-of-line pill -->
      <line class="eq-pill-connector" x1="${lastX.toFixed(1)}" y1="${lastY.toFixed(1)}" x2="${pillX.toFixed(1)}" y2="${(pillY + pillH / 2).toFixed(1)}" stroke="${EQUITY_COLOR}"/>
      <rect class="eq-pill" x="${pillX.toFixed(1)}" y="${pillY.toFixed(1)}" rx="13" ry="13" width="${pillW}" height="${pillH}" fill="${EQUITY_COLOR}"/>
      <text class="eq-pill-text" x="${(pillX + pillW / 2).toFixed(1)}" y="${(pillY + pillH / 2 + 4).toFixed(1)}" text-anchor="middle">${fmtUsd(last.v)}</text>
    </svg>
  `;

  root.innerHTML = svg;
}

function niceTickStep(rough) {
  if (rough <= 0) return 1;
  const exp = Math.floor(Math.log10(rough));
  const f = rough / Math.pow(10, exp);
  const niceFactor = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
  return niceFactor * Math.pow(10, exp);
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function fmtAxisDate(d) {
  const day = d.toLocaleDateString("en-US", { month: "short", day: "numeric" }).toUpperCase();
  const hm = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${day} ${hm}`;
}

function fmtUsdSigned(v) {
  if (v == null || isNaN(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return sign + "$" + Math.abs(v).toLocaleString("en-US", {
    maximumFractionDigits: 2, minimumFractionDigits: 2,
  });
}

function fmtPctSignedDirect(p) {
  if (p == null || isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return sign + p.toFixed(2) + "%";
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
  const w = d.config?.weights || {};
  return `<div class="readme-card"><span class="prompt">$</span> cat README.TXT

MOMENTUM — a conservative paper-trading research bot.

WHAT IT DOES
  Every 15 minutes, scores ~10 equity themes from price, volume, news,
  and policy signals, then rotates a paper portfolio across the strongest
  themes via Alpaca's PAPER trading API. Output is this read-only
  dashboard. No live trading, no margin, no shorting, no options.

SCORING FORMULA (per theme, 0..100)
  theme_score = ${w.momentum}·momentum
              + ${w.sentiment}·sentiment
              + ${w.volume}·volume
              + ${w.policy}·policy_catalyst
              − volatility_penalty            (0..30)

  - momentum         blend of 1d/5d/20d returns of constituents
  - sentiment        positive vs negative keyword hits in 24h news
  - volume           5-day avg / 20-day avg, log-shaped
  - policy_catalyst  hits for Fed, EPA, FDA, tariff, exec order, ...
  - vol_penalty      max(0, ann_vol − 0.30) × 35, capped at 30

  confidence   = 0.6·valid_feature_share + 0.4·min(1, news_count/8)
  final_weight = band_target × (0.5 + 0.5·confidence)

RANKING — SCORE BAND → TARGET WEIGHT PER THEME
  70 – 100   strong_buy       15 – 20 %
  55 – 69    buy              10 – 15 %
  40 – 54    starter           5 – 10 %
  35 – 39    hold_small        2 –  5 %
  <  35      exit_or_avoid             0 %

  Inside a theme, the top 3 tickers split its weight by ticker-level
  contribution score (same formula, per-ticker inputs).

RISK CAPS (hard)
  ≤ 20 % per theme · ≤ 7 % per ticker · ≤ 2 new buys/cycle
  5 – 8 % stop-loss · reduce at theme < 35 · exit at < 25
  ≥ 5 % cash buffer · halt new buys if drawdown > 15 %

DATA SOURCES
  prices / bars / clock   Alpaca Market Data + Paper Trading APIs
  per-theme news          Alpaca News  →  Yahoo Finance RSS  →  NewsAPI
  breaking-news ticker    Yahoo Finance · MarketWatch · BBC · NPR (RSS)
  sentiment + policy      keyword matching in src/sentiment.py (no API)

SAFETY
  ALPACA_PAPER must be 'true'. Any URL containing 'api.alpaca.markets'
  or 'live' is rejected; keys prefixed 'AK…' are rejected.
  ${d.config?.min_run_interval_minutes ?? 14}-minute interval floor enforced server-side.

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
  const eqt = e.target.closest("#equity-range button");
  if (eqt) {
    state.equityRange = eqt.dataset.range;
    document.querySelectorAll("#equity-range button")
      .forEach(b => b.classList.toggle("active", b === eqt));
    renderEquityChart();
  }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "filter-action") {
    state.actionFilter = e.target.value;
    renderFeed();
  }
});

load();
