# Repository figures

Rebuild with `.venv/bin/python analysis/make_readme_figures.py`.

`banner.svg` is an illustrative, code-native schematic, not a biological image or an experimental result. `network-evolution.png` samples the recorded baseline history at t=0, 2, 6 and 30. `validation.png` plots that history and the measured time-step study.

Inputs: `results/phase1/baseline/history.csv` and `results/phase1/validation.json`. Snapshot inner widths are proportional to conductivity, with no inner stroke rendered below D=1e-10; pale outlines show every edge regardless of conductivity. This is only a rendering convention. Raw conductivities and simulation dynamics are unchanged. Geometry is not to scale.
