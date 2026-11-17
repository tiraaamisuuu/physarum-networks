# Research log

## 16 November 2026 - Phase 1 baseline

**Question.** Can we implement and independently validate the 2010 flow/adaptation equations on a small graph before studying network formation at scale?

**Scope.** Phase 1 only. Original brief preserved in `PROJECT_BRIEF.md`. Supplied PDFs are scientific evidence, not development instructions. No research originality, biological fidelity or full-paper replication claim is made.

**Published claims checked.** Tero et al. (2010) specify pressure-driven flow, conservation, sigmoid reinforcement and random terminal selection. I0=2 and gamma=1.8 are illustrated in Fig. 4. Bonifaci et al.'s convergence result studies a distinct linear reinforcement law. The 2022 and 2026 supplied papers already address multi-demand/distributed variants, so these general themes cannot be treated as new merely because we have not implemented them.

**Our validation assumptions.** Four nodes, two internally disjoint source-sink routes of length 2 and 4, all D0=0.5, fixed source 0 and sink 3, I0=2, gamma=1.8, Euler dt=0.05, duration 30. None of the graph, initial conductivity, fixed demand, time step or duration is presented as a published Tokyo setup. No randomness is used.

**Implementation.** Plain edge list, separate conductivity state, dense Eigen LDLT pressure solve with diagonal scaling and one pressure reference per positive-conductance component. Exact-zero inactive edges are retained. No conductivity floor, artificial leakage, graph pruning or threshold-based topology extraction. Numerical failure stops the run. The CLI exports aligned-time conductivities/flows/pressures and diagnostics, plus configs and software metadata.

**Hypothesis before interpretation.** With this symmetric initial state and different route lengths, reinforcement should favour the shorter route. If it becomes the sole carrying route, each of its edges should approach f(2)=0.776895386796. This is a fixture-specific expectation, not a general shortest-path theorem.

**Experiments and measured observations.**

- Release CMake configure/build completed locally. All 14 CTest cases passed. Debug with UndefinedBehaviorSanitizer also built and passed all 14 tests with no reported UB diagnostics.
- The baseline history has 601 states, four rows per state, from t=0 to t=30. Repeating the same setup produced byte-identical history, edge, config, metadata and summary files.
- Initial circuit solution is p=(16/3,8/3,8/3,0), Q=(4/3,4/3,2/3,2/3). Series and parallel analytic fixtures are also tested independently.
- Maximum baseline conservation residual: 1.77636e-15. Maximum grounded normwise backward error: 1.26884e-16.
- Reducing the two routes as resistors independently at every baseline state agrees with flows to 1.77636e-15 and pressures to 3.55271e-15. CSV conductivity transitions agree with Euler to 1.11022e-16.
- Final short-route conductivities: approximately 0.776895386795. Final long-route conductivities: approximately 1.33973041289e-13. Corresponding flows are approximately 2 and 1.72447e-13 per route. Small conductivities remain positive; no edge has been deleted.
- At t=4, error against a fine Euler reference dt=0.000625 is 0.00305520, 0.00150994, 0.000743450 and 0.000361719 for dt=0.1, 0.05, 0.025 and 0.0125. Successive ratios are approximately 2.023, 2.031 and 2.055. This supports first-order refinement on this fixture, with a finite-reference limitation.
- Halving dt=0.05 to 0.025 changes the baseline trajectory by a maximum of 0.000867554 at aligned times. Final equilibrium agreement alone would understate this transient sensitivity.
- Negative, nonfinite and malformed inputs, exact disconnection, demand-free components, a tiny single-edge D=1e-200 and an unresolved bottleneck are covered by unit checks. Three malformed CLI config types are rejected before output-directory creation.

**Interpretation.** The implementation passes the chosen mathematical checks and supports the expected route competition on this graph. These checks give a useful Phase 1 baseline, not evidence of general stability, optimality, resilience, transport practicality or novelty.

**Unexpected development behaviour.** Eigen 5.0.1 is installed. Its CMake compatibility file rejects a request pinned to major version 3, so package discovery uses the unversioned `Eigen3` CMake package name; the actual version is recorded in each run. This fixes discovery without replacing Eigen.

**Sanitizer limitation.** A combined AddressSanitizer/UndefinedBehaviorSanitizer build compiled, but its first test hung before `main`. A macOS `sample` trace placed the process in ASan shadow-memory/allocator initialization, recursively waiting on `StaticSpinMutex::LockSlow`. The hung test and CTest were terminated. This is evidence about the observed runtime stall, not a proven diagnosis of its root cause. ASan checks remain inconclusive. The separate UBSan Debug run completed successfully. No claim of completed ASan verification is made.

**Literature corrections.** The 2007 model DOI in the brief should be `10.1016/j.jtbi.2006.07.015`; the 2012 shortest-path paper DOI should end in `.017`, not `.019`. The corrected bibliography and verification sources are in `LITERATURE.md`.

**Reproduction.** Follow README build commands, then `analysis/run_validation.py`. Generated `results/phase1/validation.json` contains numerical checks, exact configs, source/binary hashes and analysis versions; `REPORT.md` summarises them. Tests use checks active in Release. The Git repository was initialized locally, with no commit or remote publication performed.

**Known limitations.** Small dense solver; fixed synthetic graph in CLI; double precision; explicit Euler only; acceptance tolerances are appropriate to the dimensionless fixture, not universal error bounds; no adaptive step control; no recovery after exact edge death; only local macOS ARM64 execution verified; ASan inconclusive; source-audited but incomplete literature review.

**Next scientifically justified milestone.** Define a Phase 2 reproduction protocol, resolving the 2010 mesh, initialization, random terminal sampling, integration schedule and topology reporting from sources or explicitly marked assumptions. Add stochastic multi-terminal experiments only once that protocol is recorded, and separate time discretisation from terminal-switching times in any refinement study. Do not begin dynamic-demand, disruption or fungal extensions until the baseline reproduction and related-work review justify a narrower research question.


## 17 November 2026 - repository presentation

Added an illustrated README, a code-native SVG header, measured network snapshots, conductivity/refinement plots, citation metadata and a two-platform CMake workflow. The figures read the recorded Phase 1 CSV and validation JSON; the simulation and recorded numerical results are unchanged. Geometry and the visual minimum-width convention are explicitly labelled.

Replaced the initial development brief with a concise public research brief, retaining the original local copy outside the tracked project. Replaced local absolute paths in the source inventory and recorded test logs with filenames or a project-root placeholder. Earlier versions remain in Git history; these presentation edits do not rewrite the research history.

The new CI configuration is intended to test Ubuntu and macOS; hosted outcomes must be read from the actual workflow run, not inferred from its presence.

The first hosted Ubuntu Release build completed successfully on 17 November 2026, including all 14 CTest cases. This verifies Linux compilation and the mathematical tests in addition to the initial local macOS checks. Run: https://github.com/tiraaamisuuu/physarum-networks/actions/runs/44124562834 .
