# Native desktop viewer

The viewer is a Qt desktop application using PySide6 and Matplotlib. Python provides the interface and plotting; the existing C++20/Eigen executable remains responsible for all simulation steps. There is no web server or browser component.

## Start

Build the engine using the README commands. Then:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r desktop/requirements.txt -r analysis/requirements.txt
.venv/bin/python desktop/viewer.py
```

On macOS, `Launch Physarum.command` supplies the same setup/build/launch sequence. Keep its terminal open while using the viewer. The initial window computes the default baseline and pauses at step zero. Press **Play** to animate.

To open an existing experiment directly:

```sh
.venv/bin/python desktop/viewer.py --run results/phase1/baseline
```

## Inspect a state

- **Network:** line width is proportional to conductivity. Node labels show pressure. The geometry is schematic, not geographic or to scale.
- **Trajectories:** full recorded conductivity and signed-flow trajectories are visible; the vertical cursor and markers indicate the selected state. Paired edges overlap by symmetry for the standard fixture.
- **Playback:** play/pause, restart, step forward, slider and an exact step-number field all select discrete numerical states. No interpolation or browser-side reimplementation is used. A display rate of one model unit per second is not a physical biological speed.
- **Tables:** tabs show all four edge values, node pressures and solver diagnostics. The diagnostics tab includes the current value, worst value across the run and the C++ acceptance threshold. For reciprocal condition, the worst value is the minimum.
- **Plots:** the standard Matplotlib toolbar offers zoom, pan, reset and figure export. Exported figures show the selected state and full trajectories; they are a view, not a complete experiment archive.

Coloured strokes are omitted below D=1e-10 because they are below useful drawing resolution. A pale structural outline retains every original edge; this does not modify D, delete edges or change the underlying model. Raw values remain in the tables and archives.

## Run another experiment

Parameter controls describe the next run. Changing them does not alter the displayed data. The interface states when controls differ from the loaded experiment; click **Run experiment** to apply them. The C++ process runs on a worker thread, and the previous experiment is retained if a new run fails.

New runs use the four-node fixture, fixed source 0 and sink 3, and these UI bounds:

| Parameter | Supported range |
| --- | --- |
| Injected flow I0 | 0.1 to 5 |
| Response exponent gamma | 0.5 to 3 |
| Explicit Euler time step | 0.005 to 0.25 |
| Duration | 1 to 60 model units |
| Initial conductivity | 0.01 to 1 |

Duration must be a whole multiple of dt. These are interface bounds for a manageable small experiment, not published biological constraints or accuracy guarantees. Imported runs may have parameters outside the control ranges; their actual parameters remain visible in the run label, and the controls are marked as different. Re-running uses the current controls and the fixed 0→3 terminal pair.

The same Euler accuracy and model limitations documented in `MATHEMATICAL_MODEL.md` apply. A visually plausible animation does not establish convergence, resilience, replication of the Tokyo experiment or a research contribution. No Phase 2 model is introduced by the viewer.

## Preserve and reopen experiments

**Save run archive** creates a ZIP containing the original C++ `history.csv`, `edges.csv`, `config.cfg`, `metadata.txt` and `summary.txt` when present. Those files are preserved byte for byte. New experiments initially live in temporary storage; save an archive if you want to retain one after it is replaced or the viewer closes.

**Open saved run** opens these ZIP files without extracting arbitrary archive paths. **Open run folder** reads an existing C++ output directory, including `results/manual`. The viewer accepts at most 12,000 updates (12,001 states) and currently supports only the four-node Phase 1 edge structure with terminals 0 and 3, in either direction.

Before displaying a run, the reader checks required files, configuration values, row count, edge/step/time ordering, finite values, pressure consistency at shared nodes, agreement with Q=D/L times pressure difference, and conservation of the configured source-sink demand. These are record-integrity checks. The pressure backward-error and condition-estimate values are displayed from the C++ record, not independently recomputed by the viewer.

## Verification

Run the existing C++ tests and the additional viewer checks:

```sh
ctest --test-dir build --output-on-failure
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p test_viewer.py -v
```

The viewer suite covers analytic baseline values, a fresh C++ run, exact archive round trips, malformed and inconsistent records, parameter/dataset separation, synchronized state selection, step/restart/end behaviour, signed-flow axis limits and the worker-thread handoff. Native window interaction is also checked on the development Mac; offscreen tests do not establish native UI behaviour on every operating system.

On this development Mac, Qt platform libraries under `.venv` were observed with the macOS `UF_HIDDEN` display flag set, which prevents Qt's plugin directory scanning from discovering them. The viewer clears only that flag on its platform-plugin DLLs before Qt initialization. The containing environment remains hidden. A regression test covers this startup condition.
