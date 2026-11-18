# Exploratory biological growth laboratory

The default native application now runs a **mechanistic exploratory-migration benchmark**, before the separate London transport experiment. It is a working research prototype, **not a quantitatively reproduced paper or a biologically validated digital organism**.

The earlier particle trail model was insufficient for interpreting an expanding living body or persistent veins. Narrowing its glow would not repair that distinction. This laboratory instead couples an advancing reaction–diffusion margin, calcium/phosphorylation dynamics, pressure, compliant fluid flow and vein adaptation.

## Sources and an unresolved reproduction issue

1. D. Schenz, Y. Shima, S. Kuroda, T. Nakagaki and K.-I. Ueda (2017), *A mathematical model for adaptive vein formation during exploratory migration of Physarum polycephalum: routing while scouting*, J. Phys. D **50**, 434001. [DOI](https://doi.org/10.1088/1361-6463/aa88e9), [author-hosted paper](https://labkuroda.web.fc2.com/myarticles/SchenzD_ETAL_2017_print.pdf).
2. D. A. Smith and R. Saldana (1992), *Model of the Ca²⁺ oscillator for shuttle streaming in Physarum polycephalum*, Biophys. J. **61**, 368–380. [DOI](https://doi.org/10.1016/S0006-3495(92)81843-X), [primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC1260253/).
3. D. T. Schenz, doctoral thesis, chapter 4 and the chapter 2 oscillator derivation. [University repository](https://eprints.lib.hokudai.ac.jp/repo/huscap/all/74323/Daniel_Thorsten_Schenz.pdf).

The 2017 printed activation expression is `kQ × z`, with `z = K* nc/(1 + K* nc)`. With its listed coefficients, our isolated integration settles to approximately c = 3.48847 and φ = 0.84768. It does not generate the limit cycle described in the surrounding text.

Smith & Saldana's Eq. (5) includes a Hill power β; Table 1 on page 371 gives β = 4. The thesis also includes this exponent in its underlying oscillator derivation. The default therefore uses **z⁴ as an explicitly named cooperative variant**, while retaining the later fitted free-calcium relation and later parameters. This combination is **not the complete original 1992 oscillator**, nor a claim to have resolved the later paper's intent. The printed exponent-1 control remains selectable. Both are tested independently before spatial coupling.

There is another notation inconsistency: the 2017 summary Eq. (11) writes Γ(v), whereas its definition and Eq. (8) gate by body thickness w. We follow the explicit definition and Eq. (8), **Γ(w)**.

These choices are recorded, not hidden corrections. Access to the original numerical code or clarification of the equations would be needed to establish an exact reproduction. No source PDFs or microscopy images are redistributed.

## State and equations

Nodes carry calcium c, phosphorylation φ, regulatory field u, margin activator v, accumulated body proxy w, and pressure p. Edges carry signed flow q and conductivity D. These are **model variables with uncalibrated units**.

For the fitted calcium subsystem:

```
nc(c,φ) = [1 + 0.17(c − 7.5)]
          × (0.349353 − 0.0454567φ + 1.15905φ² + 1.823858φ³)
z = 1.75 nc / (1 + 1.75 nc)
F = −0.12 nc + 0.004(25 − c)
G = z^β (1 − φ) − 0.1φ
τ₁ c_t = F + 0.2 Δc
τ₁ φ_t = G + 0.012 Δφ
```

τ₁ = 0.0072, divided by three in the inoculum, which acts as a faster pacemaker. β is either the printed 1 or the explicit cooperative variant 4. The empirical nc fit can become negative during the published initial transient; exponent 1 can also produce negative φ there. We retain those values in that control rather than silently clipping them. This is a limitation of the fitted subsystem, not a physical prediction of negative concentration.

The advancing margin follows:

```
u_t = (0.2 Δu − uv²)/τ₂
v_t = (0.02 Δv + uv² − 0.01v)/τ₂ + k B(w) Σincident D
w_t = 0.1v/τ₂
B(w) = 1 for 0.1 ≤ w ≤ 0.9; otherwise 0
```

The conductivity sum is the unnormalised sum over incident mesh edges, as defined in the source. This discrete feedback can depend on mesh construction. u is a **regulatory factor, not an explicit nutrient budget**.

For an oriented edge i → j of model length ℓ:

```
L̃ = ℓ/(10 + 5√D)
R̃ = ℓ/(2.5 + 13.5D)
Ĉ = (0.1 + 0.03D^(3/4)) (1 + 0.01v̄) / ℓ
L̃ q_t = p_i − p_j − R̃q
p_t = −B diag(1/Ĉ) q − (c − 7)
D_t = Γ(w̄) |q|^1.3/(1 + 0.01|q|^1.3) − 0.15D
Γ(w̄) = 1 if w̄ > 1; otherwise 0
```

Here B is the node-edge incidence matrix with +1 at the outgoing end; bars average the endpoints. **Compliance divides by edge length.** A source-equation audit caught and corrected an initial prototype multiplication before the archived study. Pressure is dynamic, not an instantaneous Kirchhoff solve. Wall storage permits differing inflow and outflow. Pressure is not artificially grounded.

The regularising constants in L̃, R̃ and Ĉ are in the published model. They keep the mathematical background fluid network finite even at D = 0; they are not numerical conductivity floors. Chemical fields and that background network exist over the full computational arena, including unoccupied regions. Only reinforcement is body-gated. That construction should not be interpreted as fluid or calcium physically living in empty agar.

## Arena and initial state

The bent corridor approximates the rectilinear arena in the paper's figure: width 5, bounding box 40 × 15, area 350 model units². It is assembled from seven exact rectangles. The precise experimental substrate dimensions and the authors' triangulation are not recovered. A straight 40 × 5 corridor is available as a control.

The inoculum is Ω₀ = [39,40] × [0,5]. Initially p = q = φ = w = 0, u = 3 everywhere, c = v = 1 in Ω₀ and zero elsewhere. D = 0.1 on edges with either endpoint in Ω₀ and zero elsewhere. The initial inoculum ring is displayed separately because the source initialises w to zero even there.

The default uses **τ₂ = 2**, one of the front-timescale contrasts discussed by the source, to make complete arena exploration practical. The **source-front-timescale control uses τ₂ = 20**, the listed baseline. Both retain τ₁ = 0.0072 here; changing their ratio is a substantive experiment. The default also changes the Hill exponent as described above, so neither preset is labelled an exact paper reproduction.

## Spatial and time discretisation

A seeded, jittered triangular lattice and exact sampled boundary are triangulated. Triangles crossing a corridor wall are rejected by partitioning each edge at every rectangle boundary, not by sparse point sampling. The mesh must cover the known arena area, have strictly positive lumped masses, nonnegative assembled cotangent weights and a connected diffusion graph. Invalid meshes are rejected; no negative weights are clipped. The default spacing 0.5 gives 1,643 nodes and 4,626 edges at seed 42. The frozen CSVs, not a seed alone, define a replay across library versions.

Reaction–diffusion fields use lumped linear finite elements with zero normal flux. Each step applies:

1. Half a local reaction step using RK4, internally subdivided to at most 0.005 time units.
2. A full backward-Euler diffusion solve `(Mτ + Δt D K)x_new = Mτ x_old` for c, φ, u and v.
3. The other half reaction step, with the preceding vein state held fixed.
4. A frozen-coefficient Crank–Nicolson pressure/flow solve using the previous D, newly updated v and the endpoint average calcium forcing.
5. A positive exponential-decay vein update using midpoint flow and the newly updated body gate.

This composition is **overall first order**: implicit Euler diffusion and lagged/gated coupling limit its accuracy. Calling the pressure substep Crank–Nicolson does not make the complete model second order. The discontinuous gates further limit smooth-order arguments. The default is Δt = 0.02; comparisons at 0.01 are archived. There is no claim of spatial or long-time morphological convergence.

The pressure solve eliminates edge flows to a symmetric positive-definite node system and reuses its symbolic factorisation. Its residuals are independently checked against the compliant-storage and momentum equations. For coefficients held over that substep,

```
E = ½ ||p||² + ½ Σ (L̃/Ĉ) q²
ΔE = −Δt Σ (R̃/Ĉ) q_mid² − Δt p_mid · (c_mid − 7)
```

The energy diagnostic checks **this frozen linear substep**, not energy conservation of the coupled living organism. Updating D and v changes its coefficients. A separate test verifies conservation of `Σ mass × (u + v + 0.1w)` when k = 0, an invariant of the stated front equations with no-flux boundaries. This invariant is **not total biological mass conservation**.

## What you can inspect

Double-click `Launch Physarum.command`, compute, then press **Play growth**. The app reuses a complete matching local record when its engine source still matches. **Follow colony** keeps the expanding footprint visible; turn it off for the full arena.

- Body colour is the piecewise-linear w field: unoccupied arena, advancing band, transition, accumulated body. It is not predicted optical intensity.
- Fine veins are the actual mesh D values. Width is proportional to D¼, with a fixed scale of 0.5 pt at D = 1. The adjustable cutoff only affects rendering. Raw D is never clipped or pruned.
- **Advancing margin** shows v, and **Calcium** shows c over the computational domain. Their colour scales are fixed and labelled.
- Occupied area uses the lumped-node quadrature of w > 1. It is an approximate area measurement, not an exact level-set area.
- Full fields are saved every 8 model units by default. They cannot resolve the roughly unit-period calcium oscillations. The fixed inoculum-node calcium probe and its explicitly identified incident-edge flow are therefore saved **every integration step**. The lower plot shows an eight-unit probe window and signed flow, including reversals.
- Figure exports include SVG, PNG, node-field CSV, edge-flow/conductivity CSV and a JSON record reference with the cutoff and source fingerprint.
- Complete records save automatically under `results/biology_runs/`. Open a copied complete folder to inspect it on another computer. Checksums, initial conditions, positivity, monotone w, body gating, timing, summaries and source fingerprints are checked when loading.

Use **Other models → London tube adaptation** or `--tubes` for the existing food-site network experiment. The older particle model and analytic fixture remain available. The biological corridor and transport models are intentionally distinct experiments.

## Limits and next biological targets

This model does not yet implement food chemotaxis, uptake, finite biomass, body retraction, realistic membrane mechanics, biochemical concentrations, calibrated cell dimensions or experimental hours. Passing a mathematical balance test does not validate those missing processes. A connected occupied footprint also does **not** prove a connected mature vein graph.

The current variant explores the fast-front arena and produces signed oscillatory flow, but its final surviving-vein morphology does not reproduce the paper's centre-in-centre patterns quantitatively. The source-timescale control advances substantially less by the same endpoint. These mismatches and sensitivity to mesh/step are part of the evidence, not discarded failures.

Before extending to London, the priorities are resolving the calcium-model discrepancy, testing vein morphology against digitised corridor experiments with documented uncertainty, and introducing a separately identified food-response model with uptake and biomass accounting. Food-site connectivity must then be measured on actual surviving veins, not inferred from first visits or a glowing trail.
