#!/usr/bin/env python3
"""Run the floor against the stochbench collection.

Subcommands::

    run        fit problems x methods x seeds, appending one record per fit to a JSON
               results file (resumable: pairs already in the file are skipped)
    summarize  aggregate a results file into the per-(problem, method) table
    check      evaluate the objective at the true parameters, as a toolchain test
    verify     check that writing a parameter value reaches the trajectory

Methods::

    floor_de     scipy.optimize.differential_evolution over log10 parameters
    floor_cmaes  CMA-ES from the ``cma`` package, same space, same objective

Both are general-purpose optimizers with no knowledge that their objective is noisy.
That is the point: a fitting tool that does not beat them at equal simulation budget
has not earned its complexity.

Needs numpy, scipy, cma, bngsim and BNG2.pl (set ``BNGPATH``); the network-free
problems also need bngsim's NFsim backend. See README.md.

Examples::

    python runners/floor/run_floor.py check --problems Hlavacek_PNAS2001
    python runners/floor/run_floor.py run --seeds 5 --parallel 10 \\
        --out results/floor_v1.json
    python runners/floor/run_floor.py summarize results/floor_v1.json \\
        --out results/floor_v1.md
"""
import argparse
import json
import math
import multiprocessing
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / 'src' / 'python'))

from stochbench import protocol  # noqa: E402

METHODS = ('floor_de', 'floor_cmaes')


# --------------------------------------------------------------------------- #
# The two optimizers
# --------------------------------------------------------------------------- #
def _fit_de(objective, bounds, seed):
    """SciPy's differential evolution over the log10 box.

    ``maxiter`` is set past anything the budget allows and ``tol=0`` disables the
    convergence stop, so the simulation budget is the only thing that ends the search --
    the same arrangement the reference fits use, and for the same reason: a noisy
    population never converges, so a convergence stop would fire on noise.
    ``polish=False`` because the polish is a local gradient step, which is meaningless
    on a stochastic objective and would spend budget pretending otherwise.
    """
    from scipy.optimize import differential_evolution
    differential_evolution(objective, bounds, seed=seed, popsize=20, tol=0, mutation=(0.5, 1.0),
                           recombination=0.7, maxiter=10 ** 6, polish=False, init='latinhypercube',
                           updating='deferred', workers=1)


def _fit_cmaes(objective, bounds, seed):
    """CMA-ES over the same box, started at its centre with a step of a quarter of its
    width, which is the usual advice for a box with no better prior."""
    import cma
    lows = [lo for lo, _ in bounds]
    highs = [hi for _, hi in bounds]
    x0 = [(lo + hi) / 2.0 for lo, hi in bounds]
    sigma0 = min((hi - lo) for lo, hi in bounds) / 4.0
    es = cma.CMAEvolutionStrategy(x0, sigma0, {
        'bounds': [lows, highs], 'seed': int(seed) + 1, 'verbose': -9,
        'maxiter': 10 ** 6, 'tolfun': 0, 'tolx': 0, 'tolfunhist': 0,
    })
    while not es.stop():
        xs = es.ask()
        es.tell(xs, [objective(x) for x in xs])


_FITTERS = {'floor_de': _fit_de, 'floor_cmaes': _fit_cmaes}


# --------------------------------------------------------------------------- #
# One fit
# --------------------------------------------------------------------------- #
def run_fit(problem, method, seed, budget=None):
    """Fit ``problem`` with ``method`` from ``seed`` and return its scored record.

    The trace holds the reported best each time it improved, as
    ``(simulations spent, {parameter: error})``, so ``protocol.rescore`` can score the
    record again if a definition's identifiability flags are ever revised.
    """
    import floor as F
    if method not in _FITTERS:
        raise KeyError('unknown method %r (have %s)' % (method, sorted(_FITTERS)))
    budget = int(problem.budget_simulations if budget is None else budget)
    truth = problem.truth
    trace = []
    started = time.time()

    with F.Simulator(problem) as sim:
        def on_improve(simulations, values):
            trace.append((simulations, protocol.log10_errors(values, truth)))

        objective = F.Objective(problem, sim, budget=budget, on_improve=on_improve)
        bounds = [(math.log10(p.low), math.log10(p.high)) for p in problem.parameters]
        search_simulations = None
        try:
            _FITTERS[method](objective, bounds, seed)
            stop_reason = 'optimizer stop'
        except F.BudgetExhausted:
            stop_reason = ('Simulation budget reached: stopped after %d simulation(s)'
                           % sim.simulations)
        search_simulations = sim.simulations

        # The confirmation runs past the budget, exactly as the reference fits' does,
        # and its simulations are counted: the answer it picks is the answer reported.
        estimate, best_score = objective.confirm()
        simulations = sim.simulations

    estimate = estimate or {}
    trace.append((simulations, protocol.log10_errors(estimate, truth)))
    return protocol.score_fit(
        problem, estimate, simulations, trace,
        method=method, seed=int(seed), budget=budget,
        simulations_search=search_simulations,
        best_score=(None if not math.isfinite(best_score) else float(best_score)),
        wall_time=time.time() - started, stop_reason=stop_reason,
        tool='floor',
    )


