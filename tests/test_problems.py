"""Every problem directory is self-consistent: the definition names a model that declares
each free parameter's alias and one simulate action matching the frozen settings, the true
values sit inside the bounds and away from their edges, and the committed data file has
exactly the columns and sampling times the definition promises. Plus the scoring functions
on hand-made records. No simulator is needed."""
import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from stochbench import protocol

PROBLEMS = protocol.load_problems()

ROOT = protocol.problems_root().parent

#: Problem ids are permanent (PROTOCOL.md, "Versioning"): an id names one problem forever,
#: is never reused and never renamed. Every id ever published is listed here, so a rename
#: or a deletion fails the test suite rather than silently invalidating published results.
PERMANENT_IDS = {
    'Hlavacek_PNAS2001',
    'Lin_PhysRevE2016',
    'McKane_PhysRevLett2005',
    'Munsky_Science2012',
    'Shahrezaei_PNAS2008',
    'Yang_PhysRevE2008',
}


def test_collection_is_not_empty_and_ids_are_directory_names():
    assert PROBLEMS
    assert [p.id for p in PROBLEMS] == sorted(p.id for p in PROBLEMS)
    for p in PROBLEMS:
        assert p.directory.name == p.id


def test_published_problem_ids_are_still_present():
    missing = PERMANENT_IDS - {p.id for p in PROBLEMS}
    assert not missing, ('problem ids are permanent; %s was renamed or removed. Adding an id '
                         'to PERMANENT_IDS is part of publishing it; taking one out is not.'
                         % sorted(missing))


def test_the_three_version_strings_agree():
    """The collection version lives in three places a reader may look at. They must agree,
    because a results file names one of them and a citation names another."""
    pyproject = (ROOT / 'src/python/pyproject.toml').read_text()
    citation = (ROOT / 'CITATION.cff').read_text()
    assert re.search(r'^version = "%s"$' % re.escape(protocol.COLLECTION_VERSION),
                     pyproject, re.M), 'pyproject.toml disagrees with protocol.COLLECTION_VERSION'
    assert re.search(r'^version: %s$' % re.escape(protocol.COLLECTION_VERSION),
                     citation, re.M), 'CITATION.cff disagrees with protocol.COLLECTION_VERSION'


def test_every_published_result_names_the_collection_it_was_scored_against():
    for path in sorted((ROOT / 'results').glob('*.json')):
        records = json.loads(path.read_text())
        versions = {r.get('collection_version') for r in records}
        assert None not in versions, '%s has records without a collection_version' % path.name
        assert len(versions) == 1, ('%s mixes collections %s; a results file reports on one'
                                    % (path.name, sorted(versions)))


@pytest.mark.parametrize('problem', PROBLEMS, ids=lambda p: p.id)
def test_problem_definition_is_self_consistent(problem):
    assert problem.version == protocol.FORMAT_VERSION
    assert problem.reference and 'doi:' in problem.reference
    assert problem.identifiable, 'a problem with nothing identifiable cannot be scored'
    assert problem.budget_simulations > 0 and problem.smoothing >= 1
    assert problem.data_replicates >= 10
    assert problem.data_seed_offset >= 10 ** 5, 'data replicates must not collide with a fit\'s'

    model = problem.model_path.read_text()
    assert '#@reference:' in model and '#@source:' in model
    assert re.search(r'#@model_id:\s*%s\b' % re.escape(problem.id), model)
    for p in problem.parameters:
        assert p.name.endswith('__FREE')
        assert re.search(r'^\s*%s\s+%s\b' % (re.escape(p.name[:-6]), re.escape(p.name)), model, re.M), \
            '%s must be declared as the alias of %s' % (p.name, p.name[:-6])
        assert p.low < p.true < p.high
        assert math.log10(p.true / p.low) >= 0.3 and math.log10(p.high / p.true) >= 0.3, \
            '%s: the true value should sit at least 0.3 decades from each bound' % p.name
    actions = re.findall(r'^\s*simulate\(\{(.*)\}\)', model, re.M)
    assert len(actions) == 1, 'exactly one simulate action'
    settings = dict(re.findall(r'(\w+)=>"?([\w.]+)"?', actions[0]))
    assert settings['method'] == problem.method
    assert settings['suffix'] == problem.suffix
    assert float(settings['t_start']) == problem.t_start
    assert float(settings['t_end']) == problem.t_end
    assert int(settings['n_steps']) == problem.n_steps
    assert 'seed' not in settings, 'seeds come from the fitting tool\'s policy, never from the action'
    for obs in problem.observables:
        assert re.search(r'^\s*(Molecules|Species)\s+%s\s' % re.escape(obs), model, re.M), obs


