"""Telemetry as Witness — Total Account Value chart, in the discipline of the original.

One trace per strategy, ten days across the field, color-coded pills at the terminus.
No ornament. Hairline grid. Mono everywhere; serif italic only at the watermark.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Fonts — drawn from the canvas-fonts library so the piece carries the same
# typographic voice as the dashboard.
# ---------------------------------------------------------------------------
FONT_DIR = Path(
    "/Users/chupei/Library/Application Support/Claude/local-agent-mode-sessions/"
    "skills-plugin/72fc09b1-a67e-4811-a92a-1b441eb482b3/"
    "fe260139-9414-40c8-9391-fb5649c8f72f/skills/canvas-design/canvas-fonts"
)
for f in (
    "IBMPlexMono-Regular.ttf",
    "IBMPlexMono-Bold.ttf",
    "InstrumentSerif-Italic.ttf",
):
    p = FONT_DIR / f
    if p.exists():
        fm.fontManager.addfont(str(p))

MONO = "IBM Plex Mono"
SERIF_IT = "Instrument Serif"

# ---------------------------------------------------------------------------
# Strategies. Each is a single trace. Final values are chosen to mirror the
# spread of the reference (one winner, one cluster near the start, one ruin).
# ---------------------------------------------------------------------------
STRATEGIES = [
    # name,                color,        final$,   vol,    style, seed, dy_pts
    ("AI-COMPUTE TILT",   "#7B5CFF", 22077.92, 0.022, "-",  3,    0),
    ("SEMI BROAD",        "#4A6FFF", 18343.93, 0.020, "-",  9,    0),
    ("DEFENSE ROTATION",  "#FF7A4D", 12163.50, 0.014, "-", 17,   10),
    ("BALANCED PAPER",    "#0F0F0F", 10933.41, 0.009, "--",23,  -10),
    ("ENERGY HEAVY",      "#2E9C5C",  4182.46, 0.026, "-", 31,    0),
]

N_PTS = 1400
START = datetime(2026, 5, 14, 9, 30)
END = datetime(2026, 5, 23, 16, 0)
TIMES = [START + (END - START) * i / (N_PTS - 1) for i in range(N_PTS)]


def make_track(final: float, vol: float, seed: int) -> np.ndarray:
    """Random-walk path that lands exactly on `final` at t=END."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, vol, N_PTS)
    rets[0] = 0
    cum = np.cumsum(rets)
    target = np.log(final / 10000)
    adj = (target - cum[-1]) * np.linspace(0, 1, N_PTS)
    return 10000 * np.exp(cum + adj)


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": [MONO, "DejaVu Sans Mono", "monospace"],
    "font.size": 9.5,
    "axes.unicode_minus": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

FIG_W, FIG_H = 17.0, 9.5
fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor="white")

# A single rectangular field, with breathing space for the status strip
# at top and the watermark line at the bottom. Right edge pulled inward so
# the end-of-line pills have room to land cleanly inside the page.
ax = fig.add_axes([0.055, 0.11, 0.78, 0.71])
ax.set_facecolor("white")
for s in ("top", "right", "left", "bottom"):
    ax.spines[s].set_visible(False)

# X / Y limits — leave room on the right for the end-pills.
X_BUFFER_HOURS = 18
ax.set_xlim(START, END + timedelta(hours=X_BUFFER_HOURS))
ax.set_ylim(-400, 26000)

# Y ticks
y_ticks = [0, 5000, 10000, 15000, 20000, 25000]
ax.set_yticks(y_ticks)
ax.set_yticklabels([f"${v:,}" for v in y_ticks], fontsize=9, color="#0a0a0a")
ax.tick_params(axis="y", length=0, pad=12)

# Y gridlines — almost invisible hairlines except for the baseline at 0.
for y in y_ticks:
    if y == 0:
        ax.axhline(y, color="#c8c8c8", linewidth=0.5, zorder=0)
    else:
        ax.axhline(y, color="#ececec", linewidth=0.5, zorder=0)

# X ticks — one per ~1.3 days, formatted like the reference.
day_ticks = []
cur = START
while cur <= END:
    day_ticks.append(cur)
    cur += timedelta(hours=32)
ax.set_xticks(day_ticks)
ax.set_xticklabels([d.strftime("%b %-d %H:%M").upper() for d in day_ticks],
                   fontsize=8, color="#6b6b6b")
ax.tick_params(axis="x", length=0, pad=14)

# Faint vertical gridlines at each tick
for t in day_ticks:
    ax.axvline(t, color="#f1f1f1", linewidth=0.5, zorder=0)

# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------
for name, color, final, vol, ls, seed, dy in STRATEGIES:
    track = make_track(final, vol, seed)
    if ls == "--":
        ax.plot(TIMES, track, color=color, linewidth=1.2, linestyle=(0, (5, 4)),
                alpha=0.85, zorder=2, dash_capstyle="round")
    else:
        ax.plot(TIMES, track, color=color, linewidth=1.7, alpha=0.95,
                zorder=2, solid_capstyle="round")

