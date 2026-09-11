# Results

Reference results reported against this collection, one JSON file per run holding one
record per fit in the format `stochbench.protocol.score_fit` writes, with a companion
Markdown table from `stochbench.protocol.format_table` over `stochbench.protocol.aggregate`.

| file | tool | methods | seeds | date |
|---|---|---|---:|---|
| `pybnf_baseline_v1.json` | PyBNF (bngsim 0.15.1, BioNetGen 2.9.3) | `de`; `ss` and `cmaes` each with and without noise handling | 5 per problem | 2026-09-11 |
| `pybnf_ss_noise_20seeds.json` | PyBNF (bngsim 0.15.1, BioNetGen 2.9.3) | `ss`; `ss_noise` at its default deferral of 5 draws and as the variants `ss_noise_d2` and `ss_noise_d3` (`ss_noise_max_draws` 2 and 3), on Shahrezaei_PNAS2008, Lin_PhysRevE2016, Munsky_Science2012 and McKane_PhysRevLett2005 | 20 per problem and method (seeds 1 to 20; 1 to 5 shared with the baseline) | 2026-09-11 |

Every fit in `pybnf_baseline_v1` spent the problem's frozen simulation budget plus PyBNF's
end-of-fit confirmation of the best fit (ten candidates run ten more times each) and the
replicates it runs for its information criteria, all counted in `simulations`. The run is
reproducible: a second run from the same seeds reproduced every estimate, every trace and
every simulation count, with the reported objective values agreeing to floating-point
rounding. The runner is `benchmarks/stochastic_recovery/run_baseline.py` in the PyBNF
repository, which also discusses what the baseline shows.

`pybnf_ss_noise_20seeds` settles a question the baseline left open. Seed-paired over twenty
seeds, scatter search's noise handling changes the success rate on none of the four problems
(4 of 20 against 4 of 20 on McKane_PhysRevLett2005, 11 against 13 on Shahrezaei_PNAS2008, 1
against 1 and 1 against 0 on the other two) and leaves the final error worse in 48 of 80
paired seeds (sign test p = 0.09). The PyBNF benchmark README carries the analysis and the
mechanism: with noise handling on, the search accepts about half as many replacements into
its reference set per run and spends a tenth of its budget re-drawing points it has seen.
The same file holds the variants that shorten the deferral: at 2 draws the noise handling is
indistinguishable from plain scatter search and beats its own default in 50 of 79 decided
seeds (p = 0.024); at 3 it has the most successes of the four, 24 of 80 against 17 for plain
scatter search. The default of 5 is the worst of the three settings on final error.
