# Integration of the coupled growth model

Two numerical protocols implement the same stated cooperative-growth equations. **`legacy`** preserves the first-order experiment archived on 18 November. **`midpoint`** improves the reaction–diffusion and fluid/vein coupling. Selecting a method does not change the biochemical parameters, arena or initial conditions, and does not establish biological validity.

## Legacy protocol

The original update applies half a local RK4 reaction, a full backward-Euler diffusion step, and another half reaction, followed by a frozen-coefficient Crank–Nicolson fluid solve and a positive exponential vein update. The old D supplies the front feedback and fluid coefficients; the new v and w supply wall compliance and the reinforcement gate. Diffusion and lagged coupling limit the complete scheme to first order.

The legacy path remains an explicit option, including the CLI's default when its optional method argument is omitted. Old source archives and records remain readable. New records identify the selected method; a record whose settings and engine metadata disagree is rejected.

## Midpoint protocol

For each outer step of duration h, with accepted old state indexed n:

1. Predict a positive midpoint conductivity with the old forcing:

   ```
   S_n = Γ(w̄_n) f(q_n)
   D* = exp(−r h/2) D_n + [1 − exp(−r h/2)] S_n/r
   ```

   This is an explicit midpoint predictor, not an extra accepted state. It is not written into D_n. Initially empty edges remain exactly zero while their body gate is closed.

2. Evolve c, φ, u, v and w over h using half a local RK4 reaction, a full diffusion step and another half reaction. Both reaction halves use D* for the incident-conductivity feedback. Local RK4 substeps are at most 0.005 time units, as in the legacy protocol.

3. Diffusion normally uses the lumped finite-element Crank–Nicolson system:

   ```
   (Mτ + h K_D/2) x_new = (Mτ − h K_D/2) x_old
   ```

   Mτ is the node-mass/time-scale diagonal and K_D the diffusion-weighted stiffness matrix. Its constant factorisation is reused. During the **first two outer steps**, replace each full diffusion step by two backward-Euler half steps using that same matrix. This Rannacher-type startup damps the discontinuous initial spatial fields. The exact four-half-step choice is our implementation choice, not a recovered setting from the biology paper.

4. Use the endpoint averages v* = (v_n + v_new)/2 and w* = (w_n + w_new)/2. Freeze L̃, R̃ and Ĉ at D*, v*; solve pressure/flow by Crank–Nicolson with endpoint-average calcium forcing. This retains the same independently checked momentum, compliant-storage and frozen-energy identities.

5. With q* = (q_n + q_new)/2, accept:

   ```
   D_new = exp(−r h) D_n
           + [1 − exp(−r h)] Γ(w̄*) f(q*)/r
   ```

   There are no conductivity floors, clipping or topological pruning. A numerical positivity or finite-state failure stops the run. Crank–Nicolson is not unconditionally positivity preserving, so such checks remain necessary; startup damping is not a universal positivity proof.

The half/full/half reaction–diffusion composition follows the symmetric splitting principle of [Strang (1968)](https://doi.org/10.1137/0705041). Initial diffusion damping is motivated by [Rannacher (1984)](https://doi.org/10.1007/BF01390130). Those numerical results do not prove convergence of this complete nonlinear, body-gated biological surrogate.

## Accuracy that is actually checked

For a smooth resolved system, the midpoint coefficient predictor has O(h²) error, the endpoint averages approximate midpoint fields to O(h²), and the final exponential update approximates the smoothly varying source integral with local O(h³) error. The intended global order is therefore two. This reasoning requires smooth forcing and resolved reaction–diffusion dynamics. In this model, spatially varying chemical timescales, stiff splitting and discontinuous body/front gates can invalidate simple asymptotic-order arguments at practical steps.

A three-node controlled fixture tests refinement against a much finer integration of the same finite-dimensional equations. It uses unequal edge lengths and node masses, nonuniform calcium and no front-feedback forcing. The body reinforcement gate remains closed over this four-unit test. The reference step is 0.000078125. The error is the Euclidean norm of all eight state fields scaled componentwise by `1 + abs(reference)`.

| h | Legacy error | Midpoint error | Midpoint refinement ratio |
| ---: | ---: | ---: | ---: |
| 0.04 | 0.233853 | 0.0104775 | — |
| 0.02 | 0.128236 | 0.00631432 | 1.659 |
| 0.01 | 0.0725324 | 0.00191780 | 3.292 |
| 0.005 | 0.0390401 | 0.000524343 | 3.658 |
| 0.0025 | 0.0203263 | 0.000139748 | 3.752 |
| 0.00125 | 0.0103824 | 0.0000364858 | 3.830 |

At h = 0.02, the error is about **20 times smaller** than legacy. The coarsest refinement ratio is **not four** and is reported. The finer ratios approach four while the legacy ratios approach two. This is a finite numerical check against an approximate reference, not an analytic error bound or a morphology-convergence theorem. The reproducible CTest is `biology_midpoint_order`; its complete output is preserved with the integration study.

Additional tests independently solve the fluid matrix with NumPy under **both** coupling conventions, verify the front-system invariant under both protocols, reject method/record mismatch and check body gating and the full-rate measurement series.

## Measurements without spatial-snapshot aliasing

Full spatial fields still save at a stated interval (8 by default). At every integration step, `global.csv` now records:

- `vein_volume`: Σ ℓ√D, a conductivity-derived volume proxy, not conserved organism biomass.
- `retained_length_D1`: total edge length with D ≥ 1, not a proof of a connected vein network.

These full-rate series are checked against the spatial states wherever their times coincide. The **Vein measurements** tab displays bin means with min–max envelopes: every raw sample contributes, so a narrow peak cannot disappear through simple decimation. The complete CSV exports alongside the existing frame fields and probe/history data. Earlier records without this series display an explanatory message rather than an interpolated substitute.

For matched studies, final-80-time-unit means are integrated from the full-rate scalar data. They are explicitly time-window averages; they do not assume a biological period or infer a calibrated physical volume. Phase-specific endpoint differences and threshold sensitivity remain relevant and are reported separately.

## Protocol and compatibility

The optional final CLI argument is `legacy` or `midpoint`:

```text
physarum_biology NODES EDGES DURATION DT HILL FEEDBACK TAU_FRONT SAVE_INTERVAL PROBE OUTPUT [legacy|midpoint]
```

Omitting it runs legacy integration. Current engine metadata uses schema 2 and identifies the method and availability of the global series. Old schema-1 records have the legacy interpretation. Frozen old replay commands do not receive a new argument when rebuilding their old source.

The run limit is 320,000 steps, with a separate 40-million-spatial-scalar storage budget. At the smallest GUI step 0.005 this permits the full duration-1280 refinement. Outputs must be new/empty. Partial cancelled runs are preserved but are not accepted as complete records.

The matched full-corridor study uses identical frozen node, edge and triangle CSVs at every step size; mismatched input hashes stop the study. Its report distinguishes source-exact legacy replay, full-rate measurement differences and the remaining biological mismatch. No food response or new biological equation is introduced by this numerical change.

Current matched full-corridor results: the final D ≥ 1 edge set is identical at h = 0.02, 0.01 and 0.005. The default final-window volume mean is 0.595% below the finest run; halving h changes it by 0.485%. The default remains uncalibrated biologically. [Complete study](../results/biology_integration/REPORT.md).
