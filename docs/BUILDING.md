# Build, run and validate

The macOS `Launch Physarum.command` prepares a pinned app runtime under `~/Library/Caches/Physarum/python-<major.minor>/` using `desktop/runtime_setup.py`. A requirements/version marker and package/plugin probe allow healthy subsequent launches to skip installation. Setup is serialized on macOS/Linux and a failed installation is not marked ready. This runtime is separate from the manual `.venv` workflow below. Running `python3.14 desktop/runtime_setup.py` prints the cached interpreter path; installation progress goes to stderr. The local experiment catalog is excluded from Git and does not alter solver records.

## Build and test

Requires a C++20 compiler, CMake >=3.20 and Eigen with a CMake package (tested locally with Eigen 5.0.1; hosted Ubuntu/macOS builds check their installed packages, while other versions are not assumed compatible). On macOS, `brew install eigen cmake` supplies the build dependencies if needed. No dependencies are downloaded by CMake.

From the project root:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 4
ctest --test-dir build --output-on-failure
./build/physarum_run experiments/configs/two_routes.cfg results/manual
```

If Eigen is installed outside the normal search path, pass `-DEigen3_DIR=/path/to/share/eigen3/cmake` when configuring. Linux uses the same commands after installing its Eigen development package. The Ubuntu Release build and all 14 tests also passed in GitHub Actions on 17 November 2026; the README badge links to current hosted results.

## Reproduce the analysis

Python is used only to run experiments, validate CSV outputs and plot them. It is not the simulation engine.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r analysis/requirements.txt
.venv/bin/python analysis/run_validation.py
```

The analysis reruns the baseline twice, verifies deterministic output, checks every baseline state against independent series/parallel circuit calculations, checks each Euler update, rejects malformed CLI configurations, and performs time-step refinement. It saves configurations, histories, source hashes, binary hash, software versions and measured checks in `results/phase1/`. An existing output directory is overwritten on rerun; use `--output results/another-run` to preserve prior output. The pinned analysis dependencies reproduce the versions used on this Mac; older Python installations may require a compatible environment.

View [the plot](../results/phase1/conductivity.png), [the measured report](../results/phase1/REPORT.md), and [the complete validation data](../results/phase1/validation.json). PNG and SVG versions are available.

## What the experiment means

There are four nodes and two routes from source 0 to sink 3:

```text
          1
       1 / \ 1          Short route: length 2 (edges 0, 1)
        0   3
       2 \ / 2          Long route:  length 4 (edges 2, 3)
          2
```

Each edge starts at conductivity 0.5. With current 2, the initial short-route flow is 4/3 and the long-route flow is 2/3. The conductivities then change simultaneously using explicit Euler with gamma=1.8 and dt=0.05. The two edges on each route have matching conductivity by symmetry. At t=30, the shorter route carries almost all the flow. This result agrees with the known shorter route for this initial condition; it is not a proof of general shortest-path convergence for the saturating model.

The baseline invocation takes `CONFIG OUTPUT_DIRECTORY`. The config contains seven required `key=value` entries: `dt`, `steps`, `gamma`, `current`, `initial_conductivity`, `source`, `sink`. Blank lines and `#` comments are supported; unknown and duplicate keys fail. Without optional graph arguments, the CLI uses the four-node topology. The spatial extension accepts `CONFIG OUTPUT_DIRECTORY EDGES_CSV NODE_COUNT [DEMAND_CSV]`; see below. Edge orientations only set the sign of reported flows. Source and sink must differ, and current must be positive. The C++ engine has no internal randomness; spatial demand is prepared and recorded by the Python experiment layer.

Each run writes:

- `history.csv`: one row per edge per state, including t=0 and the final state. Conductivity, flow and endpoint pressures all refer to that same time, not staggered states. Residuals repeat on each edge row.
- `edges.csv`: endpoints and lengths; identifies edge IDs in the history.
- `config.cfg`, `metadata.txt`, `summary.txt`: resolved parameters, compiler/Eigen information and maximum residuals/final conductivities. Times are arbitrary model units, not biological seconds.

## Numerical choices and limits

