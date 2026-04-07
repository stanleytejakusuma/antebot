#!/usr/bin/env python3
"""Run the universal scorecard against all top strategy candidates."""
import random, time, sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.scorecard import scorecard, print_scorecard, print_ranking
from proving_ground.honest_eval import _mamba, _hybrid, _highchance

SEED = 42; BANK = 100; N = 5000


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())

    configs = [
        # (label, func, arg_builder, house_edge)
        ("MAMBA 65% IOL=3.0x",         _mamba,      lambda s: (s, BANK),                1.0),
        ("HYB 50% dal=3 mart=3.0x",    _hybrid,     lambda s: (s, BANK, 50, 3, 3.0),   1.0),
        ("HYB 50% dal=5 mart=3.0x",    _hybrid,     lambda s: (s, BANK, 50, 5, 3.0),   1.0),
        ("HYB 50% dal=5 mart=2.0x",    _hybrid,     lambda s: (s, BANK, 50, 5, 2.0),   1.0),
        ("HYB 50% dal=7 mart=3.0x",    _hybrid,     lambda s: (s, BANK, 50, 7, 3.0),   1.0),
        ("HYB 65% dal=3 mart=3.0x",    _hybrid,     lambda s: (s, BANK, 65, 3, 3.0),   1.0),
        ("HICH 75% IOL=5.0x",          _highchance, lambda s: (s, BANK, 75, 5.0),       1.0),
        ("HICH 80% IOL=5.0x",          _highchance, lambda s: (s, BANK, 80, 5.0),       1.0),
        ("HICH 80% IOL=7.0x",          _highchance, lambda s: (s, BANK, 80, 7.0),       1.0),
        ("HICH 85% IOL=7.0x",          _highchance, lambda s: (s, BANK, 85, 7.0),       1.0),
    ]

    print()
    print("=" * 105)
    print("  UNIVERSAL STRATEGY SCORECARD")
    print("  G = exp(mean(log(wealth_ratio))) - 1    |   {} sessions, ${} bank, trail 10/60".format(N, BANK))
    print("=" * 105)

    scorecards = []

    for label, func, arg_fn, edge in configs:
        args = [arg_fn(s) for s in range(N)]
        results = pool.map(func, args)
        s = scorecard(results, bank=BANK, house_edge_pct=edge, label=label)
        scorecards.append(s)

    # Print top 3 detailed scorecards
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    for s in scorecards[:3]:
        print_scorecard(s, BANK)
        print()

    # Print full ranking
    print()
    print("=" * 105)
    print("  FULL RANKING BY G (session growth rate)")
    print("=" * 105)
    print_ranking(scorecards, BANK)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 105)
