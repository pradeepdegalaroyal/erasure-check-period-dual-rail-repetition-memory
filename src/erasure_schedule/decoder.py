"""Exact minimum-weight space-time decoder for the repetition-code memory.

The decoder is a Viterbi recursion over the 2**d accumulated-error states. Per
round the flip cost of every qubit is separable, so the min-plus transition is
applied one qubit at a time. This returns the same minimum-weight correction as
minimum-weight perfect matching on the repetition-code space-time graph, with
per-shot, per-qubit, per-round edge weights ln((1-p)/p). Zero-weight edges
(p = 1/2) encode heralded erasures.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import Sample, syndrome_of

DECODER_MODES = ("blind", "flat_uncal", "flat", "graded", "oracle")
_P_MIN = 1e-6


@dataclass
class Priors:
    """Calibrated flip probabilities used to build edge weights."""

    p_all: np.ndarray        # (R+1,) flip prob. per round, ignoring flags
    p_unflag: np.ndarray     # (R+1,) flip prob. per round given not in a flagged window
    p_window: dict           # (offset c, window length W) -> flip prob.
    p_nonerased: np.ndarray  # (R+1,) flip prob. per round given not erased (oracle)
    p_meas: float


def _windows(s: Sample) -> tuple[np.ndarray, np.ndarray]:
    """Flagged windows: offset ``c`` of each (shot, qubit, round) inside a window.

    A flag raised at check round r_c covers the rounds since the previous
    check (or the start), so c = r_c - j for round j; -1 means the entry is not
    inside any flagged window. The second array holds the window length W.
    """
    win_c = np.full(s.flags.shape, -1, dtype=np.int16)
    win_w = np.zeros(s.flags.shape, dtype=np.int16)
    prev = -1
    for r_c in list(s.checks) + [s.rounds]:
        f = s.flags[:, :, r_c]
        for j in range(prev + 1, r_c + 1):
            win_c[:, :, j] = np.where(f, r_c - j, -1)
            win_w[:, :, j] = np.where(f, r_c - prev, 0)
        prev = r_c
    return win_c, win_w


def calibrate_priors(s: Sample, p_meas: float) -> Priors:
    """Estimate the edge priors from an independent calibration sample."""
    win_c, win_w = _windows(s)
    f = s.flips
    inwin = win_c >= 0
    p_all = f.mean(axis=(0, 1))
    cnt_un = np.maximum((~inwin).sum(axis=(0, 1)), 1)
    p_un = (f & ~inwin).sum(axis=(0, 1)) / cnt_un
    cnt_ne = np.maximum((~s.erased).sum(axis=(0, 1)), 1)
    p_ne = (f & ~s.erased).sum(axis=(0, 1)) / cnt_ne
    table: dict = {}
    for w in np.unique(win_w[inwin]):
        for c in range(int(w)):
            m = inwin & (win_c == c) & (win_w == w)
            n = int(m.sum())
            table[(c, int(w))] = float(f[m].mean()) if n >= 20 else 0.5
    return Priors(p_all=p_all, p_unflag=p_un, p_window=table, p_nonerased=p_ne, p_meas=p_meas)


def _edge_probs(s: Sample, pri: Priors, mode: str, p_nominal: np.ndarray) -> np.ndarray:
    """Per-shot, per-qubit, per-round flip probabilities for the chosen decoder."""
    shots, d, r1 = s.flips.shape
    j = np.arange(r1)[None, None, :]
    if mode == "blind":
        p = np.broadcast_to(pri.p_all[j], (shots, d, r1)).copy()
    elif mode == "oracle":
        p = np.where(s.erased, 0.5, pri.p_nonerased[j])
    else:
        win_c, win_w = _windows(s)
        inwin = win_c >= 0
        if mode == "flat":
            p = np.where(inwin, 0.5, pri.p_unflag[j])
        elif mode == "flat_uncal":
            p = np.where(inwin, 0.5, p_nominal[j])
        elif mode == "graded":
            tab = np.full((r1 + 1, r1 + 1), 0.5)
            for (c, w), val in pri.p_window.items():
                tab[c, w] = val
            p = np.where(inwin, tab[np.maximum(win_c, 0), win_w], pri.p_unflag[j])
        else:
            raise ValueError(f"unknown decoder mode {mode!r}")
    return np.clip(p, _P_MIN, 0.5)


def decode_failures(
    s: Sample, pri: Priors, mode: str, p_nominal: np.ndarray | None = None
) -> np.ndarray:
    """Per-shot logical failure indicator (1.0 fail, 0.5 tie, 0.0 success)."""
    d, rounds = s.d, s.rounds
    if p_nominal is None:
        p_nominal = s.p_flip_nominal
    p = _edge_probs(s, pri, mode, p_nominal)
    w = np.log((1.0 - p) / p)                                  # (S, d, R+1)
    shots = w.shape[0]
    n_states = 1 << d
    states = np.arange(n_states)
    hmat = syndrome_of(states, d)
    popcnt = np.array([bin(x).count("1") for x in range(1 << (d - 1))], dtype=np.float64)
    w_m = float(np.log((1.0 - pri.p_meas) / pri.p_meas))
    flip_idx = [states ^ (1 << q) for q in range(d)]

    cost = np.full((shots, n_states), 1e9)
    cost[:, 0] = 0.0
    for r in range(rounds):
        for q in range(d):
            cost = np.minimum(cost, cost[:, flip_idx[q]] + w[:, q, r][:, None])
        mism = popcnt[hmat[None, :] ^ s.syndromes[:, r][:, None]]
        cost = cost + w_m * mism
    for q in range(d):
        cost = np.minimum(cost, cost[:, flip_idx[q]] + w[:, q, rounds][:, None])

    rows = np.arange(shots)
    all_ones = n_states - 1
    c_true = cost[rows, s.final_state]
    c_alt = cost[rows, s.final_state ^ all_ones]
    tol = 1e-7
    return np.where(c_alt < c_true - tol, 1.0, np.where(c_alt > c_true + tol, 0.0, 0.5))


def majority_vote_failures(s: Sample) -> np.ndarray:
    """Classical baseline: majority vote of the final data readout, no syndromes."""
    d = s.d
    ones = np.array([bin(int(x)).count("1") for x in s.final_state])
    return np.where(2 * ones > d, 1.0, np.where(2 * ones == d, 0.5, 0.0))
