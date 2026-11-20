# Fine-mesh tube experiment

## Why this replaces the default particle view

The particle laboratory rendered a diffused movement trail. Its broad bands could bypass food coordinates, and local particle activity did not establish a connected maintained network. Changing line width could not solve that model mismatch. The tube experiment instead uses the published pressure–flow and sigmoid conductivity equations on a fine spatial graph. Food sites are exact vertices, not nearby targets or annotations over a raster field.

This follows the *numerical* experiment in Tero et al. (2010), which begins with an existing fine mesh and initial conductivity fluctuations. The biological expanding margin in Fig. 1 is a different phenomenon; the application does not pretend that revealing a computed network constitutes growth. The particle experiment remains separate for exploratory comparison.

## Geometry and forcing

- Frozen TfL station locations use British National Grid coordinates in kilometres. Default: 46 selected stations. Choose 2–80 food sites within the cached study bounds, including explicitly identified custom sites. The separate blank sandbox uses local kilometre coordinates without fabricated geography.
- Candidate junctions form a seeded, jittered triangular lattice, default spacing 0.45 km; independent jitter is uniform in ±0.2 spacings on each coordinate. Background points within 0.12 spacings of fixed vertices are discarded before triangulation. Every food and user junction is inserted at its exact coordinate. Coincident fixed vertices are rejected.
- Delaunay triangulation supplies actual piecewise-linear tube geometry. Rectangular restrictions remove intersecting candidate segments before initialization. Demand-free disconnected background components are discarded at that stage; disconnected food sites cause an error. No link is invented to rescue them. Geometry is frozen throughout adaptation.
- Physical length is Euclidean distance. Effective resistance length adds the stated hypothetical km-equivalent cost once to each mesh edge intersecting the cached Thames centreline. This is a discretization-dependent assumption, not bathymetry, geology or a measured tunnelling cost. A zero penalty leaves the river as context only.
- Default D₀ = 0.5 × (1 + U[−0.1, 0.1]). Mesh and initial fluctuations use separate NumPy random streams derived from the seed. The exact graph, initial values and demands are saved, so replay does not depend on reproducing a triangulator's choices.
- Default random food-pair forcing samples two distinct foods uniformly. A pair is held for a configurable model-time interval, default 0.05. Flow magnitude is I₀; reversing the pair reverses Q while preserving |Q| and the adaptation law. Fixed-pair forcing is also available.
- Demand switching remains fixed when Δt is refined. Duration and switching interval must be integer multiples of Δt. There are steps + 1 solved states: the pair recorded at state k produces Qₖ and the update Dₖ→Dₖ₊₁.

These mesh, noise, integration and switching choices are ours. The inspected article and figures S1/S2 do not specify a complete exact numerical reproduction protocol. The original Tokyo numerical comparison uses seven aggregated food sites, not these 46 London stations.

## Equations and numerical checks

Q = (D/L) Δp; at every vertex, signed net outflow equals the imposed injection. The solver grounds vertex 0 at pressure zero, diagonally scales the grounded Laplacian, uses Eigen sparse SimplicialLDLT, and permits up to two residual corrections after the initial solve. A Hager-style inverse-1-norm estimate diagnoses conditioning. It is an estimate, not a certified bound on pressure error.

For the optional Euler method, conductivity updates simultaneously:

`D_next = (1 − Δt) D + Δt |Q|^γ / (1 + |Q|^γ)`.

No numerical pruning, conductivity floor, artificial food attachments, geometric interpolation or curve smoothing is used. All D must stay finite and strictly positive. Ill-conditioning, failed factorization, underflow, overflow or unresolved conservation stops the run and preserves available inputs/output for inspection.

Every state must satisfy conservation ≤ `1e-12 + 1e-10 I₀`, backward error ≤ `1e-12`, and scaled reciprocal condition estimate ≥ `1e-14`. A small residual is not sufficient evidence of accurate forward pressure in every problem. The replay loader separately reconstructs the flow law, Kirchhoff balances, dissipation/work identity and all recorded integration transitions. It checks dimensions, exact food coordinates, demand protocol, configuration, input graph and SHA-256 checksums.

## Read the display and measurements

The cutoff **D ≥ 10⁻⁴** defines the displayed graph and all retained-network measurements. Change it in the interface to inspect sensitivity. It never changes model dynamics or raw D. A fully positive numerical graph may be connected through negligible tubes; we therefore report connectivity of this explicitly thresholded graph.

