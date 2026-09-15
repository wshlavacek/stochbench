"""The floor: a stochbench runner that is not a fitting tool.

A general-purpose optimizer from SciPy, driving a simulator directly, scoring the
same chi-square the reference fits score, under the same simulation budget. It exists
to answer one question about any tool that reports results against this collection:
does the tool beat a generic optimizer at equal cost? If it does not, that is the
finding.

Nothing here imports PyBNF. The simulator is bngsim, the same one PyBNF's baseline
used, reached through its own Python API rather than through PyBNF's model layer, so
a difference between the floor and a PyBNF result is a difference of method, not of
simulator.

What is held identical to the reference fits
--------------------------------------------

* **The objective.** ``sum (sim - obs)^2 / (2 sigma^2)`` over every observable and
  every sampling time, with ``obs`` the committed replicate mean and ``sigma`` the
  committed ``_SD`` column. That is PyBNF's ``chi_sq``: a Gaussian likelihood whose
  fixed normalizer is dropped. Under smoothing the replicate trajectories are
  averaged first and the average is scored once, which is also what PyBNF does
  (``Algorithm._fold_group_result`` folds a job group by averaging).
* **The search space.** Every free parameter on a log10 scale between the frozen
  bounds, as the reference fits' ``loguniform_var`` does.
* **The budget.** Every trajectory counts as one simulation, and the fit stops within
  one evaluation of ``fit.budget_simulations`` whatever SciPy's own stopping rule
  says -- enforced by raising out of the objective, since SciPy has no budget hook.
* **The confirmation.** The answer a stochastic fit reports is the confirmed one, so
  the top candidates are re-evaluated at the end and the best of those is reported.
  Those simulations count against the fit too.

What differs, and why it is allowed to
--------------------------------------

Seeds. PyBNF derives a trajectory's seed from the parameter values and a replicate
index, which is why the committed data are drawn at replicate indices from a million
up -- otherwise a fit that lands on the true parameters would redraw the data's own
trajectories. The floor has no such policy: it uses a counter that increases across
the whole fit, so no two evaluations share a trajectory and none can coincide with the
data's. The offset is respected for a different reason than PyBNF's, and the effect is
the same.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

os.environ.setdefault('BNGSIM_ALLOW_STALE_CORE', '1')
import bngsim  # noqa: E402

#: How many of a fit's best parameter sets are re-evaluated at the end, and how many
#: times each, to decide which is really best. Matches the reference fits' confirmation
#: stage so the cost axis is comparable.
CONFIRM_CANDIDATES = 10
CONFIRM_REPLICATES = 10


class BudgetExhausted(Exception):
    """Raised out of the objective the moment the simulation budget is spent.

    SciPy's optimizers have no budget hook -- ``maxiter`` bounds generations, not
    simulations -- so the only way to stop within one evaluation of the budget is to
    raise through them and catch it outside. The best-so-far is kept on the objective,
    so nothing is lost by unwinding.
    """


def read_exp(path):
    """Columns of a stochbench data file as ``{name: array}``, in header order."""
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    header = lines[0].lstrip('#').split()
    arr = np.array([[float(x) for x in ln.split()] for ln in lines[1:]])
    return {name: arr[:, i] for i, name in enumerate(header)}


def _substitute_free(text, values):
    """A concrete BNGL: every ``name name__FREE`` alias in the parameters block
    replaced by its value.

    Scoped to the parameters block on purpose. A model's header comments describe the
    alias form in prose, and a blanket replace would rewrite the prose too; more to the
    point, the alias form is a *declaration*, and a declaration only means anything
    where declarations live.
    """
    m = re.search(r'begin parameters.*?end parameters', text, re.S)
    if m is None:
        raise ValueError('model has no parameters block')
    block = m.group(0)
    for name, value in values.items():
        bare = name[:-6] if name.endswith('__FREE') else name
        block, n = re.subn(r'(?m)^(\s*%s\s+)%s\b' % (re.escape(bare), re.escape(name)),
                           lambda mm, v=value: mm.group(1) + repr(float(v)), block)
        if n != 1:
            raise ValueError('%s: expected one alias declaration, found %d' % (name, n))
    leftover = re.search(r'\w+__FREE', block)
    if leftover:
        raise ValueError('unsubstituted alias %s' % leftover.group(0))
    return text[:m.start()] + block + text[m.end():]


def _model_block(text):
    """The model block alone, with the author's actions dropped -- the actions are the
    problem definition's business, not the model file's, and running them would run the
    author's experiment."""
    m = re.search(r'begin model.*?end model', text, re.S)
    return m.group(0) if m else re.split(r'begin actions', text)[0]


