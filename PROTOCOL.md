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
| s01 | `k0` | 2 | 0 |
| s01 | `k1` | 2 | 1 |
| s01 | `v0` | 1 | 16 |
| s01 | `v1` | 1 | 10 |
| s02 | `B` | 8 | 97 |
| s02 | `r0` | 1 | 31 |
| s02 | `r1` | 0 | 17 |
| s02 | `K` | 13 | 4 |
| s03 | `b` | 501 | 860 |
| s03 | `d1` | 471 | 1586 |
| s03 | `p1` | 1429 | 649 |
| s03 | `p2` | 10 | 31 |
| s04 | `kon1` | 937 | 1466 |
| s04 | `kon2` | 980 | 1425 |
| s04 | `koff` | 10806 | 2795 |
| s04 | `kp` | 270 | 1015 |
| s05 | `k_on_I` | 5 | 7 |
| s05 | `k_off_I` | 7 | 1 |
| s05 | `k_on_II` | 4 | 6 |
| s05 | `k_off_II` | 3 | 1 |
| s05 | `k_on_III` | 5 | 12 |
| s05 | `k_off_III` | 13 | 6 |
| s06 | `koff` | 1017 | 1142 |
| s06 | `kon1` | 919 | 815 |
| s06 | `kon2` | 20 | 49 |

Parameters whose leverage is ten to fifty where their siblings' is a thousand (`p2` in s03,
`kon2` in s06) are narrow directions of a steep landscape; parameters whose leverage is low
in one direction (the slow promoter and transcription rates of s01, s02, s05) change a
replicate mean by less than the noise in ten replicates when halved. Both are what a method
has to cope with, and the first baseline shows they are where methods fail.

## Reference fits

The first baseline was produced with PyBNF (`benchmarks/stochastic_recovery/` in the PyBNF
repository, which also documents the runner): differential evolution, scatter search with and
without its noise handling, and CMA-ES with and without its uncertainty handling, each pair
differing only in the one toggle, all at the same simulation budget, with `fit.smoothing`
replicates per evaluation, a chi-square objective against the committed `_SD` columns, and
five fit seeds per problem. Results live in `results/`.