def run_fit_json(args):
    """``run_fit`` for a process pool: ``(problem_dir, method, seed, budget)`` in, the
    JSON-serializable record out."""
    problem_dir, method, seed, budget = args
    return run_fit(protocol.load_problem(problem_dir), method, seed, budget=budget)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def _load_records(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else []


def _save_records(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(records, indent=1) + '\n')
    tmp.replace(path)


def cmd_run(args):
    problems = protocol.load_problems(ids=args.problems or None)
    methods = args.methods or list(METHODS)
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        sys.exit('unknown method(s): %s (have %s)' % (unknown, sorted(METHODS)))
    seeds = list(range(args.first_seed, args.first_seed + args.seeds))
    records = _load_records(args.out)
    done = {(r['problem'], r['method'], r['seed']) for r in records}
    jobs = []
    # The network-free fits go first, so they do not trail the run at the end.
    for p in sorted(problems, key=lambda p: p.method != 'nf'):
        budget = p.budget_simulations if args.budget is None else args.budget
        for m in methods:
            for s in seeds:
                if (p.id, m, s) not in done:
                    jobs.append((str(p.directory), m, s, budget))
    print('%d fit(s) to run (%d already in %s), %d worker(s)'
          % (len(jobs), len(done), args.out, args.parallel), flush=True)
    if not jobs:
        return
    started = time.time()
    ctx = multiprocessing.get_context('spawn')
    with ctx.Pool(args.parallel) as pool:
        for i, rec in enumerate(pool.imap_unordered(run_fit_json, jobs), 1):
            records.append(rec)
            _save_records(args.out, records)
            print('[%3d/%d %6.0fs] %-30s %-12s seed %d  sims %6d  max err %.3f  %s'
                  % (i, len(jobs), time.time() - started, rec['problem'], rec['method'],
                     rec['seed'], rec['simulations'], rec['max_error'],
                     'ok' if rec['success_loose'] else '--'), flush=True)
    print('done in %.0f s' % (time.time() - started))


def cmd_summarize(args):
    rows = protocol.aggregate(_load_records(args.results))
    table = protocol.format_table(rows)
    print(table)
    if args.out:
        Path(args.out).write_text(table + '\n')


def cmd_check(args):
    """Evaluate the objective at the true parameters.

    Two things this is for. It proves the toolchain runs every problem, before a
    campaign discovers otherwise hours in. And the number it prints is directly
    comparable with what the PyBNF harness's ``leverage`` reports as the objective at
    the truth, which is how the claim that the two score the same chi-square is
    checked rather than asserted.
    """
    import floor as F
    for p in protocol.load_problems(ids=args.problems or None):
        with F.Simulator(p) as sim:
            objective = F.Objective(p, sim, budget=10 ** 9)
            t0 = time.time()
            scores = [objective(
                [math.log10(v) for v in p.truth.values()]) for _ in range(args.repeats)]
            dt = time.time() - t0
        mean = sum(scores) / len(scores)
        sd = (sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)) ** 0.5 if len(scores) > 1 else 0.0
        print('%-30s objective at the truth %9.2f +- %-8.2f  (%d x %d replicates, %.0f s)'
              % (p.id, mean, sd, args.repeats, p.smoothing, dt), flush=True)


def cmd_verify(args):
    """Check that writing a parameter value actually reaches the trajectory.

    The floor generates a network-based problem's network once, at the true parameter
    values, and writes later parameter sets into the generated model. That is only sound
    if a write reaches the run -- including a parameter that a derived expression turns
    into an initial condition, as ``Rubenstein_BiophysChem2007``'s ``lambda`` and ``d``
    do through ``x_0 = lambda/d``. A write that were silently ignored would not raise;
    it would produce a fit that searches a space it cannot move in, and report an honest
    looking failure. So this is checked, not assumed: every parameter is taken to ten
    times its true value on its own and the objective has to move by more than the
    objective's own noise.
    """
    import floor as F
    bad = []
    for p in protocol.load_problems(ids=args.problems or None):
        if p.method != 'ssa':
            continue      # a network-free problem rebuilds its XML per parameter set
        with F.Simulator(p) as sim:
            objective = F.Objective(p, sim, budget=10 ** 9)
            x_true = [math.log10(v) for v in p.truth.values()]
            at_truth = objective(x_true)
            shifts = []
            for i, par in enumerate(p.parameters):
                x = list(x_true)
                x[i] += 1.0
                shifts.append((par.name[:-6], abs(objective(x) - at_truth)))
        worst_name, worst = min(shifts, key=lambda ns: ns[1])
        ok = worst > args.threshold
        if not ok:
            bad.append((p.id, worst_name, worst))
        print('%-30s objective %9.2f at the truth; smallest shift at 10x is %s by %.1f  %s'
              % (p.id, at_truth, worst_name, worst, 'ok' if ok else 'NOT MOVING'), flush=True)
    if bad:
        sys.exit('parameter writes are not reaching the trajectory: %s'
                 % ', '.join('%s.%s' % (pid, n) for pid, n, _ in bad))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    r = sub.add_parser('run', help='run fits')
    r.add_argument('--problems', nargs='*', help='problem ids (default: all)')
    r.add_argument('--methods', nargs='*', help='floor method names (default: all)')
    r.add_argument('--seeds', type=int, default=5)
    r.add_argument('--first-seed', type=int, default=1)
    r.add_argument('--budget', type=int, default=None,
                   help="override every problem's simulation budget")
    r.add_argument('--parallel', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    r.add_argument('--out', default='results/floor_v1.json')
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser('summarize', help='aggregate a results file')
    s.add_argument('results')
    s.add_argument('--out', help='also write the Markdown table here')
    s.set_defaults(fn=cmd_summarize)

    c = sub.add_parser('check', help='evaluate the objective at the true parameters')
    c.add_argument('--problems', nargs='*')
    c.add_argument('--repeats', type=int, default=6)
    c.set_defaults(fn=cmd_check)

    v = sub.add_parser('verify', help='check that parameter writes reach the trajectory')
    v.add_argument('--problems', nargs='*')
    v.add_argument('--threshold', type=float, default=1.0,
                   help='how far the objective must move, in its own units, at ten times a '
                        "parameter's true value (default 1)")
    v.set_defaults(fn=cmd_verify)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == '__main__':
    sys.path.insert(0, str(_HERE))
    main()
