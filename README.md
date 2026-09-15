# stochbench

A benchmark set of stochastic models for testing fitting algorithms and simulators. Each
problem is a published stochastic model written in the BioNetGen language (BNGL), a set of
chosen true parameter values, data simulated from them, search bounds, and a simulation
budget. A fitting method is scored on whether it recovers the true values from the data
within the budget; the right answer is known exactly, because it was chosen.

For fitting deterministic models there is the
[PEtab benchmark collection](https://github.com/Benchmarking-Initiative/Benchmark-Models-PEtab),
on which this collection is modelled. For stochastic, rule-based models there was nothing:
no agreed problems, no reference answers, and no scoring protocol. This is a start on one.

The protocol (what a problem is, how the data are made, how a fit is scored) is in
[PROTOCOL.md](PROTOCOL.md). Contributions are welcome; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Overview

<!-- START OVERVIEW TABLE -->
| Problem ID | Free parameters | Method | Observables | Sampling times | Data replicates | Budget (simulations) | References |
|:---|---:|:---|---:|---:|---:|---:|:---|
| [Cortes_BiophysJ2017](Benchmark-Models/Cortes_BiophysJ2017/) | 6 | nf | 5 | 121 | 200 | 20000 | [\[1\]](https://doi.org/10.1016/j.bpj.2017.09.012) |
| [Dembo_JImmunol1978](Benchmark-Models/Dembo_JImmunol1978/) | 3 | nf | 4 | 51 | 100 | 2000 | [\[1\]](https://doi.org/10.4049/jimmunol.121.1.345) |
| [Faeder_JImmunol2003](Benchmark-Models/Faeder_JImmunol2003/) | 6 | ssa | 6 | 61 | 200 | 4000 | [\[1\]](https://doi.org/10.4049/jimmunol.170.7.3769) |
| [Hlavacek_PNAS2001](Benchmark-Models/Hlavacek_PNAS2001/) | 4 | ssa | 3 | 61 | 200 | 20000 | [\[1\]](https://doi.org/10.1073/pnas.121172298) [\[2\]](https://doi.org/10.1006/bulm.2002.0306) |
| [Lin_PhysRevE2016](Benchmark-Models/Lin_PhysRevE2016/) | 4 | ssa | 2 | 73 | 200 | 20000 | [\[1\]](https://doi.org/10.1103/PhysRevE.93.022409) |
| [McKane_PhysRevLett2005](Benchmark-Models/McKane_PhysRevLett2005/) | 4 | ssa | 2 | 81 | 200 | 20000 | [\[1\]](https://doi.org/10.1103/PhysRevLett.94.218102) |
| [Munsky_Science2012](Benchmark-Models/Munsky_Science2012/) | 6 | ssa | 6 | 301 | 200 | 20000 | [\[1\]](https://doi.org/10.1126/science.1216379) |
| [Rubenstein_BiophysChem2007](Benchmark-Models/Rubenstein_BiophysChem2007/) | 5 | ssa | 3 | 101 | 200 | 2000 | [\[1\]](https://doi.org/10.1016/j.bpc.2006.09.011) |
| [Samoilov_PNAS2005](Benchmark-Models/Samoilov_PNAS2005/) | 8 | ssa | 6 | 251 | 200 | 20000 | [\[1\]](https://doi.org/10.1073/pnas.0406841102) |
| [Shahrezaei_PNAS2008](Benchmark-Models/Shahrezaei_PNAS2008/) | 4 | ssa | 3 | 61 | 200 | 20000 | [\[1\]](https://doi.org/10.1073/pnas.0803850105) |
| [Vilar_PNAS2002](Benchmark-Models/Vilar_PNAS2002/) | 4 | ssa | 3 | 101 | 200 | 20000 | [\[1\]](https://doi.org/10.1073/pnas.092133899) |
| [Yang_PhysRevE2008](Benchmark-Models/Yang_PhysRevE2008/) | 3 | nf | 3 | 61 | 100 | 4000 | [\[1\]](https://doi.org/10.1103/PhysRevE.78.031910) |
<!-- END OVERVIEW TABLE -->

## Reference results

How far each tool that has reported against the collection got on each problem: its best
success rate at the loose tolerance (every identifiable parameter within a factor of two of
the truth) over the methods it ran, with the number of fits behind it in small type. The
methods themselves, and the median errors and costs, are in [results/](results/).

<!-- START RESULTS TABLE -->
| Problem ID | PyBNF |
|:---|---:|
| [Cortes_BiophysJ2017](Benchmark-Models/Cortes_BiophysJ2017/) | &ndash; |
| [Dembo_JImmunol1978](Benchmark-Models/Dembo_JImmunol1978/) | &ndash; |
| [Faeder_JImmunol2003](Benchmark-Models/Faeder_JImmunol2003/) | &ndash; |
| [Hlavacek_PNAS2001](Benchmark-Models/Hlavacek_PNAS2001/) | 80% <sub>5</sub> |
| [Lin_PhysRevE2016](Benchmark-Models/Lin_PhysRevE2016/) | 5% <sub>20</sub> |
| [McKane_PhysRevLett2005](Benchmark-Models/McKane_PhysRevLett2005/) | 40% <sub>5</sub> |
| [Munsky_Science2012](Benchmark-Models/Munsky_Science2012/) | 10% <sub>20</sub> |
| [Rubenstein_BiophysChem2007](Benchmark-Models/Rubenstein_BiophysChem2007/) | &ndash; |
| [Samoilov_PNAS2005](Benchmark-Models/Samoilov_PNAS2005/) | &ndash; |
| [Shahrezaei_PNAS2008](Benchmark-Models/Shahrezaei_PNAS2008/) | 80% <sub>20</sub> |
| [Vilar_PNAS2002](Benchmark-Models/Vilar_PNAS2002/) | &ndash; |
| [Yang_PhysRevE2008](Benchmark-Models/Yang_PhysRevE2008/) | 40% <sub>5</sub> |
<!-- END RESULTS TABLE -->

`PyBNF` is the tool the collection was built alongside; `floor` is a general-purpose optimizer
driving the simulator directly at the same budget, which exists so that a tool can be asked
whether it beats one (`runners/floor/`).

Both tables are generated from the problem definitions and the results files by
`python -m stochbench.overview`.

Every model comes from the curated
[BNGL-Models](https://github.com/wshlavacek/BNGL-Models) collection, where each carries its
citation and an independently verified simulation protocol. The adaptations made here (which
parameters are free, which observables are kept, the sampling window) are written in each
model's header and its `problem.json`.

## Layout

```
Benchmark-Models/<id>/   one directory per problem: model.bngl, problem.json, <suffix>.exp
PROTOCOL.md              the definition format, the data rules, the scoring rules
results/                 reference results reported against the collection
runners/floor/           the floor: a general-purpose optimizer at the same budget
src/python/stochbench/   the protocol as code (pure Python) and the overview generator
tests/                   checks that every problem directory is self-consistent
```

## Using it

Clone the repository, or download it as a
[ZIP file](https://github.com/wshlavacek/stochbench/archive/refs/heads/main.zip). The
`stochbench` Python package reads the definitions and scores results:

```bash
pip install -e src/python
```

```python
from stochbench import protocol
for problem in protocol.load_problems():
    print(problem.id, problem.method, len(problem.parameters), problem.budget_simulations)
```

A fitting tool brings its own runner, living with the tool or under `runners/` here. PyBNF's
is `benchmarks/stochastic_recovery/` in the [PyBNF repository](https://github.com/lanl/PyBNF);
it generates the data from a definition, runs its methods against a problem while counting
simulations, and produced the first baseline in `results/`.

[`runners/floor/`](runners/floor/) is the floor: `scipy.optimize.differential_evolution` and
CMA-ES driving the simulator directly, on the same chi-square, at the same budget. It is not a
fitting tool and is not meant to be a good one. It is there so that a tool reporting against
this collection can be asked whether it beats a generic optimizer at equal cost — and so that
the collection can be scored by something other than the tool it was built alongside.

## Status

Version 0.2.0: twelve problems, chosen for a range of size (three to eight free parameters,
seven species to 354), noise (single-molecule promoters to thirty thousand ligands), dynamics
(transients, noise-driven switching, noise-driven and noise-resistant cycles, exponential
aggregate growth), rate laws (mass action, and functional rate laws evaluated per event),
simulator (nine SSA, three network-free) and cost (budgets from 2,000 to 20,000 simulations).
Three free parameters are marked not identifiable, measured rather than assumed, so a method
is also tested on whether it wastes budget on a direction carrying no information. The plan is
twenty to thirty problems and reference results from several tools.

What a version means is in [PROTOCOL.md](PROTOCOL.md#versioning): problem ids are permanent,
a problem never changes in place, adding problems is a minor version, and changing a scoring
rule is a major one. Every fit record names the collection version it was scored against.
[docs/RELEASING.md](docs/RELEASING.md) is the release checklist.

## License

Code and documentation are under the [BSD 3-Clause License](LICENSE). The models and data
under `Benchmark-Models/` are adapted from BNGL-Models and are available under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); each model's header names the
publication it implements, to which different terms may apply.

## How to cite

A publication describing the collection is in preparation. Until then, cite the released
version you used (see [CITATION.cff](CITATION.cff)), and say which one: a result is only
comparable with another scored against the same version.

Releases are archived on Zenodo, which issues a DOI for each one and a concept DOI resolving
to the newest. Both go here and in `CITATION.cff` once the first release is deposited; see
[docs/RELEASING.md](docs/RELEASING.md).
