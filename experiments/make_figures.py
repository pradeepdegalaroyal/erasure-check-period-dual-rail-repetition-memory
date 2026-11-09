"""Figures from the CSV files in results/ (200 dpi, muted Tableau palette)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

TAB = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#9c755f", "#bab0ac"]
PER_ORDER = ["1", "2", "3", "4", "5", "6", "none"]
SCEN_TITLE = {"cheap_check": "cheap check (0.5 us, 0.5 % back-action)",
              "costly_check": "costly check (2 us, 2 % back-action)"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25})


def _order(periods) -> list:
    return [p for p in PER_ORDER if p in set(periods)]


def fig_ecdf(grid: pd.DataFrame, path: Path) -> None:
    """Empirical CDF over the device grid of each schedule's rate relative to period 1."""
    m = grid.groupby(["tau_c", "p_check", "period"]).rate_per_us.mean().unstack("period")
    ratio = m.div(m["1"], axis=0)
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    for i, p in enumerate([c for c in _order(ratio.columns) if c != "1"]):
        v = np.sort(ratio[p].values)
        ax.step(v, np.arange(1, len(v) + 1) / len(v), where="post", color=TAB[i], lw=1.8,
                label=f"check every {p} rounds")
    best = np.sort(m.min(axis=1).div(m["1"]).values)
    ax.step(best, np.arange(1, len(best) + 1) / len(best), where="post", color="black", lw=2.0,
            label="best period per device")
    ax.axvline(1.0, color="grey", ls="--", lw=1)
    ax.set_xscale("log")
    ticks = [0.8, 1, 1.5, 2, 3, 5]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_xlabel("logical error rate relative to checking every round (ratio, log scale)")
    ax.set_ylabel("fraction of devices (empirical CDF)")
    ax.set_title(f"Schedule rate across {len(m)} device settings (d = 5)")
    ax.legend(fontsize=7.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_violin(main: pd.DataFrame, path: Path) -> None:
    """Per-seed logical error rate per schedule (violin + individual seeds), d = 5."""
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), sharey=False)
    for ax, scen in zip(axes, ["cheap_check", "costly_check"]):
        s = main[(main.scenario == scen) & (main.d == 5) & (main.decoder == "graded")]
        pers = _order(s.period.unique())
        data = [s[s.period == p].rate_per_us.values for p in pers]
        vp = ax.violinplot(data, showextrema=False, widths=0.8)
        for b in vp["bodies"]:
            b.set_facecolor(TAB[0])
            b.set_alpha(0.35)
        ax.boxplot(data, widths=0.25, showfliers=False, medianprops=dict(color="black"))
        rng = np.random.default_rng(0)
        for i, v in enumerate(data):
            ax.scatter(i + 1 + rng.uniform(-0.08, 0.08, len(v)), v, s=14, color=TAB[1], zorder=3)
        ax.set_xticks(range(1, len(pers) + 1))
        ax.set_xticklabels(pers)
        ax.set_xlabel("check period (rounds between erasure checks)")
        ax.set_ylabel("logical error rate (per microsecond)")
        ax.set_title(SCEN_TITLE[scen], fontsize=9)
    fig.suptitle("Seed-to-seed spread of the logical error rate, d = 5, graded-window decoder", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_phase(best: pd.DataFrame, path: Path) -> None:
    """Filled-contour map of the gain of the best schedule over checking every round."""
    taus = sorted(best.tau_c.unique())
    pcs = sorted(best.p_check.unique())
    z = np.zeros((len(pcs), len(taus)))
    lab = np.empty(z.shape, dtype=object)
    sig = np.zeros(z.shape, dtype=bool)
    for _, r in best.iterrows():
        i, j = pcs.index(r.p_check), taus.index(r.tau_c)
        z[i, j] = 100.0 * r.gain
        lab[i, j] = str(r.best_period)
        sig[i, j] = bool(r.significant)
    X, Y = np.meshgrid(np.log10(taus), np.log10(pcs))
    fig, ax = plt.subplots(figsize=(6.0, 4.4))
    top = float(np.ceil(max(z.max(), 1.0) / 5.0) * 5.0)
    levels = np.linspace(0, top, int(top / 2.5) + 1)
    cs = ax.contourf(X, Y, z, levels=levels, cmap="Blues", extend="max", vmin=0, vmax=top * 1.3)
    for i in range(len(pcs)):
        for j in range(len(taus)):
            txt = f"{lab[i, j]}" + ("*" if sig[i, j] else "")
            ax.text(X[i, j], Y[i, j], txt, ha="center", va="center", fontsize=8.5, color="black",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    cb = fig.colorbar(cs, ax=ax)
    cb.set_label("error-rate reduction vs checking every round (percent)")
    ax.set_xlim(X.min() - 0.12, X.max() + 0.12)
    ax.set_ylim(Y.min() - 0.12, Y.max() + 0.12)
    ax.set_xticks(np.log10(taus))
    ax.set_xticklabels([f"{t:g}" for t in taus])
    ax.set_yticks(np.log10(pcs))
    ax.set_yticklabels([f"{p:g}" for p in pcs])
    ax.set_xlabel("check duration (microseconds)")
    ax.set_ylabel("bit-flip probability added per check")
    ax.set_title("Best check period per device (label; * = gain above 2 SE)", fontsize=9)
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_scaling(agg: pd.DataFrame, path: Path) -> None:
    """Logical error rate versus code distance for the schedules and baselines."""
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), sharey=True)
    for ax, scen in zip(axes, ["cheap_check", "costly_check"]):
        s = agg[agg.scenario == scen]
        series = [("graded", "1", "graded, check every round", TAB[0], "o"),
                  ("graded", "2", "graded, every 2 rounds", TAB[1], "s"),
                  ("graded", "none", "graded, no checks", TAB[2], "^"),
                  ("majority", "1", "classical majority vote", TAB[7], "x"),
                  ("blind", "1", "erasure-blind matching, every round", TAB[6], "D")]
        for dec, per, name, c, mk in series:
            t = s[(s.decoder == dec) & (s.period == per)].sort_values("d")
            if t.empty:
                continue
            ax.errorbar(t.d, t["mean"], yerr=t["std"].fillna(0), color=c, marker=mk, ms=5, lw=1.5,
                        capsize=2, label=name)
        ax.set_yscale("log")
        ax.set_xticks(sorted(s.d.unique()))
        ax.set_xlabel("repetition-code distance d")
        ax.set_title(SCEN_TITLE[scen], fontsize=9)
    axes[0].set_ylabel("logical error rate (per microsecond)")
    axes[1].legend(fontsize=7, loc="lower left")
    fig.suptitle("Distance scaling (mean +/- std over seeds)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_decoders(main: pd.DataFrame, path: Path) -> None:
    """Decoder ablation at d = 5: logical failure probability versus check period."""
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), sharey=True)
    names = {"blind": "erasure-blind", "flat_uncal": "flat window, nominal prior", "flat": "flat window, calibrated",
             "graded": "graded window, calibrated", "oracle": "oracle erasure positions"}
    for ax, scen in zip(axes, ["cheap_check", "costly_check"]):
        s = main[(main.scenario == scen) & (main.d == 5)]
        for i, dec in enumerate(["blind", "flat_uncal", "flat", "graded", "oracle"]):
            t = s[s.decoder == dec].groupby("period").p_fail.agg(["mean", "std"]).reindex(_order(s.period.unique()))
            ax.errorbar(range(len(t)), t["mean"], yerr=t["std"], color=TAB[i], marker="o", ms=4, lw=1.4,
                        capsize=2, label=names[dec])
        ax.set_xticks(range(len(_order(s.period.unique()))))
        ax.set_xticklabels(_order(s.period.unique()))
        ax.set_yscale("log")
        ax.set_xlabel("check period (rounds between erasure checks)")
        ax.set_title(SCEN_TITLE[scen], fontsize=9)
    axes[0].set_ylabel("logical failure probability (12 000 shots/seed)")
    axes[0].legend(fontsize=7, loc="upper left")
    fig.suptitle("Decoder ablation, d = 5 (mean +/- std over seeds)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def make_all(results: Path, figures: Path) -> None:
    """Create all figures from the saved CSV files."""
    figures.mkdir(exist_ok=True)
    main = pd.read_csv(results / "main_scaling.csv", dtype={"period": str})
    grid = pd.read_csv(results / "phase_grid.csv", dtype={"period": str})
    best = pd.read_csv(results / "phase_grid_best.csv", dtype={"best_period": str})
    agg = pd.read_csv(results / "main_scaling_agg.csv", dtype={"period": str})
    fig_ecdf(grid, figures / "fig1_schedule_ecdf.png")
    fig_violin(main, figures / "fig2_seed_spread.png")
    fig_phase(best, figures / "fig3_phase_check_cost.png")
    fig_scaling(agg, figures / "fig4_distance_scaling.png")
    fig_decoders(main, figures / "fig5_decoder_ablation.png")
