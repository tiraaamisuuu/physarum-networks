# Fine-mesh tube study

Measured numerical sensitivity of the Tero sigmoid model on real London food coordinates. This is mesh adaptation, not biological expanding-front growth or an exact Tokyo reproduction. The default has 991 vertices and 2949 candidate segments, including 46 exact food vertices.

## Final-state measurements

D ≥ 10⁻⁴; duration 30; initial D = 0.5 ± 10%; forcing switches every 0.05 model units. River cost is 2 km equivalent only in `river_cost`; all other cases use zero. Cases otherwise differ from the default in the listed parameter. Seed changes mesh, initial values and forcing together.

| Case | I₀ | γ | Δt | Mesh km | Seed | Foods connected | Length km | Mean route/direct | One-break survival | Worst-break pair access |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| default | 2 | 1.8 | 0.05 | 0.45 | 42 | 46/46 | 71.849 | 1.4214 | 0.9907 | 0.9565 |
| half_dt | 2 | 1.8 | 0.025 | 0.45 | 42 | 46/46 | 70.401 | 1.3878 | 0.9632 | 0.9565 |
| quarter_dt | 2 | 1.8 | 0.0125 | 0.45 | 42 | 46/46 | 67.454 | 1.3948 | 0.9539 | 0.9565 |
| finer_mesh | 2 | 1.8 | 0.05 | 0.3 | 42 | 46/46 | 70.411 | 1.3533 | 0.9441 | 0.9565 |
| seed43 | 2 | 1.8 | 0.05 | 0.45 | 43 | 46/46 | 70.073 | 1.3886 | 0.9898 | 0.9565 |
| seed47 | 2 | 1.8 | 0.05 | 0.45 | 47 | 46/46 | 70.393 | 1.3769 | 0.9666 | 0.9565 |
| low_current | 0.2 | 1.8 | 0.05 | 0.45 | 42 | 46/46 | 55.729 | 1.4789 | 0.6597 | 0.6783 |
| low_gamma | 2 | 1.15 | 0.05 | 0.45 | 42 | 46/46 | 341.592 | 1.0949 | 1.0000 | 1.0000 |
| river_cost | 2 | 1.8 | 0.05 | 0.45 | 42 | 46/46 | 78.338 | 1.5827 | 0.9426 | 0.6280 |

One-break survival assumes a single break uniform along retained length and asks whether all foods remain connected. It is not the paper's fault-tolerance statistic. Worst-break pair access is the fraction of all food pairs still connected under the most damaging single-segment removal; adding a useless dangling branch cannot improve it. Critical bridge length and expected post-break pair access are also in validation.json. Mean route/direct averages all 1,035 food-pair ratios, without silently excluding unreachable pairs. Physical length is distinct from resistance cost.

## Numerical evidence and limitations

Default maximum conservation residual: 2.73115e-13; maximum backward error: 2.17050e-16; minimum scaled reciprocal-condition estimate: 2.31960e-05. The Hager-style diagnostic is an estimate, not a certified condition bound. Independent fixtures check sparse versus dense and NumPy pressures, analytic circuit flows, scalar dynamics, energy/work and Euler recurrence.

Refinement holds the exact graph, initial D and forcing fixed at aligned model times. Maximum transient D differences: 0.190289 for Δt 0.05 → 0.025, and 0.0875861 for 0.025 → 0.0125; ratio 2.173. Final maximum differences: 0.178997 and 0.0651332. Shrinking differences are consistent with the first-order method in this test, but substantive final geometry differences remain. These are finite-reference comparisons, not errors against an exact London solution. Thresholded topology can change discontinuously.

The JSON records every case at cutoffs 10⁻⁵, 10⁻⁴ and 10⁻³. Mesh refinement changes geometry and the number of initial values; it is not just another time step. Three seeds do not establish statistical reliability. No calibrated biological units, measured OD demand, tunnel mechanics, service capacity, optimality or railway feasibility is demonstrated.

## Reproduce and audit

`replay/<case>/` includes exact input graph/initial/forcing CSVs, a compressed scenario with source/software hashes, four numerical D/Q/P snapshots and original file checksums. Full dynamic runs remain local in ignored `results/mesh_runs/`. The compact public archive is a replay record, not itself a dynamic run folder.

```sh
.venv/bin/python analysis/replay_mesh_case.py results/mesh_validation/replay/default
.venv/bin/python analysis/run_mesh_validation.py --output results/another-mesh-study
```

Replay solves the frozen graph without retriangulating, validates every dynamic state, compares snapshots with rtol 2×10⁻⁷ / atol 2×10⁻⁸, and reports byte identity where the software/platform match. The default replay on the development Mac was byte-identical with zero snapshot difference. Cross-platform results must be assessed numerically. Generator/metric source hashes are recorded in validation.json. Use `--refresh` only when the referenced full local runs remain available; it revalidates them and refreshes measurements/figures without rerunning the engine.

Definitions and scope: [TUBE_EXPERIMENT.md](../../docs/TUBE_EXPERIMENT.md). [Primary source](https://doi.org/10.1126/science.1177894). TfL coordinates · © OpenStreetMap contributors · [data terms](../../data/london/README.md).
