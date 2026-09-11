"""Generate the overview table of the repository README from the problem definitions.

Run ``python -m stochbench.overview`` to rewrite the table between the START/END markers
in the README, or ``--print`` to print it.
"""
import re
import sys
from pathlib import Path

from . import protocol

START = '<!-- START OVERVIEW TABLE -->'
END = '<!-- END OVERVIEW TABLE -->'


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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = table(protocol.load_problems())
    if '--print' in argv:
        print(text)
        return
    readme = protocol.problems_root().parent / 'README.md'
    content = readme.read_text()
    pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.S)
    if not pattern.search(content):
        sys.exit('README has no overview-table markers')
    readme.write_text(pattern.sub(START + '\n' + text + '\n' + END, content))
    print('wrote %d rows to %s' % (len(text.splitlines()) - 2, readme))


if __name__ == '__main__':
    main()