The dense Eigen LDLT solve uses a grounded, diagonally scaled graph Laplacian. This is deliberately simple for small graphs: O(n^3) factorization and O(n^2) memory. Disconnected components with no imposed demand receive independent pressure references and zero flow. Disconnected terminals fail. Positive conductivities are never pruned or floored. Numerically unresolved systems stop with an error rather than changing the model.

Restricting `0 < dt <= 1` guarantees nonnegative Euler updates in exact arithmetic. It does **not** establish stability or accuracy of the coupled nonlinear dynamics; the refinement experiment measures accuracy only for this fixture. Default acceptance checks are `max conservation error <= 1e-12 + 1e-10 I0`, grounded backward error <=1e-12, and scaled reciprocal condition estimate >=1e-14. These numerical safeguards are implementation choices, not published biological parameters. See [the mathematical derivation](MATHEMATICAL_MODEL.md).

The fixed terminal pair, uniform initial conductivities, four-node graph and Euler step size are our validation choices. The paper samples random food sources on a fine mesh, including extra representation of Tokyo. The separate London extension adds frozen geography, an assumed crossing cost and recorded synthetic terminal schedules. It does not implement topology growth, damage recovery, a fungal model, performance comparisons or a Phase 2 reproduction.

## Verification on 16 November 2026

Built and run locally on macOS ARM64 using Apple Clang 17.0.0, CMake 4.0.2 and Homebrew Eigen 5.0.1. The 14 CTest cases pass in Release and in Debug with UndefinedBehaviorSanitizer. Checks cover analytic pressure/flow fixtures, orientation and terminal reversal, disconnected and near-zero cases, invalid inputs, conditioning rejection, the exact scalar Euler recurrence, positivity, refinement and CLI output. The Python validation additionally confirms byte-identical repeated runs and analytic agreement at every baseline state.

Observed baseline maximum conservation error: 1.77636e-15. Maximum normalized pressure residual: 1.26884e-16. Final short-route D: 0.776895386795; long-route D: 1.33973e-13. Halving dt from 0.05 to 0.025 changes the conductivity trajectory by up to 0.000867554. Full numerical results are in the generated report.

Debug/UndefinedBehaviorSanitizer build:

```sh
cmake -S . -B build-debug -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_FLAGS="-fsanitize=undefined -fno-omit-frame-pointer" \
  -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=undefined"
cmake --build build-debug -j 4
ctest --test-dir build-debug --output-on-failure
```

An AddressSanitizer+UndefinedBehaviorSanitizer build compiled, but its first test hung before `main` in Apple's ASan runtime initialization. A process sample showed recursive allocator initialization and a sanitizer spin lock. The run was stopped. ASan validation is therefore inconclusive, not passed; this does not affect the completed Release tests. The runtime observation is recorded in the research log.


## Arbitrary graphs and scheduled demand

The spatial runner also accepts:

```sh
./build/physarum_run CONFIG OUTPUT_DIRECTORY EDGES_CSV NODE_COUNT DEMAND_CSV
```

`EDGES_CSV` has the exact header `edge,from,to,length`, consecutive zero-based edge IDs, zero-based endpoints and positive finite effective resistance lengths. It supports 2–256 nodes and 1–4,000 edges; desktop bounds are narrower. Without `DEMAND_CSV`, the config's fixed pair is used. With it, the header is `step,source,sink`, followed by exactly `steps+1` distinct, valid terminal pairs at consecutive states. The first scheduled pair is written into the resolved config. The actual schedule is copied to the output. Conductivities persist when terminals change.

Custom graph histories append `source,sink` to the original baseline columns. All edge flows, pressures, conductivities and terminals on a row refer to the same state. The terminal pair used in an update is the pair recorded at its starting state. Baseline history columns and numeric results remain unchanged. Compiler/Eigen details and the schedule source are recorded in metadata. The engine does not interpret geography or generate randomness; those choices are explicit inputs. See [the London protocol](LONDON_EXPERIMENT.md) for the meaning of its effective edge cost and terminal-switching interval.


## Particle growth engine

CMake also builds `physarum_growth` and its independent tests. The optional `--particles` mode runs it with an explicit config and input directory:

```sh
./build/physarum_growth CONFIG INPUT_DIRECTORY OUTPUT_DIRECTORY
```

Inputs include station food coordinates, accessible-cell mask and optional synthetic river repellent. This engine is a separate chemotactic particle model; it does not call the pressure-flow solver. To create a complete reproducible example and recorded fields, use `.venv/bin/python analysis/make_growth_figure.py --gif` after installing the desktop/analysis dependencies. See [the growth protocol](GROWTH_EXPERIMENT.md) for every update rule, binary format, assumptions and checks.

## Fine-mesh tube CLI

The default laboratory uses `build/physarum_mesh`, built by the same CMake command:

```sh
./build/physarum_mesh INPUT_CFG EDGES_CSV NODE_COUNT INITIAL_D_CSV DEMANDS_CSV OUTPUT_DIRECTORY
```

The config requires `dt`, `gamma`, `current`, `steps`, with optional `integrator=euler|heun` (legacy four-key files imply Euler). Edge CSV header: `edge,from,to,length`; initial CSV: `edge,conductivity`; demand CSV: `step,source,sink` with steps + 1 rows. IDs are consecutive from zero. Lengths and initial D must be positive and finite; the graph must be connected. The Python bridge prepares exact geographic food vertices and records all inputs. Its stricter limits cap runs at 5,500 nodes, 17,000 edges, 6,000 updates, 25 million recorded edge-states and 512 MB of raw states.

D/Q/P outputs are state-major little-endian float64 arrays, accompanied by per-state diagnostics and compiler/Eigen metadata. Heun also records predictor Q/P and diagnostics. The output directory must be new or empty, preserving existing records. CMake embeds an engine-source fingerprint; the Python bridge binds it to a preserved code snapshot. Unlike the original dense CLI, this solver requires strictly positive D on a fixed graph and reports a Hager-style reciprocal-condition **estimate**. It never floors or prunes conductivities. See [the tube guide](TUBE_EXPERIMENT.md) for equations, format, assumptions and exports. `analysis/replay_mesh_case.py` demonstrates direct CLI replay using archived exact inputs without rebuilding a triangulation.

## Coupled biological migration engine

The launcher opens the London network laboratory by default. Use `desktop/viewer.py --sandbox` for a blank food-site arena, `--biology` for this separate biological benchmark, and `--biology-run PATH` to reopen a complete biological record.

CMake builds `physarum_biology`. Its direct CLI takes exact finite-element inputs:

```text
physarum_biology NODES_CSV EDGES_CSV DURATION DT HILL FEEDBACK TAU_FRONT SAVE_INTERVAL PROBE_NODE OUTPUT
```

Nodes have `id,x,y,mass,inoculum`; edges have `id,from,to,length,weight`. IDs must be consecutive, values finite, masses/lengths positive, weights nonnegative and the inoculum nonempty. The desktop generator additionally verifies complete corridor coverage and diffusion connectivity. The CLI checks numeric/storage bounds and refuses a nonempty output directory. It writes little-endian float64 arrays for all eight fields, slow area/vein histories, a full-rate calcium/flow probe and engine metadata. The experiment wrapper preserves exact input CSVs, source and checksums; source-built replay reconstructs the compact public reference.

Full model, discretisation, source ambiguities and parameter interpretation: [biological growth](BIOLOGICAL_GROWTH.md). Repeat the controlled study with `analysis/validate_biology.py`. It creates new complete local records under ignored `results/biology_runs/` and updates the public compact references; preserve the previous study if needed.

The biological CLI additionally accepts an optional final `legacy` or `midpoint` argument. Omission preserves legacy behaviour; the desktop now selects midpoint by default. Engine schema 2 records the method and a full-rate `global.csv` for conductivity-derived volume and retained length. The maximum step count is 320,000 with a separate spatial-output budget. [Integration contract and evidence](BIOLOGICAL_INTEGRATION.md). Run `analysis/validate_biology_integrators.py` for matched frozen-mesh controls; this writes a separate `results/biology_integration/` study and preserves the earlier baseline.
