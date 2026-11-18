# Growth laboratory: one patch and station food sites

The default desktop mode now starts a small simulated colony at **King's Cross St Pancras**, with food sites at the selected London stations. It asks how simple local particle rules produce spreading, branching and changing trails. The start is a user-selectable experimental choice, not a claim that London has one main station. King's Cross St Pancras is a major interchange; [Network Rail describes its six Underground lines](https://www.networkrail.co.uk/rail-travel/our-stations/london-st-pancras-international/).

## Start here

Run `Launch Physarum.command` on macOS, or `desktop/viewer.py` after the README setup. The C++ engine computes the default experiment, saves it, and pauses at the initial patch. Press **Play growth**. The animation replays actual computed snapshots; the playback rate changes viewing speed, not model parameters.

- **Pale dots** are station food sites not yet visited.
- **Green dots** have been visited by a live particle at least once. This is a contact history, not evidence of a permanent connection.
- **Gold trails** show recent simulated movement activity. Repeated traffic replenishes a trail; unused signal diffuses and decays. The image is a scalar field, not a set of station-to-station straight lines or cosmetic curve interpolation.
- **Show individual live particles** adds the current occupied cells over the trail. The particles represent portions of simulated material, not separate organisms.
- The **explanation panel** describes the current stage from recorded counts. The two plots show visits and population up to the current frame. Click a food site for its name and first-contact status at that frame.

Use **Start at** to try Euston, Waterloo or another selected station, then **Compute growth experiment**. Use the same random seed to repeat a setup. Change food attraction or the division interval to explore sensitivity. A smaller division interval permits more frequent local growth attempts. The resulting differences need controlled repeated experiments before interpretation.

**Restore King's Cross example** resets the scene and parameters to an uncomputed preview; compute again to apply it. Changing controls keeps the current recorded experiment on screen with an explicit draft message. The File menu saves/opens complete growth scenarios and recorded run folders. It also opens the previous station-connection experiment and the four-node validation viewer. CLI flags `--network` and `--fixture` open those directly.

## Which part comes from the Tokyo paper?

[Tero et al. (2010), Fig. 1](https://markfricker.org/wp-content/uploads/2015/12/tero_et_al-2010-science-327-439.pdf) shows a **living** Physarum inoculum placed at Tokyo, spreading toward 36 food sites representing cities. The paper's **numerical** model in Fig. 4 starts with a pre-existing fine mesh and adapts tube conductivity under randomly chosen food-source pairs. Those are different experimental procedures.

The existing C++ pressure-flow solver implements the Tero conductivity law. Exact-zero edges cannot grow under that law alone: zero conductivity gives zero flow and zero reinforcement. Revealing a precomputed mesh would not implement outward colonization.

This mode therefore uses a **separate Jones-inspired chemotactic particle model**, retaining the one-start/food-layout idea as a qualitative laboratory analogy. [Jones (2010), Artificial Life 16(2), 127–153](https://doi.org/10.1162/artl.2010.16.2.16202) describes three forward sensors, orientation, movement, deposition and trail diffusion. [Jones and Adamatzky's manuscript](https://arxiv.org/abs/1212.0023) describes related particle sensing, single-site occupancy and external stimuli. The inoculum, population rules, cue geometry/suppression, boundaries and parameters below are explicit choices for this implementation. It is **not an exact reproduction** of either paper or a biological calibration. No claim of novelty is made.

## Complete implementation protocol, version 1

The selected stations retain their frozen TfL coordinates, transformed to EPSG:27700 in kilometres. The arena spans their bounding box plus a 1.2 km margin. It has 480 columns by default; square cells determine the number of rows. These map distances place the food sites in a scaled experimental layout. They do not imply kilometre-scale biological growth, railway construction or calibrated speed.

The initial state contains 220 particles sampled without replacement on occupied grid cells inside an 11-cell-radius disk centred at the starting station. Each has a uniformly sampled orientation. Initial trail is 5 at occupied cells and zero elsewhere. No global mesh, predetermined route or global particle population is initialized. The default food marker at the start is already visited at update zero.

Each update follows this order:

1. Shuffle the existing particle order using the recorded RNG. Each particle samples forward, left and right at distance 9 cells, sensor angle 45°. Signals are sampled by the containing grid cell.
2. The sensory signal is `trail + food_cue − aversion × river_mask`. If forward is below both side signals, choose a random left/right turn. Otherwise turn toward the stronger side if it exceeds forward. The rotation angle is 45°. Ties preserve heading. This is a discrete choice rule, not a pressure solve.
3. Attempt a one-cell-length forward move. Leave the arena, enter a blocked cell or enter another occupied cell: stay in place and randomize heading. Successful movement adds 5 trail units at the target cell. Moving within the same grid cell is allowed, with continuous sub-cell position retained.
4. Every fourth update, a successfully moving particle in a sparse 9×9 neighbourhood (1–20 occupied cells, including itself) may create one child in a randomly chosen empty, accessible cell in its immediate 3×3 neighbourhood. Newly created particles move on the next update. Total population is capped at 14,000 as a computational bound.
5. On those same update boundaries, particles in completely full 5×5 neighbourhoods (more than 24 occupied cells) are removed. Removal decisions use a fixed occupancy snapshot. These are particle-creation/removal rules, not measured cellular division or a nutrient mass balance.
6. A food site records first contact when a **live particle** is within four grid-cell units of its coordinate. Diffused signal cannot count as contact. Contact is permanent in the history, even if the site is subsequently abandoned.
7. Apply a simultaneous 3×3 mean filter to trail, then multiply by `1 − decay`, with decay=0.08. Out-of-arena or blocked neighbours reflect the current cell value. Blocked cells remain zero. This conserves trail mass before decay on the accessible lattice, up to float32 rounding. Particle deposition continually adds signal; trail is not conserved biomass.

The synthetic food cue is the maximum of broad Gaussian cues:

```
food_cue(x) = strength × max_f [ w_f × exp(−distance(x, food_f)^2 / (2 × range^2)) ]
```

Default strength=8, range=30 cells, and `w_f=1` before contact, `0.05` after first contact. Cues are recomputed when contact status changes. This is an explicit analytic stimulus field, not a physical solution for nutrient diffusion or finite food reserves. Every food site has equal strength. Suppressing a site permanently after its first visit can cause later loss of its connection; that behaviour must not be mistaken for maintaining a transport service.

Random choices use a specified xorshift32 generator and integer-to-real mapping, not a platform library distribution. Seed zero maps to the documented nonzero fallback `0x9e3779b9`. The same build and inputs are checked for exact replay. Floating-point trigonometric differences across compilers/platforms can eventually change stochastic trajectories; cross-platform bitwise identity is not promised.

Default run: seed=42, 1,600 updates, one snapshot every 10 updates, turn angle=45°, Thames aversion=0. The initial patch, 46 equal food sites and all settings are recorded. Hidden numerical parameters remain in the scenario file; changing resolution changes distances in cell units and requires its own sensitivity study.

## Geography and restrictions

The Thames is a real OSM centreline. With default aversion=0 it is only a geographic guide. Optional aversion subtracts a synthetic repellent from sensor readings in a three-cell-wide rasterized river band. It is an analogy to environmental inhibition, **not** tunnel cost, river depth or realistic bank geometry. Cues and trail can influence particles across an obstacle; particles are restricted by destination-cell accessibility. No continuous collision geometry or railway curve-radius constraint is implemented.

Scenarios can contain the same user rectangular restrictions as the geographic experiment; their cell centres define inaccessible grid cells. Growth can fail to reach food isolated by restrictions, and it is not silently rerouted by an invented connection. Added junction nodes are ignored by this model because only station food sites define the experiment. Surface elevation never changes growth. Sources and licences remain in [the frozen geographic data record](../data/london/README.md).

## Records, checks and limits

Each run is saved under ignored `results/growth_runs/` with:

- `scenario.json`: complete scene, settings, arena extent, exact grid parameters, assumptions and source/binary hashes.
- `inputs/`: C++ config, food coordinates, blocked-cell and river masks.
- `output/trail.f32`: all recorded float32 trail fields; `occupied.u8`: binary live-particle occupancy snapshots. Layout is frame, row, column; rows increase northward. Files are little endian.
- `output/stats.csv`: frame, update, live particles, food sites ever visited, occupied cells, trail mass, cumulative particle births and removals.
- `output/food.csv`: exact first-contact update for each food site, or −1 if never visited; `metadata.txt`: model/compiler/format details.
- `checksums.json`, engine log, and a failure record when a run fails or is cancelled. Keep the entire folder to preserve an experiment.

The loader checks dimensions, ordering, finite/nonnegative fields, occupancy uniqueness/counts, population accounting, contact counts, initial-patch locality, mask exclusion, initial trail, scenario/config/coordinate agreement and file checksums. These are record-integrity checks, not biological validation or a proof of connected topology. Cancelling/closing requests termination of the owned C++ process and preserves available inputs/partial output.

The display uses one fixed trail range 0–15, saturating brighter values only in the rendering; raw signal remains intact. Live particles are an optional separate overlay. No smoothing is used to invent railway alignments. Natural-looking curves in this raster field still do not demonstrate that a train could follow them.

C++ checks cover the independent 3×3 diffusion stencil and decay/mass at a reflecting corner, seeded replay, local initialization, single-cell occupancy, population accounting, impermeable barriers, first-contact semantics and invalid inputs. Python tests cover replay, corrupted records, field/count agreement, input validation, context separation, frame synchronization, explanation/selection state, draft controls and worker cancellation. A controlled statistical/resolution study and biological data comparison remain future work.

Recompute the illustrated example with `.venv/bin/python analysis/make_growth_figure.py --gif`. It saves raw output and exports measured snapshots, an animation and a compact provenance JSON. No rail-network performance or biological-accuracy conclusion follows from the animation alone.
