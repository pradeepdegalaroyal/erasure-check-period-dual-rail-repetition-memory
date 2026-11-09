# Method

## Memory and noise model

A bit-flip repetition code with `d` dual-rail data qubits stores one logical bit for `R = 2d` rounds. Each round measures the `d - 1` neighbour parities (syndrome extraction takes 1 microsecond) and the memory ends with a transversal data readout. Time is in microseconds and rates in 1/microsecond.

* **Erasure.** A healthy qubit is erased at rate `lam`. An erased qubit scrambles its stored bit (flip with probability 1/2) in every round until a check detects it and resets it.
* **Pauli noise.** A healthy qubit flips with probability `0.5 (1 - exp(-2 gamma t))` in a round of duration `t`. Each syndrome bit is wrong with probability `p_meas`.
* **Erasure check.** A check at the start of syndrome extraction detects an erased qubit with efficiency `eta`, flags a healthy qubit with probability `fp`, lasts `tau_c` and flips every qubit with probability `p_check`. A detected qubit is reset. The final data readout acts as one free check.
* **Schedule.** The check period `m` places a check in every `m`-th round (`m = 1` is the standard "check every round"; `none` never checks). A round with a check lasts `1 + tau_c` microseconds, so a larger `m` saves time but lets erasures live longer.

## Decoders

All decoders are exact minimum-weight space-time decoders (a Viterbi recursion over the `2^d` accumulated-error states, equivalent to minimum-weight perfect matching on the repetition-code space-time graph) and differ only in the edge probabilities `p` (weights `ln((1-p)/p)`):

| Name | Edge probability |
|---|---|
| `blind` | per-round flip probability, flags ignored (standard erasure-agnostic matching) |
| `flat_uncal` | `p = 1/2` in a flagged window, nominal Pauli rate elsewhere |
| `flat` | `p = 1/2` in a flagged window, calibrated rate elsewhere |
| `graded` | calibrated flip probability for each position `c` in a window of length `W` (the proposed decoder) |
| `oracle` | `p = 1/2` exactly where the qubit was erased (upper bound) |

A flag at a check covers all rounds since the previous check, because the decoder does not know when the erasure happened. Calibration uses an independent sample of the same noise model (8000 shots in the scaling study, 4000 in the grid and sweeps).

## Baselines

* **Classical:** majority vote of the final data readout, with no syndrome information.
* **Standard quantum:** the check-every-round schedule (`m = 1`) with erasure-agnostic minimum-weight matching (`blind`), and the same schedule with the flat heralded-erasure decoder.
* **Physical reference:** an unencoded qubit with no reset has rate `gamma + lam / 2`.

## Metrics

Logical failure probability per configuration, converted to a logical error rate per microsecond with `1 - 2P = exp(-2 eps T)`, where `T` is the summed round duration. Means and standard deviations are over seeds. Schedule comparisons are paired by seed and call a gain significant if it exceeds two standard errors.

## Experiments

1. **Distance scaling** (`d = 3, 5, 7`, five seeds, 20 000 / 12 000 / 4 000 shots per seed) for a cheap-check device (0.5 microsecond, 0.5 % back-action) and a costly-check device (2 microseconds, 2 % back-action), periods 1, 2, 3, 5 and none.
2. **Ablation:** the five decoders above at `d = 5`.
3. **Robustness sweep:** a 5 x 5 grid of check duration (0.25 to 4 microseconds) and back-action (0.2 % to 4 %) at `d = 5` for periods 1, 2, 3, 4, 6 (three seeds, 8000 shots), plus sweeps of detection efficiency (0.5 to 0.99) and erasure rate (0.02 to 0.2 per microsecond) for the costly-check device.

Seeds fix both the calibration sample and the evaluation sample. Everything runs on a CPU in about ten minutes.
