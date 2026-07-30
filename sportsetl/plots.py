"""Rendering helpers -- correlation heatmaps with matplotlib (no seaborn dep)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def plot_correlation_heatmap(
    corr: pd.DataFrame,
    out_path: str,
    *,
    title: str = "Correlation matrix",
) -> str:
    """Render a labelled correlation heatmap to ``out_path`` and return it."""
    labels = list(corr.columns)
    data = corr.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(1.6 * len(labels) + 1.5, 1.4 * len(labels) + 1.2))
    im = ax.imshow(data, cmap="RdBu_r", vmin=-1, vmax=1)

    ax.set_xticks(range(len(labels)), labels=labels)
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    for i in range(len(labels)):
        for j in range(len(labels)):
            val = data[i, j]
            ax.text(
                j, i, f"{val:.2f}",
                ha="center", va="center",
                color="white" if abs(val) > 0.55 else "black",
                fontsize=12, fontweight="bold",
            )

    ax.set_title(title, pad=28, fontsize=13, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.06)
    cbar.set_label("Pearson r", rotation=270, labelpad=15)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path