class Simulator:
    """Runs one problem's model at arbitrary parameter values.

    Built once per fit. For a network-based problem the network is generated once, at
    the true parameter values, and later parameter sets are written straight into the
    generated model: rate constants do not change a network's topology, so regenerating
    it per evaluation would cost seconds and buy nothing. For a network-free problem
    there is no network to generate, but BNG2.pl has to write the XML NFsim reads, and
    that *does* depend on the parameter values, so it is redone per parameter set --
    which is part of why the network-free problems carry smaller budgets.
    """

    def __init__(self, problem, workdir=None):
        self.problem = problem
        self._tmp = None
        if workdir is None:
            self._tmp = workdir = tempfile.mkdtemp(prefix='floor_%s_' % problem.id[:12])
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.text = problem.model_path.read_text()
        self.replicate = 0            # monotonic across the fit; never repeats a seed
        self.simulations = 0          # every trajectory, which is the protocol's currency
        self._model = None
        if problem.method == 'ssa':
            path = self._write_bngl(problem.truth, 'template')
            self._model = bngsim.Model.from_bngl(str(path))
        elif problem.method != 'nf':
            raise ValueError('unknown simulate method %r' % problem.method)

    def close(self):
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- BNGL plumbing ------------------------------------------------------
    def _write_bngl(self, values, stem):
        path = self.workdir / ('%s.bngl' % stem)
        path.write_text(_model_block(_substitute_free(self.text, values)) + '\n')
        return path

    def _write_xml(self, values):
        d = Path(tempfile.mkdtemp(prefix='floor_xml_', dir=self.workdir))
        src = d / 'm.bngl'
        src.write_text(_model_block(_substitute_free(self.text, values))
                       + '\nbegin actions\nwriteXML()\nend actions\n')
        bng2 = _bng2_pl()
        run = subprocess.run(['perl', bng2, '--outdir', str(d), str(src)],
                             capture_output=True, text=True, timeout=1800)
        xml = d / 'm.xml'
        if not xml.is_file():
            raise RuntimeError('BNG2.pl writeXML failed: %s'
                               % (run.stderr or run.stdout)[-400:])
        return d, xml

    # -- simulation ---------------------------------------------------------
    def replicate_mean(self, values, n):
        """The mean of ``n`` trajectories at ``values``, as ``{observable: array}``.

        Counts ``n`` simulations whatever happens, including a failure: a parameter set
        the simulator cannot run still cost what it cost.
        """
        p = self.problem
        times = p.sample_times
        self.simulations += n
        first = self.replicate
        self.replicate += n
        runs = []
        if p.method == 'ssa':
            self._model.set_params({k[:-6]: float(v) for k, v in values.items()})
            sim = bngsim.Simulator(self._model, method='ssa')
            for r in sim.run_replicates(n, (times[0], times[-1]), len(times),
                                        seed=first + 1):
                runs.append(np.column_stack([np.asarray(r.observables[o]) for o in p.observables]))
        else:
            d, xml = self._write_xml(values)
            try:
                for i in range(n):
                    with bngsim.NfsimSession(xml, block_same_complex_binding=True) as s:
                        s.initialize(seed=first + 1 + i)
                        r = s.simulate(times[0], times[-1], len(times))
                        runs.append(np.column_stack([np.asarray(r.observables[o]) for o in p.observables]))
            finally:
                shutil.rmtree(d, ignore_errors=True)
        mean = np.mean(runs, axis=0)
        return {o: mean[:, j] for j, o in enumerate(p.observables)}


