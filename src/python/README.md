# stochbench (Python)

The problem-definition format and the scoring protocol of the collection, as code.
`stochbench.protocol` imports nothing beyond the standard library; `stochbench.overview`
generates the README's overview table.

```bash
pip install -e .
python -m stochbench.overview   # rewrite the table in the repository README
```

The problems are read from the `Benchmark-Models/` directory of the repository this file
sits in; set `STOCHBENCH_ROOT` to point at another checkout.
