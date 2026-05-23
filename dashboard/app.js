// Cache-bust the JSON so GitHub Pages always serves the latest snapshot.
const DATA_URL = "data.json?t=" + Date.now();

const fmtUsd = (v) =>
  v == null ? "—" : v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const fmtPct = (v) => (v == null ? "—" : (v * 100).toFixed(2) + "%");
const fmtNum = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));

function plClass(v) { return v > 0 ? "pos" : v < 0 ? "neg" : ""; }

async function load() {
  let data;
  try {
    const resp = await fetch(DATA_URL, { cache: "no-store" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    data = await resp.json();
  } catch (e) {
    document.getElementById("meta").textContent = "Failed to load data.json: " + e.message;
    return;
  }

  // Meta line
  const meta = document.getElementById("meta");
  const market = data.market_open ? "open" : "closed";
  meta.innerHTML =
    `Generated <strong>${data.generated_at_utc}</strong> UTC · ` +
    `cycle #${data.cycle_count ?? "?"} · market <strong>${market}</strong> · ` +
    `mode <strong>${data.mode}</strong> · endpoint <strong>${data.endpoint ?? "alpaca-paper"}</strong>`;

  renderAccount(data.account);
  renderThemes(data.themes || []);
  renderPositions(data.positions || [], data.account);
  renderDecisions(data.decisions || []);
  renderNotes(data.notes || []);
}

function renderAccount(a) {
  const grid = document.getElementById("account");
  if (!a) {
    grid.innerHTML = '<div class="kv"><div class="k">Account</div><div class="v">Not connected</div></div>';
    return;
  }
  const fields = [
    ["Equity", fmtUsd(a.equity)],
    ["Cash", fmtUsd(a.cash)],
    ["Buying power", fmtUsd(a.buying_power)],
    ["Portfolio value", fmtUsd(a.portfolio_value)],
  ];
  grid.innerHTML = fields
    .map(([k, v]) => `<div class="kv"><div class="k">${k}</div><div class="v">${v}</div></div>`)
    .join("");
}

function renderThemes(themes) {
  const grid = document.getElementById("themes");
  if (!themes.length) { grid.innerHTML = '<p class="hint">No themes scored yet.</p>'; return; }
  grid.innerHTML = themes.map((t) => {
    const c = t.components || {};
    return `
      <div class="theme">
        <h3><span>${t.name}</span><span>${fmtNum(t.score, 1)}</span></h3>
        <div class="bar"><div style="width:${Math.max(0, Math.min(100, t.score))}%"></div></div>
        <div class="components">
          <span>momentum</span><span>${fmtNum(c.momentum, 1)}</span>
          <span>sentiment</span><span>${fmtNum(c.sentiment, 1)}</span>
          <span>volume</span><span>${fmtNum(c.volume, 1)}</span>
          <span>policy</span><span>${fmtNum(c.policy, 1)}</span>
          <span>vol penalty</span><span>−${fmtNum(c.volatility_penalty, 1)}</span>
          <span>target weight</span><span>${fmtPct(t.weight)}</span>
          <span>confidence</span><span>${fmtNum(t.confidence, 2)}</span>
          <span>band</span><span>${t.band || "—"}</span>
        </div>
      </div>`;
  }).join("");
}

function renderPositions(positions, account) {
  const tbody = document.querySelector("#positions tbody");
  if (!positions.length) { tbody.innerHTML = '<tr><td colspan="7">No open positions.</td></tr>'; return; }
  tbody.innerHTML = positions.map((p) => `
    <tr>
      <td><strong>${p.symbol}</strong></td>
      <td>${fmtNum(p.qty, 4)}</td>
      <td>${fmtUsd(p.avg_entry_price)}</td>
      <td>${fmtUsd(p.current_price)}</td>
      <td>${fmtUsd(p.market_value)}</td>
      <td class="${plClass(p.unrealized_pl)}">${fmtUsd(p.unrealized_pl)} (${fmtPct(p.unrealized_plpc)})</td>
      <td>${fmtPct(p.weight)}</td>
    </tr>`).join("");
}

function renderDecisions(decisions) {
  const tbody = document.querySelector("#decisions tbody");
  if (!decisions.length) { tbody.innerHTML = '<tr><td colspan="6">No decisions this cycle.</td></tr>'; return; }
  tbody.innerHTML = decisions.map((d) => `
    <tr>
      <td><span class="action ${d.action}">${d.action}</span></td>
      <td><strong>${d.symbol}</strong></td>
      <td>${d.theme_key || "—"}</td>
      <td>${fmtUsd(d.notional_delta)}</td>
      <td>${d.reason}</td>
      <td class="factors">${(d.factors || []).join(" · ")}</td>
    </tr>`).join("");
}

function renderNotes(notes) {
  const section = document.getElementById("notes-section");
  const ul = document.getElementById("notes");
  if (!notes.length) { section.classList.add("hidden"); return; }
  section.classList.remove("hidden");
  ul.innerHTML = notes.map((n) => `<li>${n}</li>`).join("");
}

load();
