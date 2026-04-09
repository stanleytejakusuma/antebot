#!/usr/bin/env python3
"""PROVING GROUND — Coverage "90% win rate" vs Snake family roulette strategies.

Tests the claim: 33/37 coverage flat betting ($150 high + $50 7-12 + $50 13-18
+ $25 split 0/2/3) = "90% win rate". Every hit nets +$25 on $275 wagered;
every miss (1,4,5,6) loses -$275.

Math: net_payout = 36/33 - 1 = 1/11 = 0.0909x  |  win_prob = 33/37 = 89.2%
EV per spin = -2.70% (identical to any other roulette layout).

Coverage is modelled as RouletteEngine(covered_count=33) because all hits produce
the same net multiplier. This is exact — verified algebraically above.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proving_ground.monte_carlo import run_mc
from proving_ground.strategy import FlatStrategy, IOLStrategy
from proving_ground.engines import RouletteEngine


def pr(tag, r):
    print("  {:<55} ${:>+7.2f} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} ${:>+7.2f}".format(
        tag, r['median'], r['mean'], r['bust_pct'], r['win_pct'], r['p10'], r['p90'], r.get('p5', 0)))


H = "  {:<55} {:>8} {:>8} {:>6} {:>6} {:>8} {:>8} {:>8}".format(
    'Strategy', 'Med', 'Mean', 'Bust%', 'Win%', 'P10', 'P90', 'P5')
S = "  {} {} {} {} {} {} {} {}".format('-'*55, '-'*8, '-'*8, '-'*6, '-'*6, '-'*8, '-'*8, '-'*8)


def main():
    num = 5000
    bank = 100
    params = dict(bank=bank, divider=10000, stop_pct=15, sl_pct=15,
                  trail_act=8, trail_lock=60, seed=42)

    print()
    print("=" * 120)
    print('  PROVING GROUND — COVERAGE "90% WIN RATE" vs SNAKE ROULETTE')
    print("  {} sessions | ${} bank | trail=8/60 SL=15% stop=15%".format(num, bank))
    print("=" * 120)

    results = []
    t0 = time.time()

    # ===================================================================
    # SECTION 1: The "90% win rate" coverage strategy (flat, no IOL)
    # ===================================================================
    print("\n  === COVERAGE STRATEGY (33/37, FLAT) ===")
    print(H); print(S)

    # Exact model of the user's layout: 33 covered, flat betting
    r = run_mc(FlatStrategy("roulette"), RouletteEngine(33), params, num=num)
    r['tag'] = 'COVERAGE 33num FLAT (the "90% strategy")'
    results.append(r); pr(r['tag'], r)

    # What if we add IOL to coverage? (hypothetical)
    for iol in [2.0, 3.0, 3.5]:
        r = run_mc(IOLStrategy(iol=iol, game="roulette"), RouletteEngine(33), params, num=num)
        r['tag'] = 'Coverage 33num IOL={}x (hypothetical)'.format(iol)
        results.append(r); pr(r['tag'], r)

    # ===================================================================
    # SECTION 2: Snake family roulette (COBRA, TAIPAN baselines)
    # ===================================================================
    print("\n  === SNAKE FAMILY ROULETTE ===")
    print(H); print(S)

    # COBRA: 23 numbers, IOL 3.0x
    r = run_mc(IOLStrategy(iol=3.0, game="roulette"), RouletteEngine(23), params, num=num)
    r['tag'] = 'COBRA 23num IOL=3.0x'
    results.append(r); pr(r['tag'], r)

    # TAIPAN-like: 12 numbers (dozen), IOL 3.0x
    r = run_mc(IOLStrategy(iol=3.0, game="roulette"), RouletteEngine(12), params, num=num)
    r['tag'] = 'TAIPAN-like 12num IOL=3.0x (dozen)'
    results.append(r); pr(r['tag'], r)

    # Even-money flat (18 numbers, no IOL) — classic red/black
    r = run_mc(FlatStrategy("roulette"), RouletteEngine(18), params, num=num)
    r['tag'] = 'Flat 18num (red/black, no IOL)'
    results.append(r); pr(r['tag'], r)

    # Even-money with IOL
    r = run_mc(IOLStrategy(iol=3.0, game="roulette"), RouletteEngine(18), params, num=num)
    r['tag'] = 'Red/Black 18num IOL=3.0x'
    results.append(r); pr(r['tag'], r)

    # Flat 23 (COBRA coverage without IOL) — isolates IOL contribution
    r = run_mc(FlatStrategy("roulette"), RouletteEngine(23), params, num=num)
    r['tag'] = 'Flat 23num (COBRA coverage, no IOL)'
    results.append(r); pr(r['tag'], r)

    # ===================================================================
    # SECTION 3: Coverage sweep — does MORE coverage help?
    # ===================================================================
    print("\n  === COVERAGE SWEEP (flat, no IOL) ===")
    print(H); print(S)

    for cov in [12, 18, 23, 28, 33, 35]:
        wp = cov / 37.0 * 100
        net = 36.0 / cov - 1.0
        r = run_mc(FlatStrategy("roulette"), RouletteEngine(cov), params, num=num)
        r['tag'] = 'Flat {}num (win={:.0f}% net={:.3f}x)'.format(cov, wp, net)
        results.append(r); pr(r['tag'], r)

    # ===================================================================
    # GRAND RANKING
    # ===================================================================
    print()
    print("=" * 120)
    print("  GRAND RANKING — by median profit")
    print("=" * 120)
    print(H); print(S)

    results.sort(key=lambda x: x['median'], reverse=True)
    for i, r in enumerate(results):
        pr("#{:<2} {}".format(i+1, r['tag']), r)

    # ===================================================================
    # RISK-ADJUSTED RANKING
    # ===================================================================
    print()
    print("=" * 120)
    print("  RISK-ADJUSTED — median / |P10| (higher = better)")
    print("=" * 120)
    for r in results:
        r['risk_adj'] = r['median'] / abs(r['p10']) if r['p10'] != 0 and r['median'] > 0 else -1
    print(H); print(S)
    results.sort(key=lambda x: x['risk_adj'], reverse=True)
    for i, r in enumerate(results):
        ra = r['risk_adj']
        pr("#{:<2} {} (ra={:.3f})".format(i+1, r['tag'], ra), r)

    elapsed = time.time() - t0
    print("\n  Runtime: {:.1f}s".format(elapsed))
    print("=" * 120)


if __name__ == "__main__":
    main()
