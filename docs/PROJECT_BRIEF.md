# Physarum — Computational Research Project
## Master Project Brief & Development Instructions

### 1. Project Overview

I am a first-year BSc Computer Science student at Royal Holloway, University of London, beginning an independent research project investigating **biologically inspired adaptive transport networks**.

My long-term ambition is to conduct meaningful original computer science research, potentially publish an academic paper, and develop my mathematical and research abilities in preparation for postgraduate study, particularly Oxford's MSc Advanced Computer Science.

This must be treated as a **serious scientific research project**, not simply a visually impressive simulation or programming exercise.

The central inspiration comes from the ability of the slime mould *Physarum polycephalum* to develop efficient transport networks through decentralised, flow-dependent adaptation.

I am also interested in fungal mycelium, whose network growth, fusion, resource redistribution and response to damage may provide an alternative biological model.

The eventual goal is to investigate whether biologically inspired network-forming and network-adapting processes can produce effective transport networks under changing conditions.

Potential applications include railway networks, urban transport networks, bus routes and regional transport infrastructure in the UK.

**Important:** This project will be developed incrementally. Do not attempt to implement the entire research vision immediately.

---

### 2. Primary Research Question

Our initial working question is:

**Can biologically inspired network adaptation produce efficient, resilient and computationally practical transport networks under changing demand and environmental conditions?**

This is provisional.

We must investigate the existing literature thoroughly before claiming originality.

Possible research extensions include:

- Comparing Physarum-inspired adaptation with fungal mycelium-inspired growth.
- Investigating how networks respond to changing origin–destination demand.
- Studying network recovery following disruption or link removal.
- Analysing trade-offs between infrastructure cost, journey efficiency and resilience.
- Comparing biological algorithms against conventional network optimisation approaches.
- Investigating convergence, stability, computational complexity and scaling.
- Exploring whether different local adaptation rules produce different emergent network topologies.

Do not attempt all these directions simultaneously.

First reproduce the established mathematical model accurately. Then use experimental results and a literature review to narrow the project to one defensible research contribution.

### 3. Scientific References

**Primary reference:**

Tero, A., Takagi, S., Saigusa, T., Ito, K., Bebber, D. P., Fricker, M. D., Yumiki, K., Kobayashi, R., & Nakagaki, T. (2010).

*Rules for Biologically Inspired Adaptive Network Design.*

Science, 327(5964), 439–442.

DOI: https://doi.org/10.1126/science.1177894

This paper provides the principal adaptive network model we intend to reproduce.

I previously uploaded a PDF of this paper to the ChatGPT project. Locate and read it if available.

**Secondary reference:**

Fricker, M. D., Heaton, L. L. M., Jones, N. S., & Boddy, L. (2017).

*The Mycelium as a Network.*

Microbiology Spectrum, 5(3), FUNK-0033-2017.

DOI: https://doi.org/10.1128/microbiolspec.FUNK-0033-2017

PDF previously uploaded as `microbiolspec.funk-0033-2017.pdf`.

Especially relevant topics include:

- Graph-theoretic representations of fungal networks.
- Conversion of real fungal networks into graphs.
- Spatially explicit network growth models.
- Biological transport networks.
- Network robustness and resilience.
- Hyphal fusion and loop formation.
- Biomass recycling and network restructuring.

Additional useful literature:

**Tero, Kobayashi & Nakagaki (2007)**  
*A Mathematical Model for Adaptive Transport Network in Path Finding by True Slime Mold.*

https://doi.org/10.1016/j.jtbi.2007.06.015

**Bonifaci, Mehlhorn & Varma (2012)**  
*Physarum Can Compute Shortest Paths.*

https://doi.org/10.1016/j.jtbi.2012.06.019

**Bebber et al. (2007)**  
*Biological Solutions to Transport Network Design.*

https://doi.org/10.1098/rspb.2007.0459

These references should be used to understand established models and identify relevant algorithms, mathematical properties and unresolved questions.

Verify relevant literature rather than assuming that a proposed extension is novel.

Maintain an organised bibliography with accurate references.

---

### 4. Mathematical Foundation

The starting point is the adaptive tube network model described by Tero et al.

A network is represented as a graph:

