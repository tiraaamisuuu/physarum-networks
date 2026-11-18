# Exploratory growth controls — 18 November 2026

**The cooperative variant grows through the arena and supports oscillatory internal flow. Its vein geometry remains numerically sensitive and does not quantitatively reproduce the source experiment.** This report distinguishes numerical verification and replay from biological validation.

Model equations, source-expression ambiguities, the explicitly restored Hill exponent and the faster default front timescale are documented in [the biological model guide](../../docs/BIOLOGICAL_GROWTH.md). The model is based on Schenz et al. (2017), [DOI 10.1088/1361-6463/aa88e9](https://doi.org/10.1088/1361-6463/aa88e9), with a cooperative response motivated by Smith & Saldana (1992), [DOI 10.1016/S0006-3495(92)81843-X](https://doi.org/10.1016/S0006-3495(92)81843-X). Neither complete original model is claimed as exactly reproduced.

## Controlled cases

Common inputs unless stated: bent corridor of area 350, seed 42, spacing 0.5, 1,643 nodes and 4,626 edges, duration 1280, Δt = 0.02, β = 4, front timescale τ₂ = 2, k = 0.01. Chemical timescale τ₁ = 0.0072, divided by three in the inoculum. Full fields save every 8 time units; the fixed inoculum probe and an incident edge save every integration step. Length measurements use D ≥ 1. This is an explicit analysis cutoff, not numerical pruning or a calibrated visible-vein threshold.

| Case | Change | Final occupied area | Far target first reached¹ | Retained vein length |
| :--- | :--- | ---: | ---: | ---: |
| Default cooperative variant | — | 350.000 | 528 | 25.469 |
| Source front timescale | τ₂ = 20 | 61.023 | Not reached | 9.944 |
| Half step | Δt = 0.01 | 350.000 | 528 | 33.439 |
| Finer mesh | h = 0.4; 2,515 nodes / 7,163 edges | 350.000 | 536 | 49.200 |
| No vein-to-front feedback | k = 0 | 350.000 | 528 | 25.469 |
| Printed calcium expression | β = 1 | 350.000 | 528 | 0.000 |

¹ A passive geometric target x ≤ 1, y ≥ 10. This is **not a food source** and exerts no attraction. Contact is detected only at the recorded full-field times, so temporal uncertainty is up to 8 model units. Occupied area is lumped-node quadrature of w > 1. Time and length are uncalibrated.

All six final occupied footprints contain one node-graph component. This says nothing by itself about connectivity of the retained vein graph. The default retained veins do not provide a uniformly maintained connection throughout the explored body.

The printed-expression control's final D maximum is approximately 7 × 10⁻¹⁴. The autonomous growth equations still produce a footprint while its veins disappear. This separates advancing-front behaviour from sustained vein formation. In the cooperative default the final-80-unit inoculum calcium range is 6.40238–7.64593, with a median sampled peak period of 1.02 model units. The incident-edge flow ranges from −0.01391 to +0.00394, demonstrating reversals at that specific probe.

Disabling k changes some recorded fields slightly (maximum saved w difference 0.07617, D difference 0.18952), but leaves the reported final length and sampled contact time unchanged. This is weak feedback in the tested variant, **not positive validation of the intended feedback mechanism**.

## Numerical sensitivity

Halving Δt changes final retained length by **+31.3%**. Maximum differences across the common saved states include w = 0.04453 and D = 407.395. The calcium phase also drifts over the long interval. A finer mesh changes retained length by approximately **+93.2%**. The mesh changes the discrete fluid network as well as the finite-element approximation, so this is not a clean continuum-convergence test.

The source-front-timescale control covers only 17.44% of the arena by the endpoint. The default fast-front variant covers it, but neither its surviving-vein geometry nor the intended strong feedback reproduces the published centre-in-centre morphology quantitatively. No error band against microscopy or calibrated biological time is claimed.

All recorded states preserve nonnegative u, v, w and D, and monotone w. At every saved state in every case, conductivity is exactly zero on initially empty edges that have never passed the body gate. Seed-incident conductivities are exempt because the published initialisation assigns them D = 0.1 even before w accumulates.

Maximum absolute momentum/storage residual over the cooperative cases is 6.17 × 10⁻¹²; the nonoscillating control reaches 6.64 × 10⁻¹⁰ as its spatially uniform pressure component grows. The frozen-coefficient fluid energy-identity defect is at most 1.63 × 10⁻¹⁰ across these cases. This substep identity is not whole-organism energy conservation.

## Replay and preserved evidence

[validation.json](validation.json) records settings, geometry sizes, outcomes, residuals and source fingerprints. Each directory under [replay/](replay/) preserves:

- Exact nodes, edge lengths, finite-element weights, triangles and inoculum membership.
- The original scenario and engine metadata, bound to the compiled C++/header/CMake fingerprint.
- A deterministic source archive, with its per-file source hashes in the scenario.
- The complete full-rate probe and full slow history as gzip-compressed CSV.
- Nine sampled states of **all eight fields** in `reference.npz`, including their indices/times.
- `reference-files.json`, hashing the archived artifacts.

The scenario's original `files` checksums refer to the complete local run; the compact public archive intentionally omits most full-rate spatial states. It is a replay package, not an incomplete folder for `load_biology`. The dedicated replay command reconstructs them:

```sh
# Build the frozen code rather than assuming the current executable matches.
.venv/bin/python analysis/replay_biology_case.py results/biology_validation/replay/default --build-source
# Re-run all six controls, preserving complete new local records and updating references.
.venv/bin/python analysis/validate_biology.py
# Regenerate the two public scientific figures using only the frozen references.
.venv/bin/python analysis/plot_biology.py
```

The default source-built replay on the development platform reproduced c, φ, u, v, w, p, q and D at every archived time with **zero absolute difference**. Its complete probe and history files were **byte-identical**. [Replay output](../../results/verification/biology-source-replay.txt). This is evidence of source/record reproducibility on that platform, not a cross-platform bitwise guarantee.

Verification: **33 CTests in Release and Debug/UBSan; 78 Python tests**. The suite includes an independently calculated front-system invariant, a separate NumPy solution of the compliant pressure/flow system with unequal edge lengths, body-gate checks, source/file integrity and native widget frame synchronization. [Release log](../verification/biology-ctest-release.txt), [UBSan log](../verification/biology-ctest-ubsan.txt), [Python log](../verification/biology-python-tests.txt).

Original copyrighted papers and experimental photographs are not included. The figures are generated from the project's own numerical fields. Food response, finite biomass, retraction and quantitative experimental validation remain outstanding biological work.
