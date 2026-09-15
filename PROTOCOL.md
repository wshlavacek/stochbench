# The stochbench protocol

A stochbench problem is a stochastic model, a set of chosen "true" parameter values, data
simulated from them, and a simulation budget. A fitting method is scored on whether it gets
the true values back from the data within that budget. The right answer is known exactly,
because it was chosen; nothing is scored against "the best anyone has found so far".

## A problem

A directory under `Benchmark-Models/` holding `problem.json`, the model it names, and the
data file it names. Everything a fit needs to be repeatable years from now is in the JSON or
committed next to it.

`problem.json` (format version 1):

| field | meaning |
|---|---|
| `id` | the directory name; permanent |
| `version` | the definition format version (1) |
| `title`, `reference`, `source` | what the model is, the publication it implements (with DOI), and where the BNGL came from |
| `model` | the model file, relative to the directory |
| `simulation.method` | `ssa` (network-based Gillespie) or `nf` (network-free) |
| `simulation.suffix` | the simulate action's suffix; the data file is `<suffix>.exp` |
| `simulation.t_start`, `t_end`, `n_steps` | the sampling grid: `n_steps + 1` evenly spaced times |
| `observables` | the observables the data record, in the model's own names |
| `parameters` | for each free parameter (named by its `__FREE` alias): `true`, `low`, `high` (search bounds), `identifiable`, `note` |
| `data.file` | the data file |
| `data.replicates` | how many trajectories the data average |
| `data.seed_offset` | the first replicate index the data were drawn at |
| `data.sd_floor_fraction` | the sigma floor, as a fraction of each observable's peak mean |
| `fit.budget_simulations` | the simulations one fit may spend |
| `fit.smoothing` | replicates per evaluation the reference fits use |
| `notes` | free text: the adaptations from the published model and what makes the problem hard |

Every free parameter is searched on a log scale between its bounds. The true value sits at
least 0.3 decades inside each bound.

## The data

The data file holds, at each sampling time, the mean of every observable over
`data.replicates` trajectories at the true values, and a `<observable>_SD` column with the
standard deviation across those trajectories, floored at `data.sd_floor_fraction` of the
observable's peak mean so a point every trajectory agrees on (the initial condition, a
species that stays at zero) does not get infinite weight. The `_SD` column is the per-point
sigma a chi-square objective reads.

The trajectories are drawn at replicate indices starting at `data.seed_offset` (one million
in the current problems). This matters for a fitting tool whose stochastic seeds derive from
the parameter values and a replicate index, as PyBNF's do by default: a fit that evaluates
the true parameters would otherwise draw replicates 0, 1, 2, ... of exactly the process the
data came from and reproduce the data's own trajectories instead of drawing fresh ones.

The data file is committed. It is regenerable from the definition and the simulator, but the
committed file is the benchmark: should a simulator's random stream change, the problem does
not.

## Scoring a fit

* **Error.** For each free parameter, `|log10(estimate / true)|` in decades. A fit's error is
  the largest over the parameters the definition marks identifiable; a parameter marked not
  identifiable is reported but never scored.
* **Success.** A fit succeeds at the loose tolerance when every identifiable parameter is
  within a factor of two of its true value (0.301 decades), and at the tight tolerance when
  every one is within 26 percent (0.1 decades). The loose tolerance is the headline: the data
  are replicate means of a stochastic process and the fit's own objective is a noisy
  estimate, so a factor of two is what "found it" means here.
* **Cost.** The currency is simulations, not evaluations, because a method that runs more
  replicates per parameter set is spending more. Every simulation the fit runs counts: the
  search, any end-of-fit re-evaluation that decides the answer, and any replicates run for
  reporting. Simulations-to-success is the number spent when the fit's reported best
  parameter set first came within the loose tolerance, and is reported only for fits whose
  final answer is within it.
* **Repetition.** Both the method and the simulator are random, so every (problem, method)
  pair is run from several fit seeds, and the success rate over those seeds is the primary
  statistic, next to the median error and the median simulations-to-success.
* **Equal budgets.** Every method gets the problem's `fit.budget_simulations`, enforced by
  the runner: a fit stops within one evaluation of the budget whatever its own stopping rule
  would say.

`src/python/stochbench/protocol.py` implements this: `load_problems`, `log10_errors`,
`max_error`, `score_fit`, `aggregate`, `format_table`, and `rescore` (to score a results file
again under revised identifiability flags without running anything). It imports nothing
beyond the standard library.

## Versioning

A number reported against this collection today has to mean the same thing as a number
reported against it in two years, so the collection is versioned and every result says which
version it was scored against.

* **Problem ids are permanent.** An id names one problem forever. It is never reused for a
  different problem and never renamed.
* **A problem never changes in place.** Its definition, its model and its data are frozen once
  published. Anything that would change what a fit of it is scored on — a true value, a bound,
  the sampling window, the observables, the budget, the data file — is a *new problem with a
  new id*, not an edit. (Text that changes nothing a fit sees, a typo in `notes` or a clearer
  `description`, is an ordinary edit.)
