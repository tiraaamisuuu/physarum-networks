# London exploratory network

This native desktop mode asks: **how does an abstract adaptive network change when real station positions and a hypothetical crossing cost are supplied?** It does not optimize Tube service, infer passenger demand, reproduce existing tracks or produce an engineering design. The independently validated four-node fixture remains available from File → Open validated four-node viewer, or `desktop/viewer.py --fixture`.

## Try it

The default launcher now opens the growth laboratory. Use **File → Open station-connection experiment**, or run `desktop/viewer.py --network` after the README setup, to compute this 46-station connection example and pause at step zero.

1. Press **Play**. Initially, all possible links have the same conductivity. Flow reinforces some connections; others become thinner. Grey outlines retain the candidate graph. No model edge is deleted.
2. Click a station to see its name and current pressure. Click a connection or table row to inspect its conductivity D and signed flow Q over the complete run. The dashed cursor selects the current recorded state.
3. Change **Thames penalty** from 2 to 0, keep seed 42 and the other settings, then click **Run adaptation**. This tests the effect of removing the assumed crossing cost under the same station-pair schedule. A changed picture alone does not establish better transport performance.
4. Use **Choose Tube stations** to change the demand locations. Use the map editing menu to add a hypothetical junction or drag a restricted rectangle. Editing creates a **scenario preview**; run again to compute new states.
5. Use **File → Save scenario** to retain an editable setup, and **Open spatial run folder** to return to a computed experiment. Every attempted C++ run is automatically saved under `results/spatial_runs/`, including failed-run inputs and any partial output.

Use the Matplotlib toolbar to zoom, pan or export a figure. Return to the arrow/inspection mode before editing the map. Station labels can be switched on; otherwise click stations individually to avoid clutter. The sidebar scrolls on smaller screens.

## What is real, and what is assumed?

| Input | Treatment |
| --- | --- |
| Station positions | Frozen TfL station catalogue; 46 selected by default. Includes one entry per NaptanMetroStation, not individual entrances. |
| Thames | Frozen OpenStreetMap river centrelines, with source way IDs. Plot width is symbolic. |
| Elevation | Real Copernicus/Open-Meteo samples, drawn as context. **No effect on the solver or connection costs.** |
| Connections | Hypothetical straight segments from a nearest-neighbour graph; not existing tracks or proposed tunnel alignments. |
| Demand | Synthetic: uniformly sampled distinct station pairs, or one chosen fixed pair. No measured passenger counts. |
| Crossing penalty | User assumption in km-equivalent resistance length; not a calibrated tunnel, bridge or monetary cost. |
| Restricted rectangles | User assumptions excluding initial candidate segments. Not an imported geological or planning constraint. |
| Added junction | Hypothetical point carrying flow; receives no external demand. |

The full catalogue has 272 station entries. Outer stations outside the cached Thames query bounds (51.45–51.57°N, −0.25–0.05°E) are disabled. Nodes outside this coverage are rejected before running: an absent river record must not silently become a free crossing. Extend and audit the geographic dataset before studying outer London. The elevation raster covers the original example with a margin; it can leave blank areas when the selected study area grows within the Thames bounds.

See [geographic data provenance and licences](../data/london/README.md). The frozen input is included in the repository, so normal application use needs no network connection or API key.

## Mathematical protocol

Coordinates use EPSG:27700 British National Grid, stored in kilometres. Each node nominates its k nearest other nodes by Euclidean distance. The undirected candidate graph is the union of those nominations; ties use node order. A station can therefore have more than k connections. Restricted rectangles remove intersecting segments before simulation. The application rejects a graph that disconnects demand stations; it does not invent repair links.

For a candidate edge e:

```
C_e = straight_line_distance_km + river_penalty_km × any_Thames_centreline_intersection
Q_e = (D_e / C_e) × (p_from − p_to)
D_e(t + dt) = (1 − dt) D_e(t) + dt × |Q_e(t)|^gamma / (1 + |Q_e(t)|^gamma)
```