\[
G=(V,E)
\]

Each node represents a junction or resource location.

Each edge \((i,j)\) possesses:

- Length \(L_{ij}\)
- Conductivity \(D_{ij}\)
- Flow \(Q_{ij}\)

The pressure at node \(i\) is \(p_i\).

Flow through each connection is determined by:

\[
Q_{ij}=\frac{D_{ij}}{L_{ij}}(p_i-p_j)
\]

Flow conservation applies at the network nodes.

For a single source \(s\) and sink \(t\), with injected flow \(I_0\):

\[
\sum_j Q_{ij} =
\begin{cases}
I_0 & i=s \\
-I_0 & i=t \\
0 & \text{otherwise}
\end{cases}
\]

This yields a weighted graph Laplacian system for node pressures.

The pressure system is singular without a reference pressure, so one node should be grounded or an equivalent mathematically justified approach should be used.

Tube conductivities evolve according to:

\[
\frac{dD_{ij}}{dt}=f(|Q_{ij}|)-D_{ij}
\]

where the reinforcement function is:

\[
f(|Q|)=\frac{|Q|^\gamma}{1+|Q|^\gamma}
\]

The parameter \(\gamma\) controls the nonlinearity of reinforcement.

A simple numerical implementation can initially use explicit Euler integration:

\[
D_{ij}^{(k+1)} =
D_{ij}^{(k)}+
\Delta t
\left[
\frac{|Q_{ij}^{(k)}|^\gamma}
{1+|Q_{ij}^{(k)}|^\gamma}
-D_{ij}^{(k)}
\right]
\]

However, do not assume Euler integration is always stable.

Investigate:

- Time-step sensitivity.
- Numerical accuracy.
- Preservation of nonnegative conductivities.
- Near-zero conductivities.
- Disconnected or nearly disconnected networks.
- Conservation of flow.
- Pressure-solver residuals.
- Convergence behaviour.

The 2010 paper explores parameters including \(I_0=2.0\) and \(\gamma=1.8\).

These are useful reference values, but reproduce the experimental setup carefully before claiming matching results.

For the original model, source and sink selection should follow the published experimental procedure.

Do not silently substitute a different reinforcement law, node-selection procedure or pruning mechanism.

If we deliberately introduce modifications, document them clearly as extensions.

### 5. Important Conceptual Distinction

We are not simply implementing Dijkstra's algorithm or A*.

Those algorithms find paths through an existing network.

Our adaptive model modifies the network's properties through repeated flow-dependent updates.

We want useful network structure to **emerge from the mathematics**, not from explicitly coded rules such as:

> If an edge is inefficient, delete it.

Any threshold-based pruning used for reporting or visualisation must be distinguished from the actual conductivity dynamics.

Also, do not confuse a physically faithful model of living slime mould with a mathematical model inspired by one.

Our implementation reproduces an established abstraction of Physarum's transport-network adaptation, not every aspect of the organism's biology.

---

### 6. Development Environment

**Primary development machine:**

Apple MacBook Air M3 (Apple Silicon, ARM64).

Confirmed installed:

- Apple Clang 17.0.0
- CMake 4.0.2
- Homebrew 7.0.9

Eigen installation was recommended but has not yet been confirmed.

The user's desktop PC is temporarily unavailable.

There is also access to Royal Holloway's Linux computers through NoMachine. This may become useful for validation or larger experiment batches, subject to university computing policies.

**Preferred technology stack:**

- C++20 for the simulation engine.
- Eigen for dense and sparse linear algebra.
- CMake for project configuration.
- A lightweight C++ graph representation initially.
- CSV or JSON for experiment data and reproducible configurations.
- Python with NumPy, Pandas and Matplotlib for analysis and plotting.
- Git and GitHub for version control.
- Automated C++ tests.

Prefer portability between macOS ARM64 and Linux.

Avoid unnecessary dependencies and architectural complexity.

Python is intended primarily for analysis and plotting, rather than being the main simulation language.

---

### 7. Initial Project Architecture

Suggested structure:

