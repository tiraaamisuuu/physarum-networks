# Repository figures

Rebuild with `.venv/bin/python analysis/make_readme_figures.py`.

`banner.svg` is an illustrative, code-native schematic, not a biological image or an experimental result. `network-evolution.png` samples the recorded baseline history at t=0, 2, 6 and 30. `validation.png` plots that history and the measured time-step study.

Inputs: `results/phase1/baseline/history.csv` and `results/phase1/validation.json`. Snapshot inner widths are proportional to conductivity, with no inner stroke rendered below D=1e-10; pale outlines show every edge regardless of conductivity. This is only a rendering convention. Raw conductivities and simulation dynamics are unchanged. Geometry is not to scale.

`desktop-viewer.jpg` is an actual capture of the native Qt application with a fresh C++ baseline selected at step 120 (t=6). It shows synchronized network widths, trajectories and the edge table. It is not an interface mockup.


`london-evolution.png` and `.svg` show four computed states (steps 0, 133, 267 and 400) of the frozen 46-station default example. Reproduce with `.venv/bin/python analysis/make_london_figure.py` after building the engine and installing desktop/analysis dependencies. The corresponding JSON records parameters, source/binary/geography/history hashes and measured diagnostics. Raw histories are automatically saved locally under ignored `results/spatial_runs/`. A scenario manifest includes provenance/version fields that can change between runs; the numeric history is the repeatability target.

London figure widths are proportional to sqrt(D), with a fixed scale across panels, unlike the linear-D Phase 1 schematic. Pale outlines retain candidate edges. The Thames centreline and stations are geographic; links are hypothetical, demand is synthetic, time is arbitrary and elevation is omitted. TfL station data; © OpenStreetMap contributors. See `data/london/README.md` for source terms.

`london-explorer.jpg` is an actual native Qt capture of the default experiment at step 240 (t=12), not a mockup. The elevation background uses real but coarsely sampled Copernicus/Open-Meteo values as visual context only.


`growth-evolution.png` and `.gif` are rendered from actual C++ particle-model fields, not generated illustrations. Reproduce with `.venv/bin/python analysis/make_growth_figure.py --gif`. The JSON records the settings, source/binary hashes, field/statistics hashes, observed population and contact times. Static snapshots select updates 0, 100, 300 and 1600; the GIF selects every second recorded frame (20 updates per frame) at 8 fps. Playback time is arbitrary. Colour maps the raw trail field to one fixed 0–15 range, with brighter values saturated only for display. Pale markers are unvisited; green shows current nearby particles, and amber shows a past visit with no nearby particles. None certifies connectivity.

Native Qt interaction was checked on the development Mac at update 200 of the default 46-food-site King’s Cross example, with the stage explanation and visit/population plots. The mode uses a distinct Jones-inspired particle model; it does not visualize Tero conductivity, measured biological growth or feasible train alignments. Complete assumptions are in `GROWTH_EXPERIMENT.md`.

## Fine-mesh tube figures

`tube-network.png/.svg` and `tube-evolution.png/.svg` show the current Heun default (dt 0.0125); generate with `analysis/compare_integrators.py`. `tube-default.json` records raw checksums, source/build and figure-generation provenance. `integration-sensitivity.png` shows matched integration comparisons. `tube-sensitivity.png` is the earlier Euler baseline study from `analysis/run_mesh_validation.py`; its other historical figures now write under that study’s `figures/` folder. Four evolution states are t = 0, 3, 10, 30. Stroke width is `1.2 pt × (D/0.5)^(1/4)`, fixed across panels; only D ≥ 10⁻⁴ is displayed/measured. All food sites are exact mesh vertices. Tube geometry is the actual piecewise-linear mesh, without image-generated content or geometric smoothing. Blue/orange food markers show the current source and sink; the Thames is context at zero crossing penalty. This is mesh adaptation, not simulated biological expanding-front growth.

Measured values, numerical refinement differences and frozen replay inputs are in `results/mesh_validation/`. The public compact archive preserves four numerical snapshots per case; replay reconstructs all states from the saved graph, initial values and demand sequence. Full dynamic runs are local under ignored `results/mesh_runs/`. TfL coordinates; © OpenStreetMap contributors; see upstream terms in `data/london/README.md`.

Current Heun replay cases and source archives are under `results/integration_validation/`; earlier Euler inputs remain under `results/mesh_validation/`. Only accepted states are used in the displayed evolution. Predictor stages are retained for numerical audit, not depicted as biological growth.

## Coupled biological-growth figures

`biology-growth.png/.svg` and `biology-controls.png/.svg` are derived from the frozen C++ field/probe records in `results/biology_validation/replay/`. Rebuild with `analysis/plot_biology.py`; it does not need the original local run folders. Nine archived complete-field samples per case support the evolution figure, which selects t = 0, 160, 480 and 1280. Conductivity segments use D ≥ 1 and a fixed width of `0.5 pt × D^(1/4)`. The body is the piecewise-linear w proxy, with levels 0.1, 0.9 and 1. No experimental image, photographic texture, trail skeletonization or curve smoothing is used.

The default is an explicitly named cooperative-calcium / fast-front variant of the Schenz et al. framework. It is not a quantitative reproduction of the paper or biologically validated mould. The control figure shows the source front timescale, the printed calcium expression, a feedback ablation, time-step and mesh sensitivity, and signed incident-edge flow. Apparent footprint connectivity does not establish a maintained vein graph. Model units are uncalibrated. See `results/biology_validation/REPORT.md` and `docs/BIOLOGICAL_GROWTH.md`.
