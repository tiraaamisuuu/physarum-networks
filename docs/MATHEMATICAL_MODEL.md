# Mathematical model and numerical contract

## Published starting point

Tero et al. (2010), Science 327, 439-442, Eq. (1) and the model text on pp. 441-442, define a fixed network of tubes with lengths L, conductivity D and pressure p. The uploaded `slimemold.pdf` contains this article; its cover page shifts PDF page numbers. In particular, PDF page 4 shows Eq. (1) and the adaptation rule. The model is an abstraction of transport adaptation, not a simulation of all cell physiology.

For an edge oriented from u to v for bookkeeping,

\[
w_e=D_e/L_e, \qquad Q_e=w_e(p_u-p_v).
\]

L is fixed, positive and finite. D is nonnegative. Q is signed: a negative value means flow against the stored orientation. D is proportional to the fourth power of physical tube radius when viscosity is fixed; it is not the tube diameter or edge conductance w itself.

Let B have +1 at each edge's stored from-node and -1 at its to-node. Then

\[
Q=\mathrm{diag}(D/L)B^T p,\quad BQ=b,\quad
A p=b,\quad A=B\mathrm{diag}(D/L)B^T.
\]

b is +I0 at the source, -I0 at the sink and zero elsewhere. This sign convention makes BQ the outgoing flow at each node. A has diagonal entries equal to the sum of incident conductances and negative off-diagonal entries. Parallel edges contribute additively. This is a global pressure solve, despite the local form of the subsequent adaptation rule; the current implementation is not a distributed solver.

## Grounding and solvability

Adding a constant to all pressures in a connected component leaves Q unchanged, so its Laplacian has a constant null vector. The solver removes the sink's row and column, sets its pressure to zero, and solves for the remaining pressures. The reduced matrix is symmetric positive definite on a connected positive-conductance component. At the removed node, conservation follows from the other equations and sum(b)=0, and is also checked explicitly.

For exact zero conductivities, detect components using only strictly positive conductances. If source and sink lie in different components, their component demands do not balance and the problem is infeasible: fail with an error. If other components have no demand, ground one node in each; the unique grounded solution there is zero pressure and zero flow. Absolute pressures in different components have no physical relationship.

No small positive weight is treated as zero. To reduce numerical scale disparity, with the reduced A define S=diag(1/sqrt(A_ii)), solve

\[
H y=S b,\quad H=SAS,\quad p=Sy.
\]

Use Eigen's dense LDLT factorization. Report its reciprocal condition estimate for H and reject values below 1e-14. This threshold is a numerical safeguard, not a pruning parameter. Detect nonfinite values and conductance underflow explicitly. Extremely ill-conditioned networks may be mathematically connected yet numerically unresolved. A tiny uniformly scaled conductivity is not necessarily ill-conditioned: the tested single-edge case D=1e-200 gives the correct flow with a large pressure.

## Adaptation and time discretisation

The 2010 paper specifies

\[
\dot D_e=f(|Q_e|)-D_e,\qquad
f(q)=\frac{q^\gamma}{1+q^\gamma},\quad \gamma>0.
\]

The implementation evaluates an equivalent form 1/(1+(1/q)^gamma) when q>1 to avoid exponentiation overflow. f(0)=0. No substitute linear reinforcement law is used.

All flows at time k are computed from the same conductivity vector, followed by simultaneous explicit Euler updates:

\[
D_e^{k+1}=(1-\Delta t)D_e^k+\Delta t\,f(|Q_e^k|).
\]

For 0<dt<=1, this is a convex combination of D and f>=0. Thus nonnegativity is preserved in exact arithmetic; if initial D<=1, it also stays <=1. dt>1 is rejected rather than clipped. This bound alone is not a stability theorem for the coupled flow-adaptation system. Euler is first order on smooth, resolved trajectories; check a fixed-duration transient with smaller steps. Identical equilibrium values can hide substantial transient error.

