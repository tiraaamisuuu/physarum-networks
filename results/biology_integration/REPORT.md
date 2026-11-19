# Coupled biological integration — 19 November 2026

**The midpoint/CN protocol substantially reduces numerical error while preserving the biological equations of the stated cooperative variant.** It is now the desktop default at Δt = 0.02. Food response, finite biomass and quantitative biological calibration remain unimplemented.

The [numerical contract](../../docs/BIOLOGICAL_INTEGRATION.md) describes the positive conductivity predictor, reaction–diffusion splitting, damped startup, midpoint fluid/body coupling and exponential conductivity update. [The biological guide](../../docs/BIOLOGICAL_GROWTH.md) documents the unresolved source-expression issues and the limits of this uncalibrated model.

## Matched full-corridor results

All cases preserve the **same exact frozen nodes, edges and triangles**, verified by CSV hashes against the earlier default. The arena has 1,643 nodes, 4,626 edges and area 350. Duration is 1280; full fields save every 8 time units. The cooperative exponent is 4, front timescale 2 and feedback 0.01. Only the integration method and step change. Every case uses compiled-source fingerprint `726ec1301ff2caeebadccf806f272d53a7ab577cacaaf47da6788551e4398c28`.

| Method | Δt | Final retained length, D ≥ 1 | Final-80-unit mean volume proxy | Difference from finest mean | Final edge-mask differences from finest |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Legacy split | 0.02 | 25.46897 | 643.73305 | −26.126% | 50 |
| Midpoint/CN | 0.04 | 33.22409 | 844.75471 | −3.056% | 2 |
| **Midpoint/CN, default** | **0.02** | **34.35667** | **866.20630** | **−0.595%** | **0** |
| Midpoint/CN | 0.01 | 34.35667 | 870.40801 | −0.113% | 0 |
| Midpoint/CN, finest reference | 0.005 | 34.35667 | 871.38855 | — | — |

The volume proxy is Σ ℓ√D, with uncalibrated units. Means integrate the **full-rate** data over model times 1200–1280, not the sparse spatial snapshots. The finest run is a numerical reference, not an exact solution.

At steps 0.02, 0.01 and 0.005, the final retained edge set is identical at D ≥ 1. Halving the default step changes the time-window mean volume by **0.485%**; halving again changes it by about **0.113%** relative to the finer value. These are finite checks at one mesh, one set of parameters and one cutoff. They do not establish universal morphology convergence.

All five cases explore the complete arena as one occupied footprint and first reach the passive far target at recorded time 528 (uncertainty up to the 8-unit field-save interval). The target is not a food source and exerts no attraction.

## Pointwise differences still matter

The archive compares nine common full-field sample times. The largest differences from the Δt = 0.005 reference include:

| Method / step | Calcium c | Body proxy w | Conductivity D |
| :--- | ---: | ---: | ---: |
| Legacy / 0.02 | 0.83642 | 0.08810 | 481.839 |
| Midpoint / 0.04 | 0.21606 | 0.00726 | 253.749 |
| Midpoint / 0.02 | 0.04812 | 0.00167 | 27.327 |
| Midpoint / 0.01 | 0.00927 | 0.000318 | 5.035 |

These are maxima **over the nine archived times**, not over every intermediate spatial state. The default and half-step runs therefore agree more closely in their final topology and mean volume than they do pointwise throughout the experiment. Coarse transient conductivity differences remain substantial. This distinction is important for interpreting an oscillatory nonlinear system.

The controlled three-node fixture shows finer-step error ratios approaching four for midpoint/CN and two for legacy. At Δt = 0.02, its scaled state error falls from 0.12824 to 0.006314, about a 20-fold reduction. The coarsest midpoint refinement ratio is only 1.659; it is not hidden. [Complete order table](smooth-order.csv). The fixture uses an approximate fine reference, not a manufactured analytic solution.

The maximum absolute fluid momentum/storage residual across the full-corridor cases is 1.05 × 10⁻¹¹. The maximum frozen-coefficient energy-identity defect is 6.91 × 10⁻¹¹. These check the stated numerical substep, not whole-organism energy conservation.

## Vein geometry is not yet the biological result

The default retained graph has **two components** at D ≥ 1. None of its retained length is attached through that graph to an inoculum node. The inoculum is a starting patch, **not a persistent food source**, so this measurement must not be described as food-site connectivity or used to infer a maintained food network.

Approximately **75.0%** of retained length has edge midpoints within 0.5 model length units of a wall; the length-weighted mean midpoint clearance is 0.3945. These are geometric diagnostics of the approximate arena, not digitised microscopy measurements. They quantify the remaining tendency to follow boundaries. The source's centre-in-centre phenotype is not reproduced quantitatively by this variant merely because integration is more accurate.

Body occupancy, vein attachment, wall proximity and numerical accuracy are separate measurements. The interface reports retained components and inoculum attachment at the selected display cutoff, and exports the diagnostic values with the underlying node/edge fields. Full food uptake/chemotaxis, finite biomass, retraction and experimental calibration remain biological work.

## Record integrity and replay

The legacy branch reproduces all eight earlier reference fields at the archived times with **zero difference**, and its entire original history and probe files are **byte-identical**. This checks that the numerical upgrade has not silently changed the reference protocol. Its new global series is additional measurement output.

Each [replay case](replay/) preserves exact mesh inputs, source and engine metadata, a source archive, complete compressed history/probe/global CSVs, nine complete-field reference states and checksums. The original scenario's full-file checksums refer to the complete local record; the public package is a compact replay archive, not a truncated folder for the normal desktop loader.

```sh
# Recompute the matched study; the earlier six-case study is preserved separately.
.venv/bin/python analysis/validate_biology_integrators.py
# Regenerate the report's derived geometric metrics and figures from frozen artifacts.
.venv/bin/python analysis/plot_biology_integrators.py
# Build preserved source, replay and compare the default midpoint case.
.venv/bin/python analysis/replay_biology_case.py results/biology_integration/replay/midpoint --build-source
```

Current complete local records include the full-rate global series. Earlier records remain readable without pretending that sparse frames contain those measurements. The normal exporter preserves the probe, history and global CSVs, seed membership, node masses, current frame fields and any comparison history shown in the figure.

Verification logs are stored under [results/verification](../verification/). Local checks cover **34 CTests in Release and Debug/UBSan**, the independent NumPy fluid solve for both methods, body-gate and exponential-update checks, full-rate summaries, source/method mismatch, preview cadence invariance, exports and native widget state. Hosted Ubuntu/macOS outcomes are reported by the actual workflow, separately from these numerical and biological claims.

The default midpoint source-built replay reproduced all eight archived fields with zero absolute difference, and its complete `history.csv`, `probe.csv` and `global.csv` were byte-identical on the development platform. [Replay log](../verification/biology-midpoint-source-replay.txt). This is a platform-specific reproducibility check, not a guarantee of bitwise identity across compilers or architectures.

All **88 Python tests** pass locally. [Python log](../verification/biology-midpoint-python-tests.txt) · [Release CTests](../verification/biology-midpoint-ctest-release.txt) · [UBSan CTests](../verification/biology-midpoint-ctest-ubsan.txt) · [Order test](../verification/biology-midpoint-order.txt).