The penalty is charged once per edge if any centreline segment intersects, including a touching intersection. It is a modelling coefficient replacing the baseline length L. Crossing segments do not create a junction unless a node is explicitly present. The model has no tunnel depth, gradient, capacity, timetabling, interchange time, vehicle or monetary cost representation. Surface elevation does not determine underground construction cost.

Defaults: I0=2, gamma=1.8, dt=0.05, duration=20, D(0)=0.5, k=6, river penalty=2 km-equivalent, seed=42. These generate 183 possible connections, 36 marked as crossing, and 401 recorded states for the 46 selected stations.

Uniform mode uses a local seeded Python generator to sample two distinct demand stations **at each Euler state**. At state n the engine solves the flow for pair n, records D_n, p_n and Q_n, then updates D for the next state. The last pair is used only for the final recorded flow. The exact ordered schedule is saved as CSV; replay that file rather than relying on a seed alone across software versions. Flow sign follows the stored edge orientation, not station priority. The imposed total current is 2 for every pair; there are no simultaneous passenger flows.

**Changing dt changes the terminal-switching interval in uniform mode.** Comparing different dt values with independently sampled per-step schedules is not a numerical convergence study of the same forcing. For refinement, use fixed-pair mode or supply schedules with identical physical switching times and compare aligned states. No spatial refinement or statistical performance study is claimed by the example.

The topology, coordinates, demand rule and penalty are experimental choices. This is not a replication of the 2010 Tokyo fine-mesh experiment and makes no novelty or optimality claim. The C++ pressure/flow and adaptation laws are the same as in the validated fixture.

## Recorded runs and verification

Each run folder contains:

- `scenario.json`: complete scene and frozen geography, settings, candidate endpoints, physical distances, effective costs and crossing flags; source and executable SHA-256 hashes; Python/NumPy versions and explicit assumptions.
- `inputs/`: configuration, graph and the actual per-state demand schedule.
- `output/`: C++ history, resolved graph/configuration, demand schedule, compiler/Eigen metadata and numerical summary.
- `engine.log`, and `failure.txt` if execution or subsequent validation fails.

Runs are local and ignored by Git; keep the whole folder to preserve an experiment. The first C++ run on this Mac completed 400 updates with maximum conservation residual 5.49e−13, below the configured acceptance threshold 2.01e−10. This is a numerical integrity observation, not a transport accuracy estimate.

Before display, the spatial reader checks graph/cost agreement with the scene and CSV inputs, complete row ordering, demand schedule agreement, finite nonnegative conductivity, coherent shared pressures, the pressure-flow equation, conservation and every Euler transition. It checks the recorded C++ diagnostics against acceptance limits; it does not independently refactor the pressure system or recompute its condition estimate. Tests also compare an arbitrary-graph initial pressure solution against an independent NumPy solve and deliberately corrupt a history while preserving instantaneous flow/conservation to verify the Euler check.

The native plot uses a fixed width mapping `6 points × sqrt(D / 0.5)` in every frame. Below D=1e−10 the coloured stroke is omitted; the pale candidate outline and raw values remain. Time and D are abstract model quantities. Playback speed does not change the model.

The interface limits experiments to 3–80 selected stations, at most 100 nodes including junctions, at most 900 edges and 2,000 updates. k is 2–12; current 0.1–5; gamma 0.5–3; dt 0.01–0.25; duration 1–40; penalty 0–10; initial D=0.5 in this interface. Duration must be a whole multiple of dt. The dense solver is intended for small exploratory graphs. Numerical failure stops the run; it does not add a conductivity floor or alter the data.

## Before calling a result a Tube redesign

A practical study needs a defined objective and baselines, measured origin/destination demand, capacity and operational constraints, plausible alignments and ground conditions, calibrated costs, sensitivity across graph construction/parameters/random seeds, and an independently controlled integration study. The current application provides a transparent starting experiment and its reproducible record. A visually convincing network is not evidence that it would serve London better.