# ---------------------------------------------------------------------------
# End-of-line pills
# ---------------------------------------------------------------------------
for name, color, final, vol, ls, seed, dy in STRATEGIES:
    txt = f"${final:,.2f}"
    ax.annotate(
        txt,
        xy=(TIMES[-1], final),
        xytext=(36, dy),
        textcoords="offset points",
        fontsize=10.5, color="white", family=MONO, fontweight="bold",
        va="center", ha="left",
        bbox=dict(boxstyle="round,pad=0.6", fc=color, ec=color, lw=0),
        arrowprops=dict(arrowstyle="-", color=color, lw=1.3,
                        shrinkA=0, shrinkB=4),
        zorder=5,
    )

# ---------------------------------------------------------------------------
# Status strip (top): HIGHEST / LOWEST
# ---------------------------------------------------------------------------
sorted_perf = sorted(STRATEGIES, key=lambda s: -s[2])
top = sorted_perf[0]
bot = sorted_perf[-1]


def kpi(x, label, name, color, value, pct, value_color):
    """A KPI block: small grey label, colored swatch, name, value, signed pct."""
    fig.text(x, 0.948, label, color="#6b6b6b", fontsize=8.5, family=MONO,
             ha="left", va="center")
    # colored square swatch instead of unicode bullet
    fig.add_artist(plt.Rectangle((x + 0.052, 0.943), 0.009, 0.011,
                                 facecolor=color, edgecolor="none",
                                 transform=fig.transFigure))
    fig.text(x + 0.068, 0.948, name, color=color, fontsize=9.5,
             family=MONO, fontweight="bold", ha="left", va="center")
    fig.text(x + 0.200, 0.948, value, color="#0a0a0a", fontsize=10.5,
             family=MONO, fontweight="bold", ha="left", va="center")
    fig.text(x + 0.272, 0.948, pct, color=value_color, fontsize=10.5,
             family=MONO, fontweight="bold", ha="left", va="center")


top_pct = (top[2] / 10000 - 1) * 100
bot_pct = (bot[2] / 10000 - 1) * 100
kpi(0.055, "HIGHEST", top[0], top[1], f"${top[2]:,.2f}",
    f"{'+' if top_pct >= 0 else ''}{top_pct:.2f}%", "#15994d")
kpi(0.470, "LOWEST",  bot[0], bot[1], f"${bot[2]:,.2f}",
    f"{'+' if bot_pct >= 0 else ''}{bot_pct:.2f}%", "#d23030")

# Title — single quiet line above the field. Triple-spaced kerning to give
# the words gravity without resorting to a heavier weight.
fig.text(0.495, 0.895, "T O T A L   A C C O U N T   V A L U E",
         ha="center", va="center",
         fontsize=11, fontweight="bold", family=MONO, color="#0a0a0a")

# $ / % toggle (top-left of the field, decorative)
fig.text(0.060, 0.862, "$", ha="center", va="center",
         fontsize=9, family=MONO, color="white", fontweight="bold",
         bbox=dict(boxstyle="square,pad=0.45", fc="#0a0a0a", ec="none"))
fig.text(0.0775, 0.862, "%", ha="center", va="center",
         fontsize=9, family=MONO, color="#9a9a9a")

# ALL / 72H toggle (top-right of the field)
fig.text(0.808, 0.862, "ALL", ha="center", va="center",
         fontsize=9, family=MONO, color="white", fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.45", fc="#0a0a0a", ec="none"))
fig.text(0.832, 0.862, "72H", ha="center", va="center",
         fontsize=9, family=MONO, color="#9a9a9a")

# ---------------------------------------------------------------------------
# Watermarks
# ---------------------------------------------------------------------------
fig.text(0.055, 0.048, "Momentum", ha="left", va="center",
         family=SERIF_IT, fontstyle="italic", fontsize=22, color="#cdcdcd")
fig.text(0.055, 0.022, "BY  TRADING-NEWS-AGENT", ha="left", va="center",
         family=MONO, fontsize=7.5, color="#bdbdbd")

fig.text(0.910, 0.048, "PAPER  ·  ALPACA",
         ha="right", va="center", family=MONO, fontsize=7.5, color="#9a9a9a")
fig.text(0.910, 0.022, "github.com/chewythechoochoo/Momentum",
         ha="right", va="center", family=MONO, fontsize=7.5, color="#bdbdbd")

# A single horizontal hairline above the watermark zone — keeps the field
# from drifting off the page.
fig.add_artist(plt.Line2D([0.055, 0.910], [0.085, 0.085],
                          color="#ececec", linewidth=0.5,
                          transform=fig.transFigure))

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUT = Path("/Users/chupei/Desktop/Momentum/art")
OUT.mkdir(exist_ok=True)
fig.savefig(OUT / "total_account_value.pdf", facecolor="white")
fig.savefig(OUT / "total_account_value.png", facecolor="white", dpi=220)
print("wrote", OUT / "total_account_value.pdf")
print("wrote", OUT / "total_account_value.png")
