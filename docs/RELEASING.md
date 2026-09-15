# Cutting a version

What a version means is in [PROTOCOL.md](../PROTOCOL.md#versioning): problem ids are permanent,
problems never change in place, adding problems is a minor version, and changing a scoring rule
is a major one. This is the checklist for releasing one.

## One-time: connect Zenodo

Zenodo mints the DOIs, and it only sees releases made after the repository is switched on there.

1. Sign in at [zenodo.org](https://zenodo.org) with the GitHub account that owns the repository.
2. Under **GitHub** in the account menu, switch `wshlavacek/stochbench` on.
3. Cut the first release (below). Zenodo deposits it and issues two DOIs: a **version DOI** for
   that release and a **concept DOI** that always resolves to the newest one.
4. Put both in `CITATION.cff` (`doi:` for the concept DOI, `identifiers:` for the version DOI)
   and in the README's "How to cite". They are minted on first release, so this step lands in
   the commit *after* `v0.1.0`, and the tag is not moved to include it.

`.zenodo.json` at the repository root supplies the deposit's metadata (title, authors, licence,
keywords), so the Zenodo record does not have to be edited by hand.

## Every release

1. Decide the number by the rule in `PROTOCOL.md`. Adding problems: minor. Changing a scoring
   rule, a tolerance, the cost accounting, or superseding a problem: major.
2. Set it in all three places, which a test holds equal:
   * `src/python/stochbench/protocol.py` — `COLLECTION_VERSION`
   * `src/python/pyproject.toml` — `version`
   * `CITATION.cff` — `version` and `date-released`
3. `python -m stochbench.overview` and commit the README if it moved.
4. `python -m pytest tests -q`.
5. Merge, then tag the merge commit and push the tag:

   ```
   git tag -a v<version> -m "stochbench v<version>"
   git push origin v<version>
   ```

6. Publish the GitHub release from the tag. Zenodo deposits it within a few minutes.
7. If this is the first release, or the concept DOI is not yet recorded, add the two DOIs to
   `CITATION.cff` and the README.

## What a release promises

Everything under `Benchmark-Models/` at that tag, scored by `PROTOCOL.md` and `protocol.py` at
that tag. A results file reported against the release names it in each record's
`collection_version`. That is the whole contract: a reader who has the tag can re-score any
record in the file without running a simulation.