With no flow, the continuous solution is D(t)=D(0) exp(-t), whereas Euler gives D_k=D_0(1-dt)^k. Positive conductivities approach zero without becoming exactly zero in exact arithmetic when dt<1. There is no floor, clipping or deletion. The implementation stops if a positive D underflows to zero at dt<1; at dt=1 a zero-flow edge is legitimately mapped to zero by Euler. Existing exact-zero edges carry no flow and cannot revive under this rule.

## Independently verifiable fixtures

Series edges with L=(2,3), D=(4,2), I0=2 have resistances (0.5,1.5). Grounding the last node gives p=(4,3,0), Q=(2,2).

Two parallel edges with L=(1,3), D=(1,1), I0=4 have conductances (1,1/3). The pressure difference is 3 and the flows are (3,1).

For the four-node experiment, edges are (0,1,L=1), (1,3,L=1), (0,2,L=2), (2,3,L=2). With D=0.5, the route resistances are 4 and 8, giving equivalent resistance 8/3, p=(16/3,8/3,8/3,0) and route flows 4/3 and 2/3. At any later time, compute route resistance as the sum of L/D along that route, compute the two route conductances in parallel, and recover flows and internal pressures without solving a matrix. The Python validation uses this independent reduction for every baseline state.

A single edge has Q=I0 independent of D and L, so its Euler recurrence is exactly

\[
D_k=f(I_0)+(D_0-f(I_0))(1-dt)^k.
\]

For gamma=2, I0=2, D0=0.2, dt=0.1, f=0.8 and the first update is D1=0.26. This test isolates the update from network selection effects.

If the long route carries zero flow, its equilibrium conductivity is zero and the short-route equilibrium is f(2)=0.776895386796 (gamma=1.8). The experiment approaches this equilibrium. This calculation identifies a possible equilibrium; it does not prove global attraction. In particular, Bonifaci et al.'s shortest-path proof studies f(q)=q and unit injected flow; its theorem must not be transferred to this sigmoid model.

## Error measures and tolerances

Report maximum conservation error over **all** nodes, including reference nodes:

\[
r_c=\|BQ-b\|_\infty.
\]

For the grounded, unscaled pressure system also report a normwise backward error:

\[
r_b=\frac{\|A p-b\|_\infty}{\|A\|_\infty\|p\|_\infty+\|b\|_\infty}.
\]

Accept rc<=1e-12+1e-10 I0 and rb<=1e-12. These limits leave room above double precision roundoff for small resolved problems and scale the conservation check with demand; they are not universal physical error bounds. The absolute term becomes permissive for extremely small injected currents. Condition estimation and nonfinite-value checks provide additional safeguards; the supported research regime is the small dimensionless fixture, not arbitrary extreme data. Backward error alone does not bound forward pressure error in ill-conditioned systems.

Tests use explicit error checks that run in Release builds, rather than C/C++ `assert` macros. Analytic fixtures use absolute tolerances of 1e-12 where values are order unity. Actual measured errors, the step-size study, and the finite-reference limitation are recorded in the generated results.

## Deliberate differences and unresolved source details

- Published: random food-source pair at each time step, fine random mesh, initial conductivity fluctuations; Tokyo represented by seven food sources in Fig. 4. Phase 1: fixed 0->3 pair, four-node graph, uniform D0=0.5, deterministic updates. Those are validation choices required to isolate the mathematics.
- I0=2 and gamma=1.8 match example parameter values in the paper; that does not match its experimental setup.
- Euler dt=0.05, duration 30, initial 0.5, solver, scaling and tolerances are our choices. The inspected article and figures S1/S2 do not specify a complete numerical reproduction protocol, including exact mesh construction, initial fluctuation distribution or integrator schedule.
- There is no reporting threshold or inferred discrete topology in Phase 1. Raw conductivities are exported. Very small D does not constitute a deleted edge.
- Mathematical local feedback does not establish transport-system feasibility, biological fidelity, originality, general convergence, resilience or favourable infrastructure trade-offs.