Stroke width is fixed across frames: **1.2 points × (D/0.5)^(1/4)**. D is proportional to radius⁴ in the Poiseuille idealization with fixed viscosity, but the display scale is not a calibrated physical radius. The strokes are actual mesh segments. Pale food markers sit on exact vertices. Blue/orange mark the currently imposed source/sink, which change under random forcing. **Candidate mesh** reveals all possible edges. Click a retained segment for its D/Q trajectory and current pressure drop. The food table lists incident retained tubes; that count alone does not establish global connectivity.

Metrics:

- **Largest food component:** maximum number of food vertices in one connected component, including all intermediate mesh vertices. All foods are connected exactly when this equals the selected food count.
- **Connected food pairs:** fraction of all unordered food pairs sharing a retained component. Isolated foods are included.
- **Retained length:** sum of actual physical lengths of retained segments, counted once. Effective resistance lengths are not substituted for physical length.
- **Mean route / direct distance:** for each food pair, shortest retained-network distance divided by direct Euclidean distance, averaged over all pairs. Reported unavailable when any food pair is disconnected; unreachable pairs are never silently dropped.
- **Terminal-only Euclidean MST:** a comparison graph connecting the food coordinates without candidate junctions. It is **not** a lower bound for networks allowed Steiner junctions.
- **Single-break survival:** probability all foods stay connected after one break uniformly distributed along retained physical length. A bridge whose removal separates food vertices causes failure; dangling food-free branches do not. This explicitly defined proxy is **not the original paper's fault-tolerance statistic**. It assumes independent single breaks and no repair, passenger demand or other failure physics.
- **Volume proxy**, JSON only: Σ L√D over *all raw tubes*, proportional to volume under a fixed Poiseuille conversion. It is not a calibrated biomass or economic cost.

The time plots select exact recorded states. The connectivity history samples at most 41 states; the displayed-state measurements use that exact state, not the sampled trace. Playback is separate from model time; no time-to-hours conversion is asserted.

## Experiments you can do now

Start with the default, inspect the final network and export a snapshot. Then change **one** variable while keeping other controls and food sites fixed:

1. I₀ = 2 versus 0.2: compare retained length, route stretch and the single-break proxy.
2. γ = 1.8 versus 1.15: inspect retained secondary routes at the same cutoff.
3. River cost 0 versus 2: inspect route changes, treating the cost as an assumption.
4. Δt = 0.05, 0.025, 0.0125 with switch interval 0.05: compare integration error under identical forcing and initial graph.
5. Mesh spacing 0.45 versus 0.30 km; seeds 42, 43, 47; cutoffs 10⁻⁵, 10⁻⁴, 10⁻³: assess dependence on discretization, randomness and graph extraction.

Our recorded study demonstrates these parameter effects and their numerical sensitivity. A three-seed check is not a statistical validation. Mesh refinement changes candidate geometry, edge count and independent initial values; it is not simply another integration step size. Avoid selecting a visually favourable graph and calling it optimal.

## Records and exports

Complete runs save locally in `results/mesh_runs/<UTC>-<id>/`, including frozen geography/mesh, settings, binary/source hashes, actual demands, C++ metadata and every raw D/Q/P state. Files D.f64, Q.f64 and P.f64 are state-major IEEE-754 little-endian float64 arrays with shapes `(steps+1, edges)`, `(steps+1, edges)`, `(steps+1, nodes)`. `diagnostics.csv` identifies terminals, times and residuals. Reopen through File → Open recorded tube run or `desktop/viewer.py --mesh-run PATH`.

Export snapshot produces `network.svg`, `network.png`, `tubes.csv`, `nodes.csv`, `snapshot.json` and the originating `scenario.json`, plus `source.tar.gz` for source-complete runs. The snapshot records the state, cutoff, metrics and originating run folder. It is a figure/data extract, not a substitute for the complete dynamic run. File → Save experiment design stores a reusable scene and settings; it does not relabel or overwrite a recorded run. Changed controls have a prominent draft banner until computed.

`analysis/run_mesh_validation.py` computes the nine-case study. The public compact record includes frozen input CSVs, a compressed scenario and four D/Q/P reference snapshots for each case. `analysis/replay_mesh_case.py CASE` replays those exact inputs with the local C++ binary, independently validates the output and compares snapshots. Original output checksums allow byte-level comparison where the software/platform match. Cross-platform acceptance uses stated numerical tolerances.

## Remaining research work

