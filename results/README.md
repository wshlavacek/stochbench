# Results

Baseline results reported against this collection, one file per run. Each JSON file holds
one record per fit in the format `stochbench.protocol.score_fit` writes; the companion
Markdown table is `stochbench.protocol.format_table` over `stochbench.protocol.aggregate`.

The first baseline (PyBNF's `de`, `ss` and `cmaes` methods, each with and without their
noise handling, five fit seeds per problem) is produced by PyBNF's
`benchmarks/stochastic_recovery/run_baseline.py` and will be added here as
`pybnf_baseline_v1.json` once that run is complete.