```text
physarum-networks/
├── CMakeLists.txt
├── README.md
├── .gitignore
├── include/
│   └── physarum/
│       ├── Graph.hpp
│       ├── FlowSolver.hpp
│       └── PhysarumModel.hpp
├── src/
│   ├── main.cpp
│   ├── Graph.cpp
│   ├── FlowSolver.cpp
│   └── PhysarumModel.cpp
├── tests/
├── experiments/
│   └── configs/
├── analysis/
├── docs/
│   ├── PROJECT_BRIEF.md
│   ├── RESEARCH_LOG.md
│   ├── MATHEMATICAL_MODEL.md
│   └── LITERATURE.md
└── results/
```

This is only a suggested structure. Adjust if a simpler design is better.

Keep the core simulation independent of visualisation, experimental orchestration and geography-specific data.

Later, we may introduce multiple interchangeable network adaptation algorithms, including a fungal mycelium-inspired model.

Do not implement that architecture prematurely.

---

### 8. Phase 1 — Establish the Research Foundations

This is the first phase to implement.

**Objective:** Produce a small, mathematically correct and independently testable Physarum-inspired network simulation.

Tasks:

1. Inspect the current project directory and development environment.
2. Confirm Eigen and other necessary dependencies.
3. Initialise or configure a clean C++20/CMake project.
4. Implement a simple graph representation.
5. Implement pressure calculation using an appropriate linear solver.
6. Calculate signed flows for each edge.
7. Implement conductivity adaptation.
8. Create a minimal command-line experiment runner.
9. Record network conductivity values over time.
10. Add tests verifying the mathematics.
11. Document how to build and run the program.

Begin with a synthetic graph containing four or five nodes and two competing routes between a source and sink.

Give those routes different total lengths.

The simulation should demonstrate how conductivities evolve as flow travels through the network.

Compare the dominant resulting route with the known shortest route.

Use independently calculated test cases where possible.

**Definition of done:**

- CMake configures successfully.
- The C++ project compiles.
- Automated tests pass.
- The pressure solver satisfies conservation equations within a justified tolerance.
- Conductivities evolve according to the specified equation.
- Results are deterministic for a fixed setup.
- Numerical output can be plotted.
- The code and experiment are documented.

Do not claim full replication of the 2010 paper merely because a simple network behaves plausibly.

---

### 9. Phase 2 — Reproduce Published Behaviour

Once Phase 1 is validated, progress to a more realistic network.

The objective is to reproduce the qualitative and, where practical, quantitative behaviour reported by Tero et al. (2010).

Investigate:

- Network thinning from a dense initial graph.
- Flow-dependent reinforcement.
- Different values of \(I_0\).
- Different values of \(\gamma\).
- Evolution over many iterations.
- Convergence and stability.
- Emergence of efficient transport networks.

Create visualisations showing the same network at different iterations.

Where possible, reproduce key results or trends from Figure 4 and the reported network performance comparisons.

Clearly report any differences between the published experiment and our implementation.

If supplementary materials are needed, locate and inspect them.

Never invent parameter values or undocumented experimental details.

### 10. Phase 3 — Research Extensions

Do not begin this phase until we have a validated baseline and an adequate literature review.

Potential extensions include:

**Dynamic transport demand**

Instead of assuming a fixed or randomly selected source–sink distribution, investigate nonstationary origin–destination patterns.

For example:

- Morning commuting demand.
- Evening commuting demand.
- Sudden changes in passenger demand.
- Shifting regional population or activity centres.

**Network disruptions**

Investigate how adaptive networks respond to:

- Edge removal.
- Station closure.
- Changes in connection capacity.
- Infrastructure damage.
- Sudden increases in transport cost.

**Comparison with fungal mycelium**

Explore whether fungal-inspired network-growth mechanisms, especially tip growth, branching, fusion and recycling, can form useful network structures under similar constraints.

This should be treated as a distinct biological model rather than assuming it follows the same dynamics as Physarum.

**Conventional optimisation baselines**

Compare against suitable approaches such as:

- Minimum spanning trees.
- Shortest-path-based structures.
- Other established network design heuristics or optimisation methods.
- Nonadaptive versions of the model.

Choose scientifically appropriate baselines depending on the final research question.

The purpose is not to prove that biological optimisation always outperforms conventional algorithms.