* **Adding problems is a minor version.** The existing problems are untouched, so a result
  reported against 0.1.0 still stands under 0.2.0; it just covers fewer problems than a result
  reported against 0.2.0 does.
* **Changing the scoring rules is a major version.** The rules above — the tolerances, what
  counts as a simulation, which statistic is primary — are part of what a version pins, in this
  file and in `protocol.py` together. A changed tolerance or cost rule is a major version even
  though no problem directory moved, because it rescores every existing result.
* **Removing or superseding a problem is a major version.** A problem found to be broken is
  marked superseded in its `notes` and kept; it is not deleted, because results that cite it
  exist.

Two version numbers live alongside each other and mean different things. The **collection
version** (`protocol.COLLECTION_VERSION`, the `version` in `CITATION.cff` and
`src/python/pyproject.toml`, and the release tag, all equal) is the one above. The **definition
format version** (the `version` field in each `problem.json`, `protocol.FORMAT_VERSION`, 1
today) is the schema those files are written in; a field added to the schema bumps it, and
`load_problem` refuses a file it does not recognize rather than guessing.

Every fit record `protocol.score_fit` writes carries a `collection_version`. A runner that
scored a checkout other than the one it imports passes the version it actually scored. A
results file whose records do not agree on that field is reporting on two different
collections and should be split.

`docs/RELEASING.md` is the checklist for cutting a version and minting its DOI.

## What the data determine

Whether the data determine a parameter is measured, not guessed: score the truth several
times to get the objective's noise there, then each parameter alone at half and double its
true value, and report the shift in units of that noise. Every parameter of the current
problems moves the objective by more than its noise in at least one direction, most by
hundreds of standard deviations, so all are marked identifiable. The measurement (six
evaluations at the truth, `fit.smoothing` replicates each, chi-square against the committed
`_SD` columns):

| problem | parameter | halved | doubled |
|---|---|---:|---:|
| Shahrezaei_PNAS2008 | `k0` | 2 | 0 |
| Shahrezaei_PNAS2008 | `k1` | 2 | 1 |
| Shahrezaei_PNAS2008 | `v0` | 1 | 16 |
| Shahrezaei_PNAS2008 | `v1` | 1 | 10 |
| Lin_PhysRevE2016 | `B` | 8 | 97 |
| Lin_PhysRevE2016 | `r0` | 1 | 31 |
| Lin_PhysRevE2016 | `r1` | 0 | 17 |
| Lin_PhysRevE2016 | `K` | 13 | 4 |
| McKane_PhysRevLett2005 | `b` | 501 | 860 |
| McKane_PhysRevLett2005 | `d1` | 471 | 1586 |
| McKane_PhysRevLett2005 | `p1` | 1429 | 649 |
| McKane_PhysRevLett2005 | `p2` | 10 | 31 |
| Hlavacek_PNAS2001 | `kon1` | 937 | 1466 |
| Hlavacek_PNAS2001 | `kon2` | 980 | 1425 |
| Hlavacek_PNAS2001 | `koff` | 10806 | 2795 |
| Hlavacek_PNAS2001 | `kp` | 270 | 1015 |
| Munsky_Science2012 | `k_on_I` | 5 | 7 |
| Munsky_Science2012 | `k_off_I` | 7 | 1 |
| Munsky_Science2012 | `k_on_II` | 4 | 6 |
| Munsky_Science2012 | `k_off_II` | 3 | 1 |
| Munsky_Science2012 | `k_on_III` | 5 | 12 |
| Munsky_Science2012 | `k_off_III` | 13 | 6 |
| Yang_PhysRevE2008 | `koff` | 1017 | 1142 |
| Yang_PhysRevE2008 | `kon1` | 919 | 815 |
| Yang_PhysRevE2008 | `kon2` | 20 | 49 |

Parameters whose leverage is ten to fifty where their siblings' is a thousand (`p2` in
McKane_PhysRevLett2005, `kon2` in Yang_PhysRevE2008) are narrow directions of a steep
landscape; parameters whose leverage is low in one direction (the slow promoter and
transcription rates of Shahrezaei_PNAS2008, Lin_PhysRevE2016 and Munsky_Science2012) change
a replicate mean by less than the noise in ten replicates when halved. Both are what a
method has to cope with, and the first baseline shows they are where methods fail.

## Reference fits

The first baseline was produced with PyBNF (`benchmarks/stochastic_recovery/` in the PyBNF
repository, which also documents the runner): differential evolution, scatter search with and
without its noise handling, and CMA-ES with and without its uncertainty handling, each pair
differing only in the one toggle, all at the same simulation budget, with `fit.smoothing`
replicates per evaluation, a chi-square objective against the committed `_SD` columns, and
five fit seeds per problem. Results live in `results/`.
