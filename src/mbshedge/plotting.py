"""One figure style for the whole project, and figure/table export.

Colors follow the strategy, never its rank. The three strategies in the headline
comparison (Static, Updating, Hybrid) use the first three slots of a palette whose
pairwise color-vision-deficiency separation was checked with a validator. The other
models get line styles as a second channel (dashed, dotted, dash-dot) so color never
carries identity alone, and the ex-post diagnostic is a black dotted line.

Every figure is saved as a 300-dpi PNG, an SVG, and the CSV of the plotted data, so the
later summary and deck can be rebuilt without refitting anything. In smoke mode every
figure carries a SYNTHETIC watermark.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
EPISODE_FILL = "#ecebe7"

STRATEGY_STYLE = {
    "UNH": {"color": "#8c8c8c", "ls": "-", "label": "Unhedged"},
    "S": {"color": "#2a78d6", "ls": "-", "label": "Static"},
    "U": {"color": "#eb6834", "ls": "-", "label": "Updating (EWMA)"},
    "H": {"color": "#1baf7a", "ls": "-", "label": "Hybrid (updating + refinancing)"},
    "E": {"color": INK_2, "ls": "--", "label": "Economic state"},
    "P": {"color": "#eda100", "ls": ":", "label": "Persistence"},
    "AR": {"color": "#e87ba4", "ls": "-.", "label": "AR(1)"},
    "X": {"color": INK, "ls": (0, (1, 1.5)), "label": "Ex-post diagnostic (infeasible)"},
}


def style(strategy: str) -> dict:
    s = STRATEGY_STYLE[strategy]
    return {"color": s["color"], "linestyle": s["ls"], "label": s["label"]}


def setup_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "figure.facecolor": "white", "axes.facecolor": "white",
        "font.size": 10.5, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.labelsize": 10.5,
        "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "grid.linestyle": "-", "lines.linewidth": 1.7, "legend.frameon": False,
        "legend.fontsize": 9.5, "axes.titlelocation": "left", "figure.constrained_layout.use": True,
        "text.parse_math": False,   # labels contain dollar signs ($mm), which must not start math mode
    })


def watermark(fig, mode: str) -> None:
    if mode == "smoke":
        fig.text(0.5, 0.5, "SYNTHETIC DATA: NOT A MARKET RESULT", ha="center", va="center", rotation=22,
                 fontsize=26, color="#c62828", alpha=0.14, weight="bold")


def shade_episodes(ax, episodes: list[dict], label: bool = False, end_default=None) -> None:
    for e in episodes:
        end = e["end"] or end_default
        if end is None:
            continue
        ax.axvspan(pd.Timestamp(e["start"]), pd.Timestamp(end), color=EPISODE_FILL, lw=0, zorder=0)
        if label:
            ax.text(pd.Timestamp(e["start"]), 1.0, e["name"], transform=ax.get_xaxis_transform(), fontsize=7,
                    color=INK_2, rotation=90, va="top", ha="right")


def mark_test_start(ax, test_start: str) -> None:
    ax.axvline(pd.Timestamp(test_start), color=INK_2, lw=1.0)
    ax.text(pd.Timestamp(test_start), 0.98, " test period →", transform=ax.get_xaxis_transform(), fontsize=8,
            color=INK_2, va="top", ha="left")


def save_figure(fig, name: str, paths, data: dict[str, pd.DataFrame] | pd.DataFrame | None = None,
                mode: str = "full") -> list[str]:
    """Save PNG + SVG + plotted data. Returns the written paths (relative to the project root)."""
    out_dir = Path(paths.figures)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data").mkdir(exist_ok=True)
    watermark(fig, mode)
    written = []
    for ext in ("png", "svg"):
        p = out_dir / f"{name}.{ext}"
        fig.savefig(p, bbox_inches="tight")
        written.append(paths.rel(p))
    if data is not None:
        items = data.items() if isinstance(data, dict) else [("", data)]
        for key, df in items:
            p = out_dir / "data" / (f"{name}__{key}.csv" if key else f"{name}.csv")
            df.to_csv(p)
            written.append(paths.rel(p))
    return written


def save_table(df: pd.DataFrame, name: str, paths, index: bool = True) -> list[str]:
    out_dir = Path(paths.tables)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{name}.csv"
    df.to_csv(p, index=index)
    return [paths.rel(p)]