@pytest.mark.parametrize('problem', PROBLEMS, ids=lambda p: p.id)
def test_committed_data_matches_definition(problem):
    lines = [ln for ln in problem.data_path.read_text().splitlines() if ln.strip()]
    header = lines[0].lstrip('#').split()
    expected = ['time'] + list(problem.observables) + [o + '_SD' for o in problem.observables]
    assert header == expected
    arr = np.array([[float(x) for x in ln.split()] for ln in lines[1:]])
    assert arr.shape == (problem.n_steps + 1, len(expected))
    assert np.allclose(arr[:, 0], problem.sample_times)
    assert np.isfinite(arr).all()
    n = len(problem.observables)
    assert (arr[:, 1 + n:] > 0).all(), 'every sigma is floored above zero'
    assert (arr[:, 1:1 + n].max(axis=0) > 0).all(), 'every observable is seen'


def _problem():
    return PROBLEMS[0]


def _errors(problem, value):
    return {name: value for name in problem.names}


def test_log10_errors_are_in_decades():
    errs = protocol.log10_errors({'a': 20.0, 'b': 0.5, 'c': None, 'd': -1.0},
                                 {'a': 2.0, 'b': 1.0, 'c': 1.0, 'd': 1.0})
    assert errs['a'] == pytest.approx(1.0)
    assert errs['b'] == pytest.approx(math.log10(2))
    assert math.isinf(errs['c']) and math.isinf(errs['d'])


def test_success_thresholds():
    assert protocol.TOL_LOOSE == pytest.approx(math.log10(2))
    assert protocol.TOL_TIGHT == 0.1


def test_simulations_to_success_reads_the_first_crossing_on_identifiable_parameters():
    trace = [(s, {'a': ea, 'b': eb}) for s, ea, eb in
             [(100, 1.2, 0.0), (300, 0.5, 0.0), (500, 0.2, 0.9), (700, 0.25, 0.0), (900, 0.05, 0.0)]]
    assert protocol.simulations_to_success(trace, ['a']) == 500
    assert protocol.simulations_to_success(trace, ['a', 'b']) == 700
    assert protocol.simulations_to_success(trace, ['a'], tol=0.1) == 900


def test_score_fit_reports_cost_to_success_only_for_a_success():
    problem = _problem()
    truth = problem.truth
    near = {k: v * 1.1 for k, v in truth.items()}
    far = dict(truth)
    far[problem.identifiable[0]] *= 5
    trace = [(200, _errors(problem, 1.0)), (600, _errors(problem, 0.2)), (1000, _errors(problem, 0.7))]
    ok = protocol.score_fit(problem, near, 1500, trace + [(1500, _errors(problem, 0.04))], method='m', seed=1)
    assert ok['success_loose'] and ok['success_tight']
    assert ok['simulations_to_success'] == 600
    assert ok['collection_version'] == protocol.COLLECTION_VERSION
    bad = protocol.score_fit(problem, far, 1500, trace + [(1500, _errors(problem, 0.7))], method='m', seed=2)
    assert not bad['success_loose']
    assert bad['simulations_to_success'] is None and bad['first_within_loose'] == 600
    json.dumps([ok, bad])


def test_aggregate_rates_and_medians():
    problem = _problem()
    truth = problem.truth
    recs = [
        protocol.score_fit(problem, {k: v * 1.05 for k, v in truth.items()}, 1000,
                           [(400, _errors(problem, 0.02))], method='m', seed=1, wall_time=10.0),
        protocol.score_fit(problem, {k: v * 1.5 for k, v in truth.items()}, 1000,
                           [(800, _errors(problem, 0.18))], method='m', seed=2, wall_time=20.0),
        protocol.score_fit(problem, {k: v * 4 for k, v in truth.items()}, 1200,
                           [(1200, _errors(problem, 0.6))], method='m', seed=3, wall_time=30.0),
    ]
    rows = protocol.aggregate(recs)
    assert len(rows) == 1
    row = rows[0]
    assert row['n_seeds'] == 3
    assert row['success_loose'] == pytest.approx(2 / 3)
    assert row['median_simulations_to_success'] == 600
    assert problem.id in protocol.format_table(rows)
