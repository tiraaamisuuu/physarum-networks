# Integration comparison

Both methods solve the same Tero sigmoid ODE on the same London graph, initial conductivities and held food-pair sequence. Heun uses a second pressure solve at its Euler predictor, then averages two Euler stages. Every stage is recorded and independently checked for the pressure law, conservation, work/dissipation and solver acceptance; this is not post-processing of Euler output.

| Method | Max D difference: dt .05 vs .025 | Max D difference: dt .025 vs .0125 | Ratio | Coarse difference to common fine Heun |
| --- | ---: | ---: | ---: | ---: |
| euler | 0.190289 | 0.0875861 | 2.173 | 0.22736 |
| heun | 0.0471375 | 0.0212941 | 2.214 | 0.0572354 |

Interactive default Heun Δt = 0.0125 versus 0.00625: maximum transient D difference 0.00885017, final maximum difference 0.00131974. Final retained edge sets at D ≥ 10⁻⁴ are identical: True. This is a finite check for this setup, not a general convergence guarantee.

These are finite-reference differences, not known exact London errors. Separate scalar CLI tests compare with an exact continuous solution and verify first/second-order behaviour. Holding the pair for both Heun stages is essential at demand-switch boundaries. Neither method is a biological calibration, proof of an optimal network or an engineering model.

Heun is expressed as convex Euler steps: D* = (1−dt)D + dt f(Q), followed by D_next = ½D + ½[(1−dt)D* + dt f(Q*)]. For the supported dt ≤ 0.25, positive conductivities remain positive in exact arithmetic; finite-state/underflow checks remain active. There is no numerical floor or pruning. Legacy four-key Euler configs and archived histories remain supported.

The public replay archives preserve exact graph, initial state, forcing and numerical reference snapshots. Replay with `analysis/replay_mesh_case.py CASE`. `validation.json` records full metrics and diagnostic extrema across accepted states **and predictor stages**. Figure: `docs/assets/integration-sensitivity.png`. Complete dynamic runs remain local under `results/mesh_runs/`.
