"""Erasure-check scheduling for a dual-rail repetition-code memory."""

from .model import NoiseParams, Sample, check_rounds, round_durations, sample_shots
from .decoder import (
    DECODER_MODES,
    Priors,
    calibrate_priors,
    decode_failures,
    majority_vote_failures,
)
from .runner import RunResult, logical_rate_per_us, run_config

__all__ = [
    "NoiseParams",
    "Sample",
    "check_rounds",
    "round_durations",
    "sample_shots",
    "DECODER_MODES",
    "Priors",
    "calibrate_priors",
    "decode_failures",
    "majority_vote_failures",
    "RunResult",
    "logical_rate_per_us",
    "run_config",
]

__version__ = "0.1.0"
