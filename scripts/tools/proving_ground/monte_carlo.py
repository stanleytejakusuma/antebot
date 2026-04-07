"""PROVING GROUND — Monte Carlo runner (Pillar 1).

Parallelises run_session across CPU cores for fast strategy evaluation.
"""

import multiprocessing
import statistics


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_stats(results):
    """Compute summary statistics from a list of (profit, busted) tuples.

    Args:
        results: list of (profit: float, busted: bool)

    Returns:
        dict with keys: median, mean, bust_pct, win_pct,
                        p5, p10, p25, p75, p90, p95, count
    """
    profits = [r[0] for r in results]
    busted_flags = [r[1] for r in results]
    n = len(profits)

    if n == 0:
        return {
            "median": 0.0, "mean": 0.0,
            "bust_pct": 0.0, "win_pct": 0.0,
            "p5": 0.0, "p10": 0.0, "p25": 0.0,
            "p75": 0.0, "p90": 0.0, "p95": 0.0,
            "count": 0,
        }

    sorted_p = sorted(profits)
    bust_count = sum(1 for b in busted_flags if b)
    win_count = sum(1 for p in profits if p > 0)

    def _percentile(data, pct):
        """Linear interpolation percentile (matches numpy default)."""
        idx = (pct / 100.0) * (len(data) - 1)
        lo = int(idx)
        hi = lo + 1
        if hi >= len(data):
            return data[-1]
        frac = idx - lo
        return data[lo] + frac * (data[hi] - data[lo])

    return {
        "median": statistics.median(profits),
        "mean": statistics.mean(profits),
        "bust_pct": 100.0 * bust_count / n,
        "win_pct": 100.0 * win_count / n,
        "p5": _percentile(sorted_p, 5),
        "p10": _percentile(sorted_p, 10),
        "p25": _percentile(sorted_p, 25),
        "p75": _percentile(sorted_p, 75),
        "p90": _percentile(sorted_p, 90),
        "p95": _percentile(sorted_p, 95),
        "count": n,
    }


# ---------------------------------------------------------------------------
# Worker (top-level for multiprocessing pickle)
# ---------------------------------------------------------------------------

def _worker(args):
    """Top-level worker function for multiprocessing.Pool.

    Imports run_session inside to avoid pickling issues with module state.
    """
    from proving_ground.session import run_session
    strategy, engine, params, seed_offset = args
    p, busted = run_session(strategy, engine, seed_offset=seed_offset, **params)
    return (p, busted)


# ---------------------------------------------------------------------------
# Primary runner
# ---------------------------------------------------------------------------

def run_mc(strategy, engine, params, num=5000, seed=42, cores=None):
    """Run Monte Carlo simulation over num sessions.

    Args:
        strategy:  Strategy instance
        engine:    Engine instance
        params:    dict of kwargs forwarded to run_session
                   (bank, divider, stop_pct, sl_pct, trail_act, trail_lock, seed, ...)
        num:       Number of sessions to simulate
        seed:      Base seed -- combined with seed_offset per session
        cores:     Worker count (default: cpu_count())

    Returns:
        dict from compute_stats
    """
    if cores is None:
        cores = multiprocessing.cpu_count()

    # Merge caller seed into params (seed_offset is the per-session differentiator)
    merged_params = dict(params)
    merged_params["seed"] = seed

    args_list = [
        (strategy, engine, merged_params, i)
        for i in range(num)
    ]

    if cores == 1:
        results = [_worker(a) for a in args_list]
    else:
        with multiprocessing.Pool(processes=cores) as pool:
            results = pool.map(_worker, args_list)

    return compute_stats(results)


# ---------------------------------------------------------------------------
# Multi-seed runner
# ---------------------------------------------------------------------------

def run_mc_multi_seed(strategy, engine, params, num=5000, seeds=None, cores=None):
    """Run run_mc across multiple seeds to measure cross-seed variance.

    Args:
        strategy:  Strategy instance
        engine:    Engine instance
        params:    dict of kwargs forwarded to run_session
        num:       Sessions per seed
        seeds:     list of seed ints (default [42, 123, 456, 789, 1337])
        cores:     Worker count passed to run_mc

    Returns:
        dict with:
            per_seed    -- list of (seed, stats_dict) pairs
            avg_median  -- arithmetic mean of per-seed medians
            std_median  -- stdev of per-seed medians (0.0 if only one seed)
            median_range -- (min_median, max_median)
    """
    if seeds is None:
        seeds = [42, 123, 456, 789, 1337]

    per_seed = []
    medians = []

    for s in seeds:
        stats = run_mc(strategy, engine, params, num=num, seed=s, cores=cores)
        per_seed.append((s, stats))
        medians.append(stats["median"])

    avg_median = statistics.mean(medians)
    std_median = statistics.stdev(medians) if len(medians) > 1 else 0.0
    median_range = (min(medians), max(medians))

    return {
        "per_seed": per_seed,
        "avg_median": avg_median,
        "std_median": std_median,
        "median_range": median_range,
    }
