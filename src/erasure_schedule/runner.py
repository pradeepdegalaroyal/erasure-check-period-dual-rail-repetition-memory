"""Run one (distance, schedule, noise) configuration and convert to a rate."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .decoder import calibrate_priors, decode_failures, majority_vote_failures
from .model import NoiseParams, sample_shots


@dataclass
class RunResult:
    """Logical failure probabilities and rates for one configuration and seed."""

    p_fail: dict            # decoder name -> logical failure probability
    rate_per_us: dict       # decoder name -> logical error rate per microsecond
    total_time: float       # duration of the memory experiment (us)


def logical_rate_per_us(p_fail: float, total_time: float) -> float:
    """Decay rate eps defined by 1 - 2 P = exp(-2 eps T)."""
    x = 1.0 - 2.0 * min(max(p_fail, 0.0), 0.5 - 1e-9)
    return float(-np.log(x) / (2.0 * total_time))


def run_config(
    d: int,
    rounds: int,
    period: int | None,
    params: NoiseParams,
    shots: int,
    seed: int,
    modes: tuple = ("blind", "flat", "graded", "oracle"),
    calib_shots: int = 8000,
    majority: bool = False,
) -> RunResult:
    """Simulate, calibrate priors on an independent sample, and decode."""
    rng_cal = np.random.default_rng([seed, 1])
    rng_run = np.random.default_rng([seed, 2])
    cal = sample_shots(d, rounds, period, params, calib_shots, rng_cal)
    pri = calibrate_priors(cal, params.p_meas)
    smp = sample_shots(d, rounds, period, params, shots, rng_run)
    pf: dict = {}
    for m in modes:
        pf[m] = float(decode_failures(smp, pri, m).mean())
    if majority:
        pf["majority"] = float(majority_vote_failures(smp).mean())
    rates = {k: logical_rate_per_us(v, smp.total_time) for k, v in pf.items()}
    return RunResult(p_fail=pf, rate_per_us=rates, total_time=smp.total_time)
