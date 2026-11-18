# Research project brief

## Objective

Investigate whether biologically inspired flow adaptation can form efficient and resilient transport networks under changing conditions. This is a provisional research question; useful contributions must be justified by a literature review and validated experiments.

The starting point is the adaptive tube model in Tero et al. (2010), *Rules for Biologically Inspired Adaptive Network Design*, [doi:10.1126/science.1177894](https://doi.org/10.1126/science.1177894). A future fungal-network comparison would require a distinct, published growth model rather than a relabelled Physarum model.

## Phase 1 — mathematical foundations

**Status: implemented and locally validated.**

The initial milestone is a small C++20 simulation that can be understood and checked independently. It contains a graph representation, a pressure solver, signed flows, simultaneous conductivity adaptation, a command-line experiment, CSV output, numerical tests and analysis figures.

The validation graph has four nodes and two competing source-sink routes of total lengths 2 and 4. Conductivities begin at 0.5. The baseline uses fixed terminals, current 2, gamma 1.8 and explicit Euler with time step 0.05. These choices define a mathematical test setup, not a complete reproduction of the published experiment.

Completion criteria are a successful CMake build, passing mathematical tests, flow conservation, correct conductivity updates, deterministic output, plottable results and documented assumptions. Evidence and limitations are in the [measured report](../results/phase1/REPORT.md) and [mathematical model](MATHEMATICAL_MODEL.md).

## Phase 2 — reproduce published behaviour

**Status: protocol development is the next milestone.**

Resolve the mesh, initial conductivities, source-sink selection, integration schedule and topology-reporting procedure from published sources or mark assumptions explicitly. Then investigate the reported qualitative behaviour and, where adequately specified, quantitative comparisons. Parameter similarity alone does not establish replication.

## Phase 3 — a focused research extension

**Status: deferred.**

Possible directions include nonstationary origin-destination demand, damage and recovery, scaling and stability, or comparison with a defensible fungal growth model. Choose one direction after baseline reproduction and a sufficiently broad related-work review. Existing multi-commodity and distributed Physarum literature must be accounted for before claiming novelty.

## User-directed exploratory tools

The native London connection workspace and the separate Jones-inspired particle growth laboratory support hands-on experimentation at the user’s request. Their protocols, model differences and limitations are recorded in `LONDON_EXPERIMENT.md` and `GROWTH_EXPERIMENT.md`. They do not change the status of the source-audited Tokyo reproduction or establish a research contribution. Both retain recorded inputs and computed results.

## Research principles

- Correctness before performance, with small independently verifiable components.
- Reproducible parameters, software versions, raw histories and numerical diagnostics.
- Explicit separation of published results, implementation assumptions, observations and interpretations.
- Clear distinction between conductivity dynamics and any visualization threshold.
- Fair baselines and uncertainty reporting when comparative experiments begin.
- No claims of biological completeness, originality or infrastructure feasibility without supporting evidence.

The simulation core remains independent of plotting and geographic data. The current stack is C++20, Eigen and CMake for simulation; Python, NumPy and Matplotlib for analysis; and Git for the research record.
