# Physarum networks

A Phase 1 research baseline: a C++20 implementation of flow-dependent conductivity adaptation, using the saturating reinforcement law in Tero et al. (2010). This is a validated small synthetic experiment, not a replication of the Tokyo rail-network experiment or a model of all slime-mould biology.

## Build and test

Requires a C++20 compiler, CMake >=3.20 and Eigen with a CMake package (tested with Eigen 5.0.1; Eigen 3.3+ is the intended API baseline, but older versions have not been tested). On macOS, `brew install eigen cmake` supplies the build dependencies if needed. No dependencies are downloaded by CMake.

From the project root:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 4
ctest --test-dir build --output-on-failure
./build/physarum_run experiments/configs/two_routes.cfg results/manual
```

If Eigen is installed outside the normal search path, pass `-DEigen3_DIR=/path/to/share/eigen3/cmake` when configuring. Linux should use the same commands after installing its Eigen development package; Linux execution has not been verified.

## Reproduce the analysis

Python is used only to run experiments, validate CSV outputs and plot them. It is not the simulation engine.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r analysis/requirements.txt
.venv/bin/python analysis/run_validation.py
```

The analysis reruns the baseline twice, verifies deterministic output, checks every baseline state against independent series/parallel circuit calculations, checks each Euler update, rejects malformed CLI configurations, and performs time-step refinement. It saves configurations, histories, source hashes, binary hash, software versions and measured checks in `results/phase1/`. An existing output directory is overwritten on rerun; use `--output results/another-run` to preserve prior output. The pinned analysis dependencies reproduce the versions used on this Mac; older Python installations may require a compatible environment.

View [the plot](results/phase1/conductivity.png), [the measured report](results/phase1/REPORT.md), and [the complete validation data](results/phase1/validation.json). PNG and SVG versions are available.

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

The runner takes exactly `CONFIG OUTPUT_DIRECTORY`. The config contains seven required `key=value` entries: `dt`, `steps`, `gamma`, `current`, `initial_conductivity`, `source`, `sink`. Blank lines and `#` comments are supported; unknown and duplicate keys fail. The CLI fixes the four-node topology; other graphs can be constructed through the C++ API. Edge orientations only set the sign of reported flows. Source and sink must differ, and current must be positive. There is no randomness or seed in this milestone.

Each run writes:

- `history.csv`: one row per edge per state, including t=0 and the final state. Conductivity, flow and endpoint pressures all refer to that same time, not staggered states. Residuals repeat on each edge row.
- `edges.csv`: endpoints and lengths; identifies edge IDs in the history.
- `config.cfg`, `metadata.txt`, `summary.txt`: resolved parameters, compiler/Eigen information and maximum residuals/final conductivities. Times are arbitrary model units, not biological seconds.

## Numerical choices and limits

The dense Eigen LDLT solve uses a grounded, diagonally scaled graph Laplacian. This is deliberately simple for small graphs: O(n^3) factorization and O(n^2) memory. Disconnected components with no imposed demand receive independent pressure references and zero flow. Disconnected terminals fail. Positive conductivities are never pruned or floored. Numerically unresolved systems stop with an error rather than changing the model.

Restricting `0 < dt <= 1` guarantees nonnegative Euler updates in exact arithmetic. It does **not** establish stability or accuracy of the coupled nonlinear dynamics; the refinement experiment measures accuracy only for this fixture. Default acceptance checks are `max conservation error <= 1e-12 + 1e-10 I0`, grounded backward error <=1e-12, and scaled reciprocal condition estimate >=1e-14. These numerical safeguards are implementation choices, not published biological parameters. See [the mathematical derivation](docs/MATHEMATICAL_MODEL.md).

The fixed terminal pair, uniform initial conductivities, four-node graph and Euler step size are our validation choices. The paper samples random food sources on a fine mesh, including extra representation of Tokyo. No stochastic selection, geography, topology growth, damage experiment, fungal model, performance metric comparison or Phase 2 reproduction is implemented.

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

## Research record and next milestone

The [original brief](docs/PROJECT_BRIEF.md), [mathematical model](docs/MATHEMATICAL_MODEL.md), [literature notes](docs/LITERATURE.md), [bibliography](docs/references.bib), and [research log](docs/RESEARCH_LOG.md) document the scope and reasoning.

Next: specify a source-audited Phase 2 replication protocol, resolving the mesh, initial noise, terminal sampling, integration schedule and interpretation of near-zero tubes before comparing with published figures. The inspected supplementary PDF supplies figures S1/S2, not a complete implementation protocol. Further source investigation is needed; no novelty claim or research extension has been made.
