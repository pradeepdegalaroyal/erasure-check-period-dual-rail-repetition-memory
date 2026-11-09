# Research gap: how often should a dual-rail memory check for erasures?

## State of the art (from the supplied literature)

Quantum error correction (QEC) has moved from principle to repeated experiment. Acharya et al. (2023, doi:10.1038/s41586-022-05434-1) showed a distance-5 surface code that modestly beats distance-3 codes, and Zobrist et al. (2025, doi:10.1038/s41586-024-08449-y) reached a below-threshold factor of 2.14 per distance step with a real-time decoder, finding that rare correlated events limit repetition codes. Sivak et al. (2023, doi:10.1038/s41586-023-05782-6) beat break-even with a logical qubit whose cycle itself adds errors, and Bluvstein et al. (2024, doi:10.1038/s41586-023-06927-3) combined logical qubits with error detection on a neutral-atom processor. Bravyi et al. (2024, doi:10.1038/s41586-024-07107-7) proposed quantum low-density parity-check (qLDPC) memories with a 0.7 % threshold, and Bartolucci et al. (2023, doi:10.1038/s41467-023-36493-1) built a fault-tolerant model around photon loss, which is an erasure error. On the theory side, Matsumoto (2027, doi:10.1007/s40314-026-03881-4) states that measurements are costly and error-prone, and formalises which stabilisers a decoder can omit after an erasure.

## Related work

| Paper | Year | Role | What it does | What it does NOT cover |
|---|---|---|---|---|
| Acharya et al., doi:10.1038/s41586-022-05434-1 | 2023 | landmark | Distance-3 to 5 surface-code scaling, error budgets | Erasure heralding or a choice of check schedule |
| Zobrist et al., doi:10.1038/s41586-024-08449-y | 2025 | landmark | Below-threshold memories, real-time decoding | Heralded erasures; cost of extra checks |
| Sivak et al., doi:10.1038/s41586-023-05782-6 | 2023 | landmark | Break-even logical qubit with learned control | Erasure checks inside the cycle |
| Bluvstein et al., doi:10.1038/s41586-023-06927-3 | 2024 | landmark | Logical processor with detection codes on 280 atoms | Schedule of detection versus cost in time |
| Bravyi et al., doi:10.1038/s41586-024-07107-7 | 2024 | landmark | qLDPC memory, 0.7 % circuit threshold | Erasure-aware cycle design |
| Bartolucci et al., doi:10.1038/s41467-023-36493-1 | 2023 | landmark | Fusion-based computation tolerating 10.4 % fusion loss | Imperfect loss detection that costs time |
| Evered et al., doi:10.1038/s41586-023-06481-y | 2023 | adjacent | 99.5 % parallel entangling gates on 60 atoms | Error-correction schedules |
| Kim et al., doi:10.1038/s41586-023-06096-3 | 2023 | adjacent | Noisy 127-qubit utility experiment without QEC | Fault-tolerant cycles |
| Matsumoto, doi:10.1007/s40314-026-03881-4 | 2027 | recent | Formalises which stabilisers erasure recovery needs | Time cost of erasure checks, their misses and decoder priors |
| Wang et al., doi:10.15302/frontphys.2027.023301 | 2027 | review | Variational algorithms across early and full fault tolerance | Concrete check schedules |
| Fisher et al., doi:10.1146/annurev-conmatphys-031720-030658 | 2023 | review | Random and monitored circuits, measurement-induced transitions | Hardware-timed check schedules |
| Das and Dash, doi:10.1007/978-3-032-35516-4_32 | 2027 | recent | Qiskit quantum Hamming encoder/decoder, T-count | Erasure information; noise model |
| Kong, doi:10.1007/978-3-032-39708-9_31 | 2027 | recent | Learned error mitigation on noisy devices | Active error correction with erasure flags |

## Gap

The experiments above treat every syndrome round as the unit of error correction. The erasure-aware proposals treat a heralded erasure as free information (flags come with every round) and the theory work reduces *stabiliser* measurements, not the *erasure checks* that a dual-rail device performs in addition to them. On a multimode superconducting device, a check takes time, adds back-action, misses a fraction of erasures and, between checks, an undetected erased qubit keeps scrambling the syndrome. The check period is therefore a design variable with a trade-off, and the supplied papers do not report how a decoder should be built for it or where "check every round" stops being optimal.

**Novelty (one sentence).** We treat the erasure-check period as the optimisation variable of a concatenated detection-plus-repetition-code memory, supply an exact calibrated decoder that handles flag windows of unknown erasure time, and map where checking less often than every round lowers the logical error rate per unit time.

## Hypotheses and success metrics

* **H1.** For a device with imperfect checks (detection efficiency below 1) and non-zero check cost, the logical error rate per microsecond has its minimum at a check period larger than one round in a non-empty region of the (check duration, check back-action) plane. *Falsified* if no cell of the swept plane shows a paired-seed gain of at least two standard errors (SE) for any period above one.
* **H2.** A decoder whose priors inside a flagged window depend on the position in the window ("graded") lowers the logical failure probability relative to a flat zero-weight window with calibrated priors elsewhere, increasingly so for longer periods. *Falsified* if the paired gain is not positive at periods of 3 and 5.
* **Metric.** Logical error rate per microsecond, defined by 1 - 2P = exp(-2 eps T), mean and standard deviation over seeds, with paired-seed standard errors for comparisons.

## Scale and honesty

This is a classical simulation of a bit-flip repetition code with distances 3 to 7 and phenomenological noise. It tests the *scheduling question* and the decoder design, not a hardware claim, and it does not model correlated errors, leakage beyond the erased state, or the full surface code.
