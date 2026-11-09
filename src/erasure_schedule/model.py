"""Circuit-level-flavoured noise model of a dual-rail repetition-code memory.

Every data qubit is a dual-rail qubit that can be *erased* (photon loss or
leakage out of the encoding). An erased qubit scrambles its stored bit in every
round until an erasure check detects it and resets it. A check is imperfect
(detection efficiency ``eta``, false-positive rate ``fp``), takes time ``tau_c``
and adds a small bit-flip ``p_check`` to every qubit. The schedule decides in
which rounds a check is performed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np


@dataclass(frozen=True)
class NoiseParams:
    """Physical parameters. Times are in microseconds (us), rates in 1/us."""

    t_round: float = 1.0      # syndrome-extraction time per round (us)
    lam: float = 0.02         # erasure rate per data qubit (1/us)
    gamma: float = 0.002      # bit-flip rate of a healthy qubit (1/us)
    p_meas: float = 0.01      # syndrome-measurement flip probability
    eta: float = 0.9          # erasure-check detection efficiency
    fp: float = 0.005         # check false-positive probability on a healthy qubit
    tau_c: float = 0.5        # duration of one erasure check (us)
    p_check: float = 0.003    # extra bit-flip probability caused by one check

    def with_(self, **kw: float) -> "NoiseParams":
        """Return a copy with some fields replaced."""
        return replace(self, **kw)


@dataclass
class Sample:
    """Simulated memory experiments (S shots, d data qubits, R rounds).

    Arrays with a last axis of length ``R + 1`` use index ``R`` for the final
    transversal data readout.
    """

    d: int
    rounds: int
    checks: tuple[int, ...]            # 0-based rounds that contain a check
    flips: np.ndarray                  # (S, d, R+1) bool, X flips applied
    erased: np.ndarray                 # (S, d, R+1) bool, qubit erased in that round
    flags: np.ndarray                  # (S, d, R+1) bool, flag raised at a check / readout
    syndromes: np.ndarray              # (S, R) int, measured syndrome bit-strings
    final_syndrome: np.ndarray         # (S,) int, syndrome of the read-out data bits
    final_state: np.ndarray            # (S,) int, bit-string of accumulated X errors
    durations: np.ndarray              # (R,) round durations (us)
    p_flip_nominal: np.ndarray         # (R+1,) healthy-qubit flip probability per round

    @property
    def total_time(self) -> float:
        """Wall-clock duration of the R syndrome rounds (us)."""
        return float(self.durations.sum())


def check_rounds(rounds: int, period: int | None) -> tuple[int, ...]:
    """Rounds (0-based) carrying an erasure check for check period ``period``.

    ``period=None`` means the memory never checks (only the free final readout).
    """
    if period is None:
        return ()
    return tuple(r for r in range(rounds) if (r + 1) % period == 0)


def round_durations(rounds: int, checks: tuple[int, ...], p: NoiseParams) -> np.ndarray:
    """Duration of each round: syndrome extraction plus a check where scheduled."""
    t = np.full(rounds, p.t_round, dtype=float)
    for r in checks:
        t[r] += p.tau_c
    return t


def _xor_prob(a: np.ndarray, b: float | np.ndarray) -> np.ndarray:
    """Probability that exactly one of two independent flips happens."""
    return a + b - 2.0 * a * b


def sample_shots(
    d: int,
    rounds: int,
    period: int | None,
    p: NoiseParams,
    shots: int,
    rng: np.random.Generator,
) -> Sample:
    """Sample ``shots`` memory experiments of ``rounds`` rounds on ``d`` qubits."""
    if d < 2 or d > 9:
        raise ValueError("d must be in 2..9 (state space is 2**d)")
    checks = check_rounds(rounds, period)
    durations = round_durations(rounds, checks, p)
    is_check = np.zeros(rounds, dtype=bool)
    is_check[list(checks)] = True

    p_erase = 1.0 - np.exp(-p.lam * durations)
    p_pauli = 0.5 * (1.0 - np.exp(-2.0 * p.gamma * durations))
    p_flip = _xor_prob(p_pauli, np.where(is_check, p.p_check, 0.0))

    flips = np.zeros((shots, d, rounds + 1), dtype=bool)
    erased_hist = np.zeros((shots, d, rounds + 1), dtype=bool)
    flags = np.zeros((shots, d, rounds + 1), dtype=bool)
    erased = np.zeros((shots, d), dtype=bool)

    for r in range(rounds):
        erased |= rng.random((shots, d)) < p_erase[r]
        scramble = rng.random((shots, d)) < 0.5
        healthy_flip = rng.random((shots, d)) < p_flip[r]
        flips[:, :, r] = np.where(erased, scramble, healthy_flip)
        erased_hist[:, :, r] = erased
        if is_check[r]:
            detect = erased & (rng.random((shots, d)) < p.eta)
            false_pos = ~erased & (rng.random((shots, d)) < p.fp)
            flags[:, :, r] = detect | false_pos
            erased = erased & ~detect

    # final transversal readout: free check, erased qubits read out at random
    erased_hist[:, :, rounds] = erased
    flips[:, :, rounds] = erased & (rng.random((shots, d)) < 0.5)
    detect = erased & (rng.random((shots, d)) < p.eta)
    false_pos = ~erased & (rng.random((shots, d)) < p.fp)
    flags[:, :, rounds] = detect | false_pos

    weights = (1 << np.arange(d)).astype(np.int64)
    cum = np.cumsum(flips, axis=2) % 2                      # (S, d, R+1) accumulated X
    states = (cum * weights[None, :, None]).sum(axis=1)     # (S, R+1) bit-string ints
    h = syndrome_of(states, d)
    meas_flip = rng.random((shots, rounds, d - 1)) < p.p_meas
    mf = (meas_flip * (1 << np.arange(d - 1))[None, None, :]).sum(axis=2)
    syndromes = h[:, :rounds] ^ mf
    return Sample(
        d=d,
        rounds=rounds,
        checks=checks,
        flips=flips,
        erased=erased_hist,
        flags=flags,
        syndromes=syndromes.astype(np.int64),
        final_syndrome=h[:, rounds].astype(np.int64),
        final_state=states[:, rounds].astype(np.int64),
        durations=durations,
        p_flip_nominal=np.append(p_flip, 0.0),
    )


def syndrome_of(states: np.ndarray, d: int) -> np.ndarray:
    """Parity-check syndrome (d-1 bits) of bit-string state(s) of length d."""
    states = np.asarray(states, dtype=np.int64)
    return (states ^ (states >> 1)) & ((1 << (d - 1)) - 1)