Biological expanding-front dynamics, experimental image calibration, exact Tokyo source protocol, oscillatory streaming, elasticity/viscosity dynamics, measured passenger demand, ground/terrain engineering, route curvature constraints, optimization claims and statistical inference remain outside this implementation. Source: [Tero et al. (2010)](https://doi.org/10.1126/science.1177894). Geographic provenance: [London data](../data/london/README.md).

## Map editing and parameter studies

The **Map editor / sandbox** tab is a design canvas, separate from recorded results. Search for a station or click an unused grey station to add food. Selected stations are green circles; custom food sites are amber diamonds. Choose an explicit tool to place, inspect, move or remove food. Custom names and coordinates are editable; official stations retain their real names and locations. Undo/redo preserve stable node IDs. The cached London study bounds and 2–80 food limit apply. The blank sandbox uses a 16 × 10 km local arena; background candidate vertices span its domain rather than only the food bounding box, allowing routes around obstacles. London custom sites likewise use the cached study extent. Unedited legacy London mesh construction is unchanged.

Draw rectangular exclusions to remove intersecting candidate segments before a new run. Food inside an exclusion is rejected, as is a disconnected resulting food graph. On the Network tab, dashed outlines indicate unapplied restriction edits; solid hatching belongs to the recorded run. Compute applies a design; it never changes an existing record. The editor hides old numerical measurements/playback. [Practical sandbox guide](SANDBOX.md).

**Route inspector** uses Dijkstra's algorithm with physical edge lengths on the retained numerical graph. It highlights only an existing path at the recorded state and chosen cutoff, reports disconnected pairs and identifies food vertices actually traversed. This inspection does not change the model. Route exports include both recorded-edge and path-direction signed flows.

Both maps can show sampled **surface elevation** as context, with Copernicus/Open-Meteo attribution. This is a coarse surface dataset, not underground geology; it does not alter tube resistance. No fabricated smooth terrain or inferred subsurface mechanics is introduced.

The **Parameter study** tab varies one parameter over 2–8 values and 1–8 seeds (up to 24 cases, 2 GB of raw states). The scene, remaining controls and cutoff are captured when the study starts. Values for γ, I₀, spacing, river cost or Δt are paired by seed. For γ/current/cost/dt contrasts at a given seed, mesh/initialization/forcing remain matched except where the parameter explicitly changes them. Refining Δt holds the demand switching interval fixed; spacing changes geometry and the number of initial values.

Every completed case writes to `summary.csv` and `summary.json` immediately; each also has a complete run directory. CSV rows include the extraction cutoff and model settings. Cancellation retains completed cases and any available partial output. The chart displays individual runs labelled by seed, rather than an unsupported confidence interval; disconnected cases are counted explicitly and their route ratio is unavailable. Select a row and **Inspect selected run** to load its final state at the study's original cutoff. Completed studies save SVG/PNG charts and a complete plan under `results/mesh_sweeps/`.

## Optional imported food-pair frequencies

File → **Save demand CSV template** creates a small example with the header `source,sink,weight`. Replace its example values with documented data or an explicitly synthetic hypothesis. Endpoints can be exact selected station names or TfL IDs. Import through File → **Import demand weights CSV**, or the sidebar button, and select **Weighted pairs from CSV**. All referenced stations must already be food sites. Weights must be finite and positive; endpoints must differ. Missing stations, malformed rows, empty files and unresolvable floating-point weight ranges are rejected.

Weights control **sampling frequency**, not the magnitude of injected flow, which remains I₀ for every pair draw. Direction reverses signed flow in this undirected model; the reinforcement depends on |Q|. Imported weights do not add train capacity, passenger journey times, station dwell, simultaneous OD flows or an empirical-demand claim. Foods not referenced by the demand may lose their retained connections; they remain included in connectivity measurements. Source filename/hash, normalized endpoint IDs, all weights and the actual sampled schedule are saved with the scenario. The same fixed switching interval supports matched Δt refinement. Reopening needs no original CSV file.

**Failure impact:** `critical_bridge_length_km` sums retained bridge length whose removal separates food vertices. `expected_connected_pair_fraction_after_break` averages the fraction of all food pairs still connected after one break uniform along retained length. `worst_break_connected_pair_fraction` reports that fraction under the most damaging single-segment removal. A three-food chain retains only one of three food pairs after either link breaks; a cycle retains all three under any one-link break. These metrics account for intermediate junctions and already-disconnected components. The worst-case fraction cannot be improved by adding a food-free dangling branch. They measure topology without flow capacity, repair or a time-calibrated failure rate.

Use **Open saved study** to restore a complete or partial study index, chart and planned controls. Moving the entire study folder preserves inspection because run paths are rebased from its `runs/` directory. Opening a summary checks plan/case agreement and scalar consistency; **Inspect selected run** then revalidates the complete dynamic record. Legacy summaries can be read, with measurements they did not record labelled unavailable rather than fabricated.

## Recorded two-stage integration and the current default

The laboratory now defaults to **Heun / SSPRK2 at Δt = 0.0125**; Euler remains selectable and old records remain readable. Both solve the same sigmoid tube ODE. Heun computes an Euler predictor D*, solves a second pressure system using D* and the **same held food pair**, and corrects with the convex average:

`D* = (1−dt) D + dt f(Q)`

`D_next = ½D + ½[(1−dt) D* + dt f(Q*)]`.

For the supported dt ≤ 0.25 this preserves positive conductivity in exact arithmetic. Overflow/underflow checks still reject unresolved finite states; no floor or pruning is added. Scalar CLI tests verify the exact discrete recurrence and second-order refinement against a continuous analytic solution. The full London experiment has a measured refinement ratio near 2 at the tested coarser steps, so formal order is not an accuracy guarantee there.

The default versus Δt = 0.00625 has maximum transient conductivity difference 0.00885017 and final maximum difference 0.00131974. At D ≥ 10⁻⁴ the final retained segment sets are identical in this pair, with all 46 foods connected. This is finite evidence for this one experiment, not proof of convergence across parameters, seeds or extraction cutoffs. The default network length is 65.894 km and mean food-pair route/direct ratio 1.40091. The earlier Euler study is preserved separately and reports different values. See [integration evidence](../results/integration_validation/REPORT.md).

Heun records schema 2: accepted states remain D/Q/P, and `stage_Q.f64` / `stage_P.f64` have shapes `(steps, edges)` / `(steps, nodes)`. Stage D* is reconstructed from recorded D and Q. `stage_diagnostics.csv` records the predictor solves at endpoint time `(k+1)dt` with the held pair from step k; this is the **left-side forcing at a switch boundary**, not the next accepted state's new pair. These internal stages are not displayed as biological states or interpolated animation frames. The reader verifies their pressure law, conservation, energy identity, reference pressure and integration recurrence. Reported global diagnostic extrema include all accepted and predictor solves.

The interface supports dt from 0.005 to 0.25, at most 6,000 updates and 512 MB of raw states per run; batch studies retain their 2 GB queue cap. Changing method affects storage estimates. Records preserve all numerical stages. **Compare runs** additionally reports aligned D differences when graph, initialization, model and full held forcing match on nested time grids. Those are pairwise differences, not errors against an exact London solution.

## Source provenance

New runs include a code-only `source/` snapshot with SHA-256 checksums. CMake embeds a fingerprint of the C++/header/build-description files in the executable; the reader compares it with the source snapshot and refuses a mismatched run. This detects source edited without rebuilding the engine. The binary hash, compiler/Eigen versions, Python/library versions, exact graph, initial values and forcing remain recorded. Snapshots capture files present at run creation; restart the application after editing Python code. Exact input CSVs and the compiled engine fingerprint are authoritative for physics replay.

Public current Heun cases include `source.tar.gz`; older archives preserve their original hashes and remain labelled by their recorded integration method. Source-verified replays retain original software metadata in `replay_reference_software`, so provenance refinement does not pretend an old file was produced by new source. Every archive is generated only from the indexed code files, with deterministic metadata. Snapshot exports now also include the originating `scenario.json` and, for source-complete runs, `source.tar.gz`; node CSV includes stable food/junction keys.

Additional JSON quantities expose the selected pair's required pressure drop and hydraulic dissipation `I₀ Δp = Σ Q²L/D` over the raw network. These are **model units for the currently imposed pair**, not measured train power, passenger travel cost, capacity or an average over all demands.

To build only the archived engine source in isolation, extract `source.tar.gz` into a scratch directory and configure it with `-DBUILD_TESTING=OFF`. Full repository tests and frozen geographic layers live in the checkout; the source archive is not a standalone distribution of those datasets. Engine snapshots preserve the C++/header/CMake bytes required to reproduce the compiled fingerprint. Figure provenance separately records the rendering script and plotting-library versions, because plotting may occur after the physical run.
