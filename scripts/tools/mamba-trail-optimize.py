#!/usr/bin/env python3
"""
MAMBA v2 Trail Optimizer — Find optimal (trailActivatePct, trailLockPct) pair
Sweeps across stop levels to find the best trailing stop config.

Usage:
  python3 mamba-trail-optimize.py          # Full (5k sessions)
  python3 mamba-trail-optimize.py --quick  # Quick (2k sessions)
"""

import random
import sys
from itertools import product

CHANCE = 65
WIN_PROB = CHANCE / 100.0
WIN_PAYOUT = 99.0 / CHANCE - 1.0
IOL = 3.0
DIVIDER = 10000


def sim(bank, num, max_bets, seed, stop_pct, trail_activate, trail_lock):
    pnls = []
    busts = 0
    trail_exits = 0
    target_exits = 0
    total_bets = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base_bet = bank / DIVIDER
        mult = 1.0
        profit = 0.0
        peak = 0.0
        bets = 0
        trail_active = False

        stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
        activate_thresh = bank * trail_activate / 100 if trail_activate > 0 else 0

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            bet = base_bet * mult
            if bet > bal * 0.95:
                mult = 1.0
                bet = base_bet
            if bet > bal:
                bet = bal
            if bet < 0.001:
                busts += 1
                break

            bets += 1
            if random.random() < WIN_PROB:
                profit += bet * WIN_PAYOUT
                mult = 1.0
            else:
                profit -= bet
                mult *= IOL
                nb = base_bet * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

            # Trailing stop
            if trail_activate > 0:
                if not trail_active and profit >= activate_thresh:
                    trail_active = True
                if trail_active:
                    floor = peak * trail_lock / 100
                    if profit <= floor and mult <= 1.01:
                        trail_exits += 1
                        break

            # Fixed stop
            if stop_thresh > 0 and profit >= stop_thresh and mult <= 1.01:
                target_exits += 1
                break

        total_bets += bets
        pnls.append(profit)

    pnls.sort()
    n = len(pnls)
    return {
        'median': pnls[n // 2],
        'mean': sum(pnls) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n * 100,
        'p10': pnls[n // 10],
        'p90': pnls[9 * n // 10],
        'avg_bets': total_bets / n,
        'trail_exits': trail_exits,
        'target_exits': target_exits,
    }


def pr(tag, r, bl=None):
    m = " **" if bl is not None and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 10 / 60
    te = r['trail_exits']
    tg = r['target_exits']
    print(f"  {tag:<42} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} "
          f"{t:>4.1f}m T{te:>4}/S{tg:>4}{m}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    max_bets = 15000

    H = (f"  {'Config':<42} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} "
         f"{'Tm':>5} {'Trail/Stop':>10}")
    S = (f"  {'─'*42} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} "
         f"{'─'*5} {'─'*10}")

    print()
    print("=" * 125)
    print("  MAMBA v2 TRAILING STOP OPTIMIZER")
    print(f"  {num:,} sessions | D65 IOL3.0x div10000 | ${bank:,}")
    print("=" * 125)

    for stop in [0, 8, 10, 15, 20, 30]:
        print(f"\n  {'='*60}")
        print(f"  STOP = {stop}%" + (" (trailing-only)" if stop == 0 else ""))
        print(f"  {'='*60}")

        # Baseline (no trail)
        print(f"\n  --- Baseline (no trailing stop) ---")
        print(H); print(S)
        r_bl = sim(bank, num, max_bets, seed, stop, 0, 0)
        pr("No trail", r_bl)
        bl = r_bl['median']

        # Full sweep
        print(f"\n  --- Activate × Lock sweep ---")
        print(H); print(S)

        all_results = []
        for act in [1, 2, 3, 4, 5, 6, 8, 10]:
            for lock in [30, 40, 50, 60, 70, 80]:
                if stop > 0 and act >= stop:
                    continue  # activate must be below stop target
                tag = f"act={act}% lock={lock}%"
                r = sim(bank, num, max_bets, seed, stop, act, lock)
                r['tag'] = tag
                r['act'] = act
                r['lock'] = lock
                all_results.append(r)

        # Sort by composite score: median * (1 - bust_pct/100) — rewards high median + low bust
        for r in all_results:
            r['score'] = r['median'] * (1 - r['bust_pct'] / 100)

        by_score = sorted(all_results, key=lambda r: r['score'], reverse=True)

        print(f"\n  TOP 15 BY RISK-ADJUSTED SCORE (median × survival rate):")
        print(H); print(S)
        for r in by_score[:15]:
            pr(r['tag'] + f" [s={r['score']:.1f}]", r, bl)

        # Best by pure median
        by_med = sorted(all_results, key=lambda r: r['median'], reverse=True)
        print(f"\n  TOP 10 BY MEDIAN:")
        print(H); print(S)
        for r in by_med[:10]:
            pr(r['tag'], r, bl)

        # Best by bust rate (with positive median)
        positive = [r for r in all_results if r['median'] > 0]
        by_bust = sorted(positive, key=lambda r: r['bust_pct'])
        print(f"\n  TOP 10 LOWEST BUST (median > 0):")
        print(H); print(S)
        for r in by_bust[:10]:
            pr(r['tag'], r, bl)

        # Best by win rate
        by_win = sorted(all_results, key=lambda r: r['win_pct'], reverse=True)
        print(f"\n  TOP 5 HIGHEST WIN RATE:")
        print(H); print(S)
        for r in by_win[:5]:
            pr(r['tag'], r, bl)

    # ============================================================
    # GRAND SUMMARY
    # ============================================================
    print()
    print("=" * 125)
    print("  GRAND SUMMARY — Best trailing stop per stop level")
    print("=" * 125)
    print(f"\n  {'Stop%':<8} {'Best Config':<25} {'Median':>9} {'Bust%':>7} {'Win%':>7} {'Score':>8} {'vs Baseline':>12}")
    print(f"  {'─'*8} {'─'*25} {'─'*9} {'─'*7} {'─'*7} {'─'*8} {'─'*12}")

    for stop in [0, 8, 10, 15, 20, 30]:
        # Baseline
        r_bl = sim(bank, num, max_bets, seed, stop, 0, 0)
        bl_score = r_bl['median'] * (1 - r_bl['bust_pct'] / 100)

        # Find best
        best = None
        best_score = -999999
        for act in [1, 2, 3, 4, 5, 6, 8, 10]:
            for lock in [30, 40, 50, 60, 70, 80]:
                if stop > 0 and act >= stop:
                    continue
                r = sim(bank, num, max_bets, seed, stop, act, lock)
                score = r['median'] * (1 - r['bust_pct'] / 100)
                if score > best_score:
                    best_score = score
                    best = r
                    best['tag'] = f"act={act}% lock={lock}%"

        delta = best['median'] - r_bl['median']
        bust_delta = best['bust_pct'] - r_bl['bust_pct']
        stop_label = f"{stop}%" if stop > 0 else "none"
        print(f"  {stop_label:<8} {best['tag']:<25} ${best['median']:>+8.2f} {best['bust_pct']:>6.1f}% {best['win_pct']:>6.1f}% {best_score:>7.1f}  "
              f"med {'+' if delta >= 0 else ''}{delta:.2f} bust {'+' if bust_delta >= 0 else ''}{bust_delta:.1f}%")

    print()
    print("  RECOMMENDATION:")
    # Run the recommended configs one more time for clean output
    print(f"\n  {'Config':<50} {'Median':>9} {'Bust%':>7} {'Win%':>7}")
    print(f"  {'─'*50} {'─'*9} {'─'*7} {'─'*7}")
    for stop, act, lock, label in [
        (15, 3, 50, "RECOMMENDED: stop=15% act=3% lock=50%"),
        (15, 2, 50, "Alternative: stop=15% act=2% lock=50%"),
        (15, 3, 60, "Alternative: stop=15% act=3% lock=60%"),
        (20, 3, 50, "Aggressive: stop=20% act=3% lock=50%"),
        (20, 5, 50, "Aggressive: stop=20% act=5% lock=50%"),
        (10, 3, 50, "Conservative: stop=10% act=3% lock=50%"),
        (0, 3, 50, "Trail-only: no stop, act=3% lock=50%"),
        (0, 5, 60, "Trail-only: no stop, act=5% lock=60%"),
    ]:
        r = sim(bank, num, max_bets, seed, stop, act, lock)
        print(f"  {label:<50} ${r['median']:>+8.2f} {r['bust_pct']:>6.1f}% {r['win_pct']:>6.1f}%")
    print("=" * 125)
