# Results

Reference results reported against this collection, one JSON file per run holding one
record per fit in the format `stochbench.protocol.score_fit` writes, with a companion
Markdown table from `stochbench.protocol.format_table` over `stochbench.protocol.aggregate`.

| file | tool | methods | seeds | date |
|---|---|---|---:|---|
| `pybnf_baseline_v1.json` | PyBNF (bngsim 0.15.1, BioNetGen 2.9.3) | `de`; `ss` and `cmaes` each with and without noise handling | 5 per problem | 2026-09-11 |

Every fit in `pybnf_baseline_v1` spent the problem's frozen simulation budget plus PyBNF's
end-of-fit confirmation of the best fit (ten candidates run ten more times each) and the
replicates it runs for its information criteria, all counted in `simulations`. The run is
reproducible: a second run from the same seeds reproduced every estimate, every trace and
every simulation count, with the reported objective values agreeing to floating-point
rounding. The runner is `benchmarks/stochastic_recovery/run_baseline.py` in the PyBNF
repository, which also discusses what the baseline shows.
