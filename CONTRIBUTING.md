# Contributing a problem

New problems are welcome. Open a pull request with a new directory under
`Benchmark-Models/`; the checks in `tests/` run on every pull request and will tell you
whether the directory is self-consistent.

A problem is a directory holding:

* `problem.json`: the frozen definition (see [PROTOCOL.md](PROTOCOL.md) for the fields).
* `model.bngl`: the model, with every free parameter bound through the `name name__FREE`
  alias form and exactly one `simulate` action, without a seed.
* `<suffix>.exp`: the data, drawn at the true parameter values by the rules in
  [PROTOCOL.md](PROTOCOL.md): at each sampling time, the mean of every observable over the
  replicates and a `<observable>_SD` column with the standard deviation across them.

To add one:

1. Pick a published stochastic model with a citation. The curated
   [BNGL-Models](https://github.com/wshlavacek/BNGL-Models) collection is the pool the
   current problems came from; each of its models carries its citation and an
   independently verified simulation protocol.
2. Copy the model in, bind the free parameters, keep the observables that carry
   information, write one simulate action over a transient window from a fixed initial
   state, and record every adaptation from the published model in the header
   (`#@model_id`, `#@title`, `#@description`, `#@reference`, `#@source`).
3. Write `problem.json` by copying a neighbour's. True values must sit at least 0.3 decades
   inside the bounds on each side. Choose the simulation budget so that a fit is affordable
   (the current problems allow 20,000 simulations for SSA models and 4,000 for a network-free
   one).
4. Generate the data at the true values with the seed offset and sigma floor in the
   definition, and commit the `.exp` file. PyBNF's harness
   (`benchmarks/stochastic_recovery/run_baseline.py generate` in the PyBNF repository) does
   this from the definition.
5. Measure each parameter's leverage on the objective (PyBNF: `run_baseline.py leverage`)
   and add the rows to the table in `PROTOCOL.md`. A parameter the data do not see should be
   marked `"identifiable": false` and its reason given in `note`.
6. Run `pytest` and open the pull request.

Problem ids are permanent. A change to a problem's definition is a new version of the
collection, never a silent edit, so that a result reported against a version stays
comparable.
