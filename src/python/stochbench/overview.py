"""Generate the README's two tables from the problem definitions and the results files.

The **overview** table says what each problem is. The **results** table says how far each
tool that has reported against the collection got on it: one row per problem, one column
per tool, holding that tool's best loose-tolerance success rate over the methods it ran.
A tool is named by the ``tool`` field every record carries.

Run ``python -m stochbench.overview`` to rewrite both tables between their START/END
markers in the README, or ``--print`` to print them.
"""
import json
import re
import sys
from pathlib import Path

from . import protocol

START = '<!-- START OVERVIEW TABLE -->'
END = '<!-- END OVERVIEW TABLE -->'
RESULTS_START = '<!-- START RESULTS TABLE -->'
RESULTS_END = '<!-- END RESULTS TABLE -->'


def _doi_links(reference):
    dois = re.findall(r'doi:(10\.\S+?)(?=[\s,;]|$)', reference)
    return ' '.join('[\\[%d\\]](https://doi.org/%s)' % (i + 1, d.rstrip('.')) for i, d in enumerate(dois))


def table(problems):
    head = ('| Problem ID | Free parameters | Method | Observables | Sampling times | Data replicates '
            '| Budget (simulations) | References |')
    sep = '|:---|---:|:---|---:|---:|---:|---:|:---|'
    rows = [head, sep]
    for p in problems:
        rows.append('| [%s](Benchmark-Models/%s/) | %d | %s | %d | %d | %d | %d | %s |' % (
            p.id, p.id, len(p.parameters), p.method, len(p.observables), p.n_steps + 1,
            p.data_replicates, p.budget_simulations, _doi_links(p.reference)))
    return '\n'.join(rows)


def load_results(root=None):
    """Every record in every ``results/*.json``, with the file it came from.

    Raises if a record does not say which tool produced it: a results table with an
    unattributed column would be worse than no table.
    """
    root = Path(root) if root is not None else protocol.problems_root().parent / 'results'
    records = []
    for path in sorted(root.glob('*.json')):
        for r in json.loads(path.read_text()):
            if not r.get('tool'):
                raise ValueError('%s: a record for %s has no "tool" field'
                                 % (path.name, r.get('problem')))
            records.append(r)
    return records


def results_table(problems, records):
    """One row per problem, one column per tool: the best loose-tolerance success rate
    that tool reached on that problem over the methods it ran, and the seeds behind it.

    The best over methods, not the mean, because a tool is fairly represented by its best
    available method -- a tool is not penalized for having also run a weaker one. The
    method that achieved it is in the results file.
    """
    tools = sorted({r['tool'] for r in records})
    best = {}
    for r in records:
        key = (r['problem'], r['tool'], r.get('method', '?'))
        n, k = best.get(key, (0, 0))
        best[key] = (n + 1, k + bool(r['success_loose']))
    rows = ['| Problem ID | ' + ' | '.join(tools) + ' |',
            '|:---|' + '---:|' * len(tools)]
    for p in problems:
        cells = []
        for tool in tools:
            scores = [(k / n, n) for (pid, t, _), (n, k) in best.items()
                      if pid == p.id and t == tool]
            if not scores:
                cells.append('&ndash;')
            else:
                rate, n = max(scores)
                cells.append('%.0f%% <sub>%d</sub>' % (100 * rate, n))
        rows.append('| [%s](Benchmark-Models/%s/) | ' % (p.id, p.id) + ' | '.join(cells) + ' |')
    return '\n'.join(rows)


def _replace(content, start, end, text, what):
    pattern = re.compile(re.escape(start) + '.*?' + re.escape(end), re.S)
    if not pattern.search(content):
        sys.exit('README has no %s markers' % what)
    return pattern.sub(lambda _: start + '\n' + text + '\n' + end, content)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    problems = protocol.load_problems()
    overview = table(problems)
    results = results_table(problems, load_results())
    if '--print' in argv:
        print(overview)
        print()
        print(results)
        return
    readme = protocol.problems_root().parent / 'README.md'
    content = readme.read_text()
    content = _replace(content, START, END, overview, 'overview-table')
    content = _replace(content, RESULTS_START, RESULTS_END, results, 'results-table')
    readme.write_text(content)
    print('wrote %d problem rows and %d result rows to %s'
          % (len(overview.splitlines()) - 2, len(results.splitlines()) - 2, readme))


if __name__ == '__main__':
    main()