Primary source: https://doi.org/10.1126/science.1177894. Source inventory and bibliography are in `LITERATURE.md` and `references.bib`.

## Fine-mesh sparse experiment (18 November 2026)

The default native laboratory now uses the same pressure–flow and sigmoid law on a fine London mesh. `SparseFlowSolver` requires a fixed connected graph with strictly positive conductivities, unlike the dense baseline's support for exact-zero edges and separate demand-free components. Background components without food are removed **before initialization**. The sparse solver never prunes edges or floors conductivity. It fixes pressure at node 0, independent of the current sink, and reuses symbolic factorization for the fixed sparsity pattern.

Grounded A is diagonally scaled to unit diagonal H; Eigen SimplicialLDLT solves H. The pressure solution is checked in the original unscaled system with the same conservation/backward-error limits described above; up to two corrections follow the initial solve. Positive finite factor pivots are required. `scaled_rcond_estimate` is `1/(||H||₁ × estimated ||H⁻¹||₁)` using a Hager-style procedure capped at six iterations. H is symmetric, so its 1- and infinity-norms agree. **This is an estimated diagnostic, not Eigen's dense rcond, a rigorous condition bound or a forward-error certificate.** Estimates below 1e-14 reject the state. Scale overflow and nonfinite states also reject it.

The mesh CLI records every state as float64 D/Q/P and diagnostics, preserving input edge orientations and actual forcing. The loader independently checks Q=(D/L)Δp, Kirchhoff balances, Σ Q²L/D = I₀(p_source−p_sink), every simultaneous Euler transition and file checksums. Default condition estimates remain well above the rejection limit in the recorded London study. Small residuals validate the solved equations, not biological fidelity or integration accuracy.

The native display explicitly extracts a graph at a user-selected conductivity cutoff; raw D and dynamics are unmodified. Global food connectivity, retained physical length, shortest-path stretch and a defined length-weighted single-break proxy are measured on that graph. The proxy is not the paper's fault-tolerance statistic. A terminal-only Euclidean MST is a reference, not a Steiner lower bound. Full construction, forcing, metric definitions and unresolved assumptions are in [TUBE_EXPERIMENT.md](TUBE_EXPERIMENT.md); measured integration/mesh/seed/cutoff sensitivity is in [the study](../results/mesh_validation/REPORT.md).

## Two-stage Heun / SSPRK2 and source binding

The current fine-mesh default uses dt=0.0125 and Heun; the original dense baseline and legacy Euler archive are unchanged. For F(D)=f(Q(D))−D, Heun is implemented as an Euler predictor D*, a second steady pressure solve at D* with the held forcing, and D_next=0.5 D+0.5[(1−dt)D*+dt f(Q*)]. Both pressure solves must pass the same acceptance criteria. This convex form preserves positivity in exact arithmetic for 0<dt≤1; the supported mesh interface restricts dt≤0.25 and rejects nonfinite/underflowed states. All update components use frozen stage flows, not partially updated edge values.

The pair remains fixed throughout a step, including a predictor evaluated at a demand-switch endpoint. The next accepted state then uses the new recorded pair. Refinement divides the switching interval exactly. Predictor Q/P and diagnostics are retained; the reader independently reconstructs D*, validates both hydraulic systems and the correction recurrence. Formal second-order convergence is verified on an analytic scalar problem. London finite-reference differences decrease substantially versus Euler but do not show a uniform factor of four at the tested coarser steps; no general accuracy order or converged topology is inferred from the formal method.

CMake embeds a SHA-256 fingerprint over the C++ sources, headers and CMake description. New run snapshots preserve those files and Python/analysis code, with checksums. Reopening validates snapshot bytes, recomputes the C++ fingerprint and compares it with engine metadata. These are provenance/integrity checks, not a cryptographic authenticity guarantee for a record from an untrusted author. Exact frozen graph/initial/forcing inputs support independent current-code replay. The [current integration report](../results/integration_validation/REPORT.md) preserves source-complete cases and a finer-step comparison.
