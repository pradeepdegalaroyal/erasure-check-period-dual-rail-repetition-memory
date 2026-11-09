"""Reproduce every result: python experiments/run_all.py [--quick]

Writes results/*.csv and results/summary.json, then calls make_figures.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from erasure_schedule import NoiseParams, run_config  # noqa: E402

NOMINAL = NoiseParams(lam=0.06, gamma=0.004, p_meas=0.02, eta=0.8, fp=0.01, p_check=0.005, tau_c=0.5)
SCENARIOS = {
    "cheap_check": NOMINAL,                                    # 0.5 us, 0.5 % back-action
    "costly_check": NOMINAL.with_(tau_c=2.0, p_check=0.02),    # 2 us, 2 % back-action
}
PERIODS = (1, 2, 3, 5, None)
PERIOD_LABEL = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", None: "none"}


def main_scaling(cfg: dict, out: Path) -> pd.DataFrame:
    """Distance scaling for both check-cost scenarios, all decoders and baselines."""
    rows = []
    for scen, params in SCENARIOS.items():
        for d in cfg["distances"]:
            shots = cfg["shots_d"][d]
            modes = ("blind", "flat_uncal", "flat", "graded", "oracle") if d <= 5 else ("flat", "graded")
            for period in PERIODS:
                for seed in range(cfg["seeds"]):
                    t0 = time.time()
                    res = run_config(d, 2 * d, period, params, shots, seed, modes=modes,
                                     majority=(d <= 5))
                    for dec, pf in res.p_fail.items():
                        rows.append(dict(scenario=scen, d=d, rounds=2 * d, period=PERIOD_LABEL[period],
                                         seed=seed, decoder=dec, shots=shots, p_fail=pf,
                                         rate_per_us=res.rate_per_us[dec], total_time_us=res.total_time))
                print(f"  main {scen} d={d} period={period} done ({time.time() - t0:.1f}s/seed)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "main_scaling.csv", index=False)
    return df


def phase_grid(cfg: dict, out: Path) -> pd.DataFrame:
    """Check duration x check back-action grid at d = 5; best schedule per cell."""
    rows = []
    for tau in cfg["tau_grid"]:
        for pc in cfg["pc_grid"]:
            params = NOMINAL.with_(tau_c=tau, p_check=pc)
            for period in cfg["grid_periods"]:
                for seed in range(cfg["grid_seeds"]):
                    res = run_config(5, 10, period, params, cfg["grid_shots"], 100 + seed,
                                     modes=("graded",), calib_shots=4000)
                    rows.append(dict(tau_c=tau, p_check=pc, period=PERIOD_LABEL[period], seed=seed,
                                     p_fail=res.p_fail["graded"], rate_per_us=res.rate_per_us["graded"],
                                     total_time_us=res.total_time))
        print(f"  grid tau_c={tau} done", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "phase_grid.csv", index=False)
    return df


def sweeps(cfg: dict, out: Path) -> pd.DataFrame:
    """Detection-efficiency and erasure-rate sweeps for the costly-check device, d = 5."""
    rows = []
    base = SCENARIOS["costly_check"]
    for name, values in (("eta", cfg["eta_sweep"]), ("lam", cfg["lam_sweep"])):
        for v in values:
            params = base.with_(**{name: v})
            for period in cfg["grid_periods"]:
                for seed in range(cfg["grid_seeds"]):
                    res = run_config(5, 10, period, params, cfg["grid_shots"], 200 + seed,
                                     modes=("graded",), calib_shots=4000)
                    rows.append(dict(sweep=name, value=v, period=PERIOD_LABEL[period], seed=seed,
                                     p_fail=res.p_fail["graded"], rate_per_us=res.rate_per_us["graded"]))
        print(f"  sweep {name} done", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "sweeps.csv", index=False)
    return df


def _agg(df: pd.DataFrame, keys: list, col: str = "rate_per_us") -> pd.DataFrame:
    g = df.groupby(keys)[col].agg(["mean", "std", "count"]).reset_index()
    return g


def paired_gain(df: pd.DataFrame, keys: list, ref: str = "1") -> pd.DataFrame:
    """For every setting, the best period vs the reference period with paired-seed statistics."""
    out = []
    for key, sub in df.groupby(keys):
        piv = sub.pivot_table(index="seed", columns="period", values="rate_per_us")
        means = piv.mean()
        best = means.idxmin()
        diff = (piv[ref] - piv[best]) / piv[ref]
        n = len(diff)
        se = float(diff.std(ddof=1) / np.sqrt(n)) if n > 1 and best != ref else 0.0
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, key))
        row.update(best_period=best, eps_ref=float(means[ref]), eps_best=float(means[best]),
                   gain=float(diff.mean()), gain_se=se,
                   significant=bool(best != ref and diff.mean() > 2 * se))
        out.append(row)
    return pd.DataFrame(out)


def summarise(main: pd.DataFrame, grid: pd.DataFrame, sw: pd.DataFrame, cfg: dict, out: Path) -> dict:
    """Aggregate raw results into the headline numbers quoted in the README."""
    summ: dict = {"config": cfg}
    agg = _agg(main, ["scenario", "d", "period", "decoder"])
    agg.to_csv(out / "main_scaling_agg.csv", index=False)
    summ["main_agg"] = agg.to_dict(orient="records")

    sub = main[(main.decoder == "graded") | (main.decoder == "flat")]
    sub = sub[sub.decoder == "graded"]
    pg = paired_gain(sub, ["scenario", "d"])
    pg.to_csv(out / "main_best_period.csv", index=False)
    summ["best_period_graded"] = pg.to_dict(orient="records")

    gg = paired_gain(grid, ["tau_c", "p_check"])
    gg.to_csv(out / "phase_grid_best.csv", index=False)
    summ["phase_cells"] = int(len(gg))
    summ["phase_cells_significant_gain"] = int(gg.significant.sum())
    summ["phase_max_gain"] = float(gg.gain.max())
    summ["phase_cells_best_gt1"] = int((gg.best_period != "1").sum())

    sg = paired_gain(sw, ["sweep", "value"])
    sg.to_csv(out / "sweeps_best.csv", index=False)
    summ["sweep_best"] = sg.to_dict(orient="records")

    # decoder ablation at d = 5 (paired against the flat-window decoder)
    abl = []
    for scen in SCENARIOS:
        for period in PERIOD_LABEL.values():
            s = main[(main.scenario == scen) & (main.d == 5) & (main.period == period)]
            if s.empty:
                continue
            piv = s.pivot_table(index="seed", columns="decoder", values="rate_per_us")
            for dec in piv.columns:
                if dec == "flat":
                    continue
                diff = (piv["flat"] - piv[dec]) / piv["flat"]
                abl.append(dict(scenario=scen, period=period, decoder=dec, rel_gain_vs_flat=float(diff.mean()),
                                se=float(diff.std(ddof=1) / np.sqrt(len(diff)))))
    pd.DataFrame(abl).to_csv(out / "decoder_ablation.csv", index=False)
    summ["decoder_ablation"] = abl

    eps_phys = NOMINAL.gamma + NOMINAL.lam / 2.0
    summ["eps_phys_unencoded_per_us"] = eps_phys
    with open(out / "summary.json", "w") as fh:
        json.dump(summ, fh, indent=2, default=float)
    return summ


def get_config(quick: bool) -> dict:
    if quick:
        return dict(quick=True, seeds=2, distances=[3, 5], shots_d={3: 1500, 5: 800}, grid_seeds=2,
                    grid_shots=500, tau_grid=[0.5, 2.0], pc_grid=[0.005, 0.02], grid_periods=[1, 2, 3],
                    eta_sweep=[0.6, 0.95], lam_sweep=[0.03, 0.1])
    return dict(quick=False, seeds=5, distances=[3, 5, 7], shots_d={3: 20000, 5: 12000, 7: 4000},
                grid_seeds=3, grid_shots=8000, tau_grid=[0.25, 0.5, 1.0, 2.0, 4.0],
                pc_grid=[0.002, 0.005, 0.01, 0.02, 0.04], grid_periods=[1, 2, 3, 4, 6],
                eta_sweep=[0.5, 0.7, 0.9, 0.99], lam_sweep=[0.02, 0.06, 0.12, 0.2])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="under-one-minute smoke run")
    args = ap.parse_args()
    cfg = get_config(args.quick)
    out = ROOT / ("results_quick" if args.quick else "results")
    out.mkdir(exist_ok=True)
    t0 = time.time()
    print("[1/3] distance scaling", flush=True)
    main_df = main_scaling(cfg, out)
    print("[2/3] check-cost phase grid", flush=True)
    grid_df = phase_grid(cfg, out)
    print("[3/3] efficiency and erasure-rate sweeps", flush=True)
    sw_df = sweeps(cfg, out)
    summ = summarise(main_df, grid_df, sw_df, cfg, out)
    summ_runtime = time.time() - t0
    summ["runtime_s"] = summ_runtime
    with open(out / "summary.json", "w") as fh:
        json.dump(summ, fh, indent=2, default=float)
    import make_figures
    make_figures.make_all(out, ROOT / ("figures_quick" if args.quick else "figures"))
    print(f"done in {summ_runtime:.0f}s -> {out}")


if __name__ == "__main__":
    main()