def _bng2_pl():
    """BNG2.pl, from ``$BNG2_PL`` or ``$BNGPATH``."""
    explicit = os.environ.get('BNG2_PL')
    if explicit:
        return explicit
    bngpath = os.environ.get('BNGPATH')
    if bngpath:
        candidate = Path(bngpath) / 'BNG2.pl'
        if candidate.is_file():
            return str(candidate)
    found = shutil.which('BNG2.pl')
    if found:
        return found
    raise RuntimeError('BNG2.pl not found; set BNGPATH or BNG2_PL')


class Objective:
    """The frozen chi-square of one problem, with the budget enforced on every call.

    Callable with a vector of log10 parameter values in the problem's parameter order,
    which is the space the optimizers search -- the same log scale the reference fits'
    ``loguniform_var`` searches on.
    """

    def __init__(self, problem, simulator, budget=None, replicates=None, on_improve=None):
        self.problem = problem
        self.sim = simulator
        self.budget = int(problem.budget_simulations if budget is None else budget)
        self.replicates = int(problem.smoothing if replicates is None else replicates)
        self.on_improve = on_improve
        data = read_exp(problem.data_path)
        self.obs = {o: data[o] for o in problem.observables}
        self.sigma = {o: data[o + '_SD'] for o in problem.observables}
        self.best_score = math.inf
        self.best_values = None
        self.history = []             # (score, {name: value}), for the confirmation stage

    # -- the chi-square -----------------------------------------------------
    def chi_square(self, simulated):
        """``sum (sim - obs)^2 / (2 sigma^2)``: PyBNF's ``chi_sq``, whose fixed Gaussian
        normalizer is parameter-independent and therefore dropped."""
        total = 0.0
        for o in self.problem.observables:
            residual = simulated[o] - self.obs[o]
            total += float(np.sum(residual ** 2 / (2.0 * self.sigma[o] ** 2)))
        return total

    # -- one evaluation -----------------------------------------------------
    def values_from_log10(self, x):
        return {p.name: float(10.0 ** xi) for p, xi in zip(self.problem.parameters, x)}

    def __call__(self, x):
        if self.sim.simulations >= self.budget:
            raise BudgetExhausted()
        values = self.values_from_log10(x)
        try:
            score = self.chi_square(self.sim.replicate_mean(values, self.replicates))
        except Exception:
            # A parameter set the simulator cannot run -- a particle-count blow-up, a
            # rate that makes a trajectory unbounded -- is a bad parameter set, not a
            # crashed fit. It costs its replicates and scores as infinite, which is what
            # a fitting tool does with a failed simulation.
            score = math.inf
        if not math.isfinite(score):
            score = math.inf
        self.history.append((score, values))
        if score < self.best_score:
            self.best_score = score
            self.best_values = values
            if self.on_improve is not None:
                self.on_improve(self.sim.simulations, values)
        return score

    # -- the end-of-fit confirmation ---------------------------------------
    def confirm(self, candidates=CONFIRM_CANDIDATES, replicates=CONFIRM_REPLICATES):
        """Re-evaluate the best distinct parameter sets the search saw and return the
        best of them.

        A single noisy evaluation can look good by luck, so the answer a stochastic fit
        reports should be the one that survives being run again. The reference fits do
        this and count its simulations; so does the floor.
        """
        seen, ranked = set(), []
        for score, values in sorted(self.history, key=lambda sv: sv[0]):
            key = tuple(round(math.log10(v), 9) if v > 0 else v for v in values.values())
            if key in seen:
                continue
            seen.add(key)
            ranked.append(values)
            if len(ranked) >= candidates:
                break
        best_values, best_score = self.best_values, math.inf
        for values in ranked:
            try:
                score = self.chi_square(self.sim.replicate_mean(values, replicates))
            except Exception:
                score = math.inf
            if score < best_score:
                best_score, best_values = score, values
        if self.on_improve is not None and best_values is not None:
            self.on_improve(self.sim.simulations, best_values)
        return best_values, best_score