A negative result, or the discovery of trade-offs and limitations, can be academically valuable.

---

### 11. Experimental Evaluation

Eventually assess network performance using metrics such as:

**Infrastructure cost**

Total network length, or a more realistic construction/maintenance cost function.

**Transport efficiency**

Mean or demand-weighted shortest-path distance, or a suitable journey-time measure.

**Fault tolerance**

How performance changes when links or nodes fail.

**Adaptation**

How rapidly and effectively the network responds to changing conditions.

**Stability**

Whether the network converges, oscillates or undergoes undesirable restructuring.

**Computational efficiency**

Runtime, memory usage and scaling with network size and connectivity.

Follow sound experimental methodology:

- Fix random seeds where appropriate.
- Perform repeated trials.
- Report variability and uncertainty.
- Use fair baseline comparisons.
- Control infrastructure budgets where relevant.
- Separate model parameters from evaluation metrics.
- Preserve experiment configurations and software versions.
- Never select only favourable results.

As the project develops, consider applying the simulation to geographic data around London, the Midlands or the wider UK.

Potential data sources include OpenStreetMap and publicly available transport datasets.

Do not assume that a biologically generated infrastructure network is automatically economically or geographically feasible.

---

### 12. Research Documentation

Maintain documentation from the beginning.

`PROJECT_BRIEF.md` should describe the objective, phases, scope and long-term research direction.

`MATHEMATICAL_MODEL.md` should explain the mathematics carefully enough that I can understand and independently verify it.

`LITERATURE.md` should track relevant publications, what each contributes, limitations and potential research gaps.

`RESEARCH_LOG.md` should record the questions, parameters, experiments, results, unexpected behaviour and next steps.

The research log should distinguish:

- Published scientific claims.
- Our assumptions.
- Hypotheses.
- Observations from experiments.
- Interpretations of those observations.

The long-term aim is a conventional academic research paper containing:

1. Abstract.
2. Introduction.
3. Related Work.
4. Mathematical Model.
5. Experimental Methodology.
6. Results.
7. Discussion.
8. Conclusion.
9. References.

Do not write speculative results or conclusions before performing experiments.

---

### 13. Development Principles

Treat this as both a scientific and a software engineering project.

**Correctness before performance.**

Use small testable components and independently verifiable numerical results.

**Reproducibility.**

Experiments should be reproducible from documented configurations and seeds.

**Incremental development.**

Each stage should leave the program functional and testable.

**Scientific honesty.**

Do not claim originality without a literature review, or accuracy without validation.

**Performance when justified.**

The MacBook Air M3 should be adequate for initial development.

Profile performance before introducing concurrency, GPU acceleration or complicated optimisations.

**Maintainability.**

Use readable C++20 code, clear interfaces and automated tests.

**Educational transparency.**

I want to understand the mathematics, scientific reasoning and implementation decisions, rather than blindly accepting generated code.

Explain important design decisions and any equations or numerical methods being introduced.

**Autonomous progress.**

Within the agreed milestone, implement, build, test, debug and document as much as possible without requiring approval for every routine engineering decision.

Do not expand into later research phases just because more work is possible.

---

### 14. Instructions for Codex / Work

Please begin by reviewing this brief and inspecting the available project files and development environment.

Then carry out **Phase 1 only**.

Use the primary scientific paper as the authoritative source for the model.

Where source details are unclear, explicitly state the uncertainty rather than inventing an implementation detail.

Create the project structure, implement the core model, add tests, run the experiments and produce an initial visualisation of conductivity changing over time.

Build and verify the software wherever the execution environment allows.

If access to my Mac's local filesystem or terminal is unavailable, do not claim that code has been built or tested locally. Prepare the project in an accessible workspace and clearly distinguish what has actually been verified.

At the end of the milestone, provide:

- A summary of what was implemented.
- Build and run instructions.
- Tests performed and their outcomes.
- Numerical validation results.
- Any differences from the published model.
- Known limitations.
- The next scientifically justified milestone.

**Our immediate goal is not a full UK transport optimiser, a complex GUI or a finished research paper.**

It is a small, correct, reproducible implementation of Physarum-inspired flow adaptation that we can understand, validate and build upon.

Start with Phase 1.