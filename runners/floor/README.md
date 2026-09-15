# The floor

A stochbench runner that is not a fitting tool: a general-purpose optimizer from SciPy or
from `cma`, driving the simulator directly, scoring the same chi-square the reference fits
score, under the same simulation budget.

It exists to answer one question about any tool that reports results against this collection.
**Does the tool beat a generic optimizer at equal cost?** If it does not, that is the finding,
and it is one the collection should be able to produce about itself.

Nothing here imports PyBNF. The simulator is [bngsim](https://pypi.org/project/bngsim/), the
same one PyBNF's baseline used, reached through its own Python API rather than through PyBNF's
model layer, so a difference between a floor result and a PyBNF result is a difference of
method and not of simulator.

## Methods

| name | what it is |
|---|---|
| `floor_de` | `scipy.optimize.differential_evolution` over the log10 parameter box, population 20, convergence stop off, no polish |
| `floor_cmaes` | CMA-ES from the `cma` package, same box, started at its centre with a step of a quarter of its width |

Neither knows its objective is noisy. That is the point: they are the null hypothesis a
noise-aware method has to beat.

## What is held identical to the reference fits

* **The objective.** `sum (sim - obs)^2 / (2 sigma^2)` over every observable and sampling time,
  with `obs` the committed replicate mean and `sigma` the committed `_SD` column. That is
  PyBNF's `chi_sq`: a Gaussian likelihood whose fixed normalizer is parameter-independent and
  dropped. Under smoothing the replicate trajectories are averaged and the average scored once,
  which is what PyBNF's job groups do.
* **The search space.** Every free parameter on a log10 scale between the frozen bounds.
* **The budget.** Every trajectory is one simulation, and the fit stops within one evaluation
  of `fit.budget_simulations`. SciPy's optimizers have no budget hook, so the objective raises
  `BudgetExhausted` through them and the runner catches it outside.
* **The confirmation.** The top ten distinct candidates are re-evaluated ten times each at the
  end and the best of those is reported, because a single noisy evaluation can look good by
  luck. Those simulations count against the fit, as PyBNF's confirmation does.
* **Failures.** A parameter set the simulator cannot run — one that blows a particle cap, or
  makes a trajectory unbounded — costs its replicates and scores as infinite. It is a bad
  candidate, not a crashed fit.

## What differs, and why that is allowed

**Seeds.** PyBNF derives a trajectory's seed from the parameter values and a replicate index,
which is why the committed data are drawn at replicate indices from a million up: otherwise a
fit that landed on the true parameters would redraw the data's own trajectories and score
itself against them. The floor has no such policy — it uses a counter that increases across the
whole fit, so no two evaluations share a trajectory and none can coincide with the data's. The
seed offset is respected for a different reason than PyBNF's, and the effect is the same.

**Network generation.** For a network-based problem the network is generated once, at the true
parameter values, and later parameter sets are written into the generated model: rate constants
do not change a network's topology. For a network-free problem BNG2.pl has to write the XML
NFsim reads, and that does depend on the parameter values, so it is redone per parameter set.

## Running it

```bash
python -m venv runners/floor/.venv
runners/floor/.venv/bin/pip install -r runners/floor/requirements.txt
export BNGPATH=/path/to/BioNetGen   # the folder holding BNG2.pl
```

Check the toolchain before spending a campaign on it. `check` evaluates the objective at the
true parameters; the number it prints is directly comparable with what PyBNF's harness reports
as the objective at the truth (`run_baseline.py leverage`), which is how the claim that the two
score the same chi-square is checked rather than asserted:

```bash
runners/floor/.venv/bin/python runners/floor/run_floor.py check
```

Then run and summarize. The results file is resumable: a (problem, method, seed) already in it
is skipped, so an interrupted campaign continues where it stopped.

```bash
runners/floor/.venv/bin/python runners/floor/run_floor.py run \
    --seeds 5 --parallel 10 --out results/floor_v1.json
runners/floor/.venv/bin/python runners/floor/run_floor.py summarize \
    results/floor_v1.json --out results/floor_v1.md
```

## Records

Every fit is scored by `stochbench.protocol.score_fit`, so a floor record is the same shape as
any other: the estimate, its per-parameter error in decades, the simulations spent, and a trace
of the reported best against simulations spent, from which simulations-to-success is read. The
trace keeps errors per parameter, so `protocol.rescore` can score the file again if a problem's
identifiability flags are ever revised.
