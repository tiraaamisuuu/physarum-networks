# Repository figures

Rebuild with `.venv/bin/python analysis/make_readme_figures.py`.

`banner.svg` is an illustrative, code-native schematic, not a biological image or an experimental result. `network-evolution.png` samples the recorded baseline history at t=0, 2, 6 and 30. `validation.png` plots that history and the measured time-step study.

Inputs: `results/phase1/baseline/history.csv` and `results/phase1/validation.json`. Snapshot inner widths are proportional to conductivity, with no inner stroke rendered below D=1e-10; pale outlines show every edge regardless of conductivity. This is only a rendering convention. Raw conductivities and simulation dynamics are unchanged. Geometry is not to scale.

`desktop-viewer.jpg` is an actual capture of the native Qt application with a fresh C++ baseline selected at step 120 (t=6). It shows synchronized network widths, trajectories and the edge table. It is not an interface mockup.


`london-evolution.png` and `.svg` show four computed states (steps 0, 133, 267 and 400) of the frozen 46-station default example. Reproduce with `.venv/bin/python analysis/make_london_figure.py` after building the engine and installing desktop/analysis dependencies. The corresponding JSON records parameters, source/binary/geography/history hashes and measured diagnostics. Raw histories are automatically saved locally under ignored `results/spatial_runs/`. A scenario manifest includes provenance/version fields that can change between runs; the numeric history is the repeatability target.

London figure widths are proportional to sqrt(D), with a fixed scale across panels, unlike the linear-D Phase 1 schematic. Pale outlines retain candidate edges. The Thames centreline and stations are geographic; links are hypothetical, demand is synthetic, time is arbitrary and elevation is omitted. TfL station data; © OpenStreetMap contributors. See `data/london/README.md` for source terms.

`london-explorer.jpg` is an actual native Qt capture of the default experiment at step 240 (t=12), not a mockup. The elevation background uses real but coarsely sampled Copernicus/Open-Meteo values as visual context only.
