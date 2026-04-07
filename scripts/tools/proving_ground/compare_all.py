#!/usr/bin/env python3
"""Run ALL snake family strategies through PROVING GROUND."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proving_ground.monte_carlo import run_mc
from proving_ground.strategy import MambaStrategy, SidewinderStrategy, FlatStrategy, IOLStrategy
from proving_ground.engines import DiceEngine, RouletteEngine, HiLoEngine


def pr(tag, r):
    print("  {:<50} ${:>+7.2f} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} ${:>+7.2f}".format(
        tag, r['median'], r['mean'], r['bust_pct'], r['win_pct'], r['p10'], r['p90'], r.get('p5', 0)))

H = "  {:<50} {:>8} {:>8} {:>6} {:>6} {:>8} {:>8} {:>8}".format(
    'Strategy', 'Med', 'Mean', 'Bust%', 'Win%', 'P10', 'P90', 'P5')
S = "  {} {} {} {} {} {} {} {}".format('-'*50, '-'*8, '-'*8, '-'*6, '-'*6, '-'*8, '-'*8, '-'*8)


def main():
    num = 5000
    bank = 100
    params = dict(bank=bank, divider=10000, stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60, seed=42)

    print()
    print("=" * 115)
    print("  PROVING GROUND — FULL SNAKE FAMILY COMPARISON")
    print("  {} sessions | ${} bank | trail=8/60 SL=15% stop=15%".format(num, bank))
    print("=" * 115)

    results = []
    t0 = time.time()

    # === DICE ===
    print("\n  === DICE ===")
    print(H); print(S)

    r = run_mc(MambaStrategy(iol=3.0), DiceEngine(65), params, num=num)
    r['tag'] = 'MAMBA dice 65% IOL=3.0x'
    results.append(r); pr(r['tag'], r)

    for chance in [50, 75, 85]:
        s = IOLStrategy(iol=3.0, game="dice")
        e = DiceEngine(chance)
        r = run_mc(s, e, params, num=num)
        r['tag'] = 'Dice {}% IOL=3.0x'.format(chance)
        results.append(r); pr(r['tag'], r)

    r = run_mc(FlatStrategy("dice"), DiceEngine(65), params, num=num)
    r['tag'] = 'Flat dice 65% (no IOL)'
    results.append(r); pr(r['tag'], r)

    # === ROULETTE ===
    print("\n  === ROULETTE ===")
    print(H); print(S)

    s = IOLStrategy(iol=3.0, game="roulette")
    e = RouletteEngine(covered_count=23)
    r = run_mc(s, e, params, num=num)
    r['tag'] = 'COBRA roulette 23num IOL=3.0x'
    results.append(r); pr(r['tag'], r)

    for cov in [18, 24, 30]:
        s = IOLStrategy(iol=3.0, game="roulette")
        e = RouletteEngine(covered_count=cov)
        r = run_mc(s, e, params, num=num)
        r['tag'] = 'Roulette {}num IOL=3.0x'.format(cov)
        results.append(r); pr(r['tag'], r)

    r = run_mc(FlatStrategy("roulette"), RouletteEngine(23), params, num=num)
    r['tag'] = 'Flat roulette 23num (no IOL)'
    results.append(r); pr(r['tag'], r)

    # === HILO ===
    print("\n  === HILO ===")
    print(H); print(S)

    r = run_mc(SidewinderStrategy(iol=3.0), HiLoEngine(skip_set=frozenset({6,7,8}), cashout_target=1.5), params, num=num)
    r['tag'] = 'SIDEWINDER HiLo IOL=3.0x skip={6-8}'
    results.append(r); pr(r['tag'], r)

    for iol in [2.0, 2.5, 4.0]:
        r = run_mc(SidewinderStrategy(iol=iol), HiLoEngine(skip_set=frozenset({6,7,8}), cashout_target=1.5), params, num=num)
        r['tag'] = 'SIDEWINDER IOL={}x'.format(iol)
        results.append(r); pr(r['tag'], r)

    for skip_label, skip_set in [("5-9", frozenset({5,6,7,8,9})), ("7 only", frozenset({7})), ("none", frozenset())]:
        r = run_mc(SidewinderStrategy(iol=3.0, skip_set=skip_set),
                   HiLoEngine(skip_set=skip_set, cashout_target=1.5), params, num=num)
        r['tag'] = 'SIDEWINDER skip={{{}}}'.format(skip_label)
        results.append(r); pr(r['tag'], r)

    r = run_mc(FlatStrategy("hilo"), HiLoEngine(skip_set=frozenset({6,7,8}), cashout_target=1.5), params, num=num)
    r['tag'] = 'Flat HiLo co=1.5 (no IOL)'
    results.append(r); pr(r['tag'], r)

    # === GRAND RANKING ===
    print()
    print("=" * 115)
    print("  GRAND RANKING — All strategies by median profit")
    print("=" * 115)
    print(H); print(S)

    results.sort(key=lambda x: x['median'], reverse=True)
    for i, r in enumerate(results):
        pr("#{:<2} {}".format(i+1, r['tag']), r)

    # === SAFETY RANKING ===
    print()
    print("=" * 115)
    print("  SAFETY RANKING — by P10 (least tail risk)")
    print("=" * 115)
    print(H); print(S)

    results.sort(key=lambda x: x['p10'], reverse=True)
    for i, r in enumerate(results):
        pr("#{:<2} {}".format(i+1, r['tag']), r)

    # === RISK-ADJUSTED ===
    print()
    print("=" * 115)
    print("  RISK-ADJUSTED — median / |P10| (higher = better)")
    print("=" * 115)
    for r in results:
        r['risk_adj'] = r['median'] / abs(r['p10']) if r['p10'] != 0 and r['median'] > 0 else -1
    print(H); print(S)
    results.sort(key=lambda x: x['risk_adj'], reverse=True)
    for i, r in enumerate(results):
        ra = r['risk_adj']
        pr("#{:<2} {} (ra={:.3f})".format(i+1, r['tag'], ra), r)

    elapsed = time.time() - t0
    print("\n  Runtime: {:.1f}s".format(elapsed))
    print("=" * 115)


if __name__ == "__main__":
    main()
