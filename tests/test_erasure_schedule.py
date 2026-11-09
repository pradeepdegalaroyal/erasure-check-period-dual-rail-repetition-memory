"""Fast unit tests for the erasure-check scheduling package."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from erasure_schedule import (  # noqa: E402
    NoiseParams,
    calibrate_priors,
    check_rounds,
    decode_failures,
    logical_rate_per_us,
    majority_vote_failures,
    round_durations,
    run_config,
    sample_shots,
)
from erasure_schedule.model import syndrome_of  # noqa: E402


def test_check_rounds_and_durations():
    assert check_rounds(6, 2) == (1, 3, 5)
    assert check_rounds(6, None) == ()
    p = NoiseParams(t_round=1.0, tau_c=0.5)
    t = round_durations(6, check_rounds(6, 3), p)
    assert np.allclose(t, [1, 1, 1.5, 1, 1, 1.5])


def test_syndrome_of_repetition_code():
    # state 0b0110 on 4 qubits: bits (q0..q3) = 0,1,1,0 -> parities 1,0,1
    assert int(syndrome_of(np.array([0b0110]), 4)[0]) == 0b101


def test_noiseless_memory_never_fails():
    p = NoiseParams(lam=0.0, gamma=0.0, p_meas=1e-9, p_check=0.0, fp=0.0)
    s = sample_shots(3, 4, 1, p, 200, np.random.default_rng(0))
    assert not s.flips.any()
    pri = calibrate_priors(s, 1e-9)
    assert decode_failures(s, pri, "graded").sum() == 0


def test_oracle_decoder_not_worse_than_blind():
    p = NoiseParams(lam=0.08, gamma=0.003, eta=0.8)
    rng = np.random.default_rng(1)
    cal = sample_shots(5, 8, 2, p, 4000, rng)
    pri = calibrate_priors(cal, p.p_meas)
    s = sample_shots(5, 8, 2, p, 4000, rng)
    fo = decode_failures(s, pri, "oracle").mean()
    fb = decode_failures(s, pri, "blind").mean()
    assert fo <= fb


def test_decoder_beats_majority_vote_for_syndrome_information():
    p = NoiseParams(lam=0.0, gamma=0.03, p_meas=0.01, eta=1.0, p_check=0.0)
    rng = np.random.default_rng(2)
    cal = sample_shots(5, 10, 1, p, 4000, rng)
    pri = calibrate_priors(cal, p.p_meas)
    s = sample_shots(5, 10, 1, p, 4000, rng)
    assert decode_failures(s, pri, "flat").mean() < majority_vote_failures(s).mean()


def test_rate_conversion_and_runner():
    assert abs(logical_rate_per_us(0.0, 10.0)) < 1e-12
    r = run_config(3, 4, 2, NoiseParams(), 300, 0, modes=("flat", "graded"), calib_shots=300)
    assert set(r.p_fail) == {"flat", "graded"}
    assert all(0.0 <= v <= 1.0 for v in r.p_fail.values())
    assert r.total_time > 0
