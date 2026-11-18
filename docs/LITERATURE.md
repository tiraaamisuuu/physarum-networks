# Literature record

Reviewed 16 November 2026 for Phase 1. This is an initial source audit, not a systematic review or evidence of novelty. All eight supplied PDFs were located and text-extracted. Reading depth differs: the 2010 model text was read and its equation page visually checked; the 2012 defining equations/theorem and 2026 defining equations were checked; other papers were screened for identity and relevant themes. No claims of a complete reading of all proofs or all fungal modelling details are made.

## Authoritative implementation source

**Tero, Takagi, Saigusa, Ito, Bebber, Fricker, Yumiki, Kobayashi & Nakagaki (2010). Rules for Biologically Inspired Adaptive Network Design. Science 327(5964), 439-442.** [DOI](https://doi.org/10.1126/science.1177894). Supplied as `slimemold.pdf`.

Eq. (1) gives Q=D(p_i-p_j)/L. The text on p. 441 specifies conductivity adaptation with f(q)=q^gamma/(1+q^gamma), and random source/sink food-source selection at each time step. Fig. 4 uses I0=2, gamma=1.8 and represents Tokyo with seven food sources. The study compares network cost, transport efficiency and fault tolerance. Phase 1 implements the flow and reinforcement equations on a deterministic validation graph. Its initial state and terminal procedure do not reproduce Fig. 4.

The author-hosted [article copy](https://markfricker.org/wp-content/uploads/2015/12/tero_et_al-2010-science-327-439.pdf) and [Oxford archive record](https://ora.ox.ac.uk/objects/uuid%3A01616eb5-3b21-4848-8b63-f909f34a83cc) were located. The source article is the authority, not unrelated material preceding it in some PDF versions.

The [supporting PDF mirrored at MIT](https://math.mit.edu/~dunkel/Teach/18.S995_2014F/paper_suggestions/science_tero_sm.pdf) was downloaded to the ignored `tmp/pdfs/` area and inspected. It contains a title page, S1 caption/figure and S2 caption/figure (five PDF pages). S1 varies I0 at gamma=1.8, S2 varies gamma at I0=0.2. It does not supply a full integration or mesh-generation protocol. Exact random initial-condition distribution, mesh construction, time-step meaning and any topology-extraction thresholds remain unresolved for future replication. No such details have been invented.

## Mathematical context

**Tero, Kobayashi & Nakagaki (2007). A mathematical model for adaptive transport network in path finding by true slime mold. Journal of Theoretical Biology 244(4), 553-564.** Correct [DOI](https://doi.org/10.1016/j.jtbi.2006.07.015). Supplied as `JTB244-4.pdf`, a repository manuscript with a bibliographic cover sheet. The brief's DOI `10.1016/j.jtbi.2007.06.015` is incorrect for this title. Verified against that cover sheet and the [Hokkaido repository PDF](https://eprints.lib.hokudai.ac.jp/repo/huscap/all/28041/JTB244-4.pdf).

Establishes the earlier feedback model and explores dependence on the reinforcement response. Useful mathematical background; it does not replace the 2010 sigmoid specification selected for implementation.

**Bonifaci, Mehlhorn & Varma (2012). Physarum can compute shortest paths. Journal of Theoretical Biology 309, 121-133.** Correct [DOI](https://doi.org/10.1016/j.jtbi.2012.06.017). Supplied as `physarum-jtb.pdf`, a 29-page author manuscript. The brief's DOI ending `.019` is incorrect for this paper; `.017` and the page range are verified on [Mehlhorn's institutional publication record](https://www.mpi-inf.mpg.de/people/mehlhorn/). A preliminary SODA version has a separate DOI and should not be confused with the journal paper.

The inspected model uses dD/dt=|Q|-D with unit injected current, positive initial conductivities and positive lengths. The theorem proves attraction to the set of shortest-path flows and convergence to the unique unit shortest-path flow when the shortest path is unique. This does **not** establish a convergence theorem for the 2010 saturating f, for Euler discretisation, or for resampled multi-terminal flow. The Phase 1 short-route result is an observation on one fixture.

**Bonifaci, Facca, Folz, Karrenbauer, Kolev, Mehlhorn, Morigi, Shahkarami & Vermande (2022). Physarum-inspired multi-commodity flow dynamics. Theoretical Computer Science 920, 1-20.** [DOI](https://doi.org/10.1016/j.tcs.2022.02.001). Supplied as `1-s2.0-S0304397522000822-main.pdf`; identity checked from its first page and [publisher record](https://www.sciencedirect.com/science/article/pii/S0304397522000822).

Develops dynamics for networks supporting multiple demands, with analytical and numerical optimisation results. Any future claim about multi-demand adaptive transport must account for this existing literature and the exact response law it studies. A detailed comparison of assumptions and convergence conditions remains future work; no blanket novelty claim is justified.

**Oishi, Jimbo, Kikuchi, Date, Kaji & Kashima (2026). Physarum-based approach to distributed optimal transport on graphs. Scientific Reports 16, 32314.** [DOI](https://doi.org/10.1038/s41598-026-61965-x). Supplied as `s41598-026-61965-x.pdf`; title, authors and article number verified in the PDF. Browser retrieval of the DOI page was unsuccessful, so the supplied publisher PDF is the source used here.

The introduction and Eqs. (1)-(7) distinguish local conductivity updates from the global Laplacian solve and formulate a distributed inner pressure solve with an outer adaptation step. Its Eq. (3) uses |Q|-D, not our sigmoid. It is directly relevant to future computational scaling and distributed implementations, but no algorithm from it is implemented in Phase 1. Its optimal-transport claims cannot be transferred to a different reinforcement law by analogy.

## Fungal context, screened only

**Fricker, Heaton, Jones & Boddy (2017). The Mycelium as a Network. Microbiology Spectrum 5(3), FUNK-0033-2017.** [DOI](https://doi.org/10.1128/microbiolspec.FUNK-0033-2017). Supplied as `microbiolspec.funk-0033-2017.pdf`.

Review of fungal architecture, transport and network growth. The abstract and initial sections discuss tip growth, branching, fusion, transport and recycling. Useful for selecting a biologically distinct future model. A graph abstraction alone does not specify which fungal growth law to implement; extracting a defensible model requires further reading.

**Bebber, Hynes, Darrah, Boddy & Fricker (2007). Biological solutions to transport network design. Proceedings of the Royal Society B 274, 2307-2315.** [DOI](https://doi.org/10.1098/rspb.2007.0459). Supplied as `rspb.2007.0459.pdf`.

Experimental analysis of the saprotrophic fungus Phanerochaete velutina, discussing transport capacity, robustness and network investment as networks develop. Provides a basis for later metric selection, with definitions and biological constraints needing careful checking. It is fungal evidence, not a numerical validation of our Physarum model.

**Oyarte Galvez and colleagues (2025). A travelling-wave strategy for plant-fungal trade. Nature 639.** [DOI](https://doi.org/10.1038/s41586-025-08614-x). Supplied as `s41586-025-08614-x.pdf`; bibliographic identity and abstract screened from its first page. Browser DOI retrieval encountered a publisher identity redirect.

Describes observed arbuscular mycorrhizal network development with tip-growth waves, fusion and transport. This is a different biological system from the saprotrophic networks above and from Physarum. The abstract motivates hypotheses for later study, not an implemented mechanism or an established research gap.

## Next reading tasks

1. Resolve the 2010 replication details via author code, additional methods or cited modelling papers. Record what is known and what remains unavailable.
2. Separate linear, power-law, sigmoid and multi-commodity adaptation models and their convergence assumptions.
3. Before choosing a dynamic-demand or disruption question, review work specifically on time-dependent demands, damage, budgets and recovery. The current eight-paper set does not establish originality.
4. For any fungal comparison, choose one organism class and a published, explicit growth/fusion/recycling model before coding.

`references.bib` stores the initial bibliography. The initial planning brief supplied two incorrect DOIs; their corrections are recorded above. `PROJECT_BRIEF.md` is the public research summary. `source_inventory.json` records supplied PDF filenames and hashes without machine-specific paths. Copyrighted source PDFs are not copied into the Git project.

## Outward-growth exploration added 17 November 2026

The user's request to watch a local inoculum expand concerns the laboratory sequence in Tero et al. Fig. 1, not the pre-existing-mesh initialization of its Fig. 4 numerical model. Those are kept distinct in the new growth mode and its [complete protocol](GROWTH_EXPERIMENT.md).

**Jones (2010), Characteristics of Pattern Formation and Evolution in Approximations of Physarum Transport Networks**, Artificial Life 16(2), 127–153, [doi:10.1162/artl.2010.16.2.16202](https://doi.org/10.1162/artl.2010.16.2.16202). The primary institutional manuscript was located at `https://uwe-repository.worktribe.com/preview/980585/artl.2010.16.2.pdf`; browser retrieval was blocked, while indexed method/table excerpts and the author manuscript mirrored elsewhere were available. Three-sensor chemotaxis, exclusive particle occupancy, movement deposition and 3×3 mean diffusion motivate the new engine. Exact reproduction is not claimed.

**Jones and Adamatzky (2012), Emergence of Self-Organized Amoeboid Movement in a Multi-Agent Approximation of Physarum polycephalum**, [author manuscript](https://arxiv.org/abs/1212.0023). The methods section and sensing/movement pseudocode were read from the primary arXiv PDF. It supports the broader family of particle models and environmental cues; this repository does not claim its oscillatory motor model or full organism behaviour. Our population, Gaussian cue and boundary choices are specified separately, and the new mode does not invoke the Tero Laplacian solver.
