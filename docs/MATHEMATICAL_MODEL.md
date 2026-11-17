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
