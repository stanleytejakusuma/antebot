#!/usr/bin/env python3
"""
MAMBA v2.0.1 Trail Optimizer — FIXED (no multiplier gate on trail)
The trailing stop fires immediately when profit < floor, even mid-IOL.
"""

import random
import sys
from itertools import product

CHANCE = 65
WIN_PROB = CHANCE / 100.0
WIN_PAYOUT = 99.0 / CHANCE - 1.0
IOL = 3.0
DIVIDER = 10000


def sim(bank, num, max_bets, seed, stop_pct, trail_act, trail_lock):
    pnls = []
    busts = 0
    trail_exits = 0
    target_exits = 0
    total_bets = 0
    # Track trail exit P&L for analysis
    trail_pnls = []

    for s in range(num):
        random.seed(seed * 100000 + s)

        base = bank / DIVIDER
        mult = 1.0
        profit = 0.0
        peak = 0.0
        bets = 0
        trail_active = False
        exited_trail = False

        stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
        act_thresh = bank * trail_act / 100 if trail_act > 0 else 0

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            bet = base * mult
            if bet > bal * 0.95:
                mult = 1.0
                bet = base
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
                nb = base * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

            # TRAILING STOP — NO MULTIPLIER GATE (v2.0.1 fix)
            if trail_act > 0:
                if not trail_active and profit >= act_thresh:
                    trail_active = True
                if trail_active:
                    floor = peak * trail_lock / 100
                    if profit <= floor:
                        trail_exits += 1
                        exited_trail = True
                        trail_pnls.append(profit)
                        break

            # Fixed stop (still gated by multiplier for clean exit)
            if stop_thresh > 0 and profit >= stop_thresh and mult <= 1.01:
                target_exits += 1
                break

        total_bets += bets
        pnls.append(profit)

    pnls.sort()
    n = len(pnls)
    avg_trail_pnl = sum(trail_pnls) / len(trail_pnls) if trail_pnls else 0
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
        'avg_trail_pnl': avg_trail_pnl,
    }


def pr(tag, r, bl=None):
    m = " **" if bl is not None and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 10 / 60
    te = r['trail_exits']
    tg = r['target_exits']
    atp = r.get('avg_trail_pnl', 0)
    trail_info = f"T{te:>4}/S{tg:>4}" + (f" avg${atp:>+.0f}" if te > 0 else "")
    print(f"  {tag:<42} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} "
          f"{t:>4.1f}m {trail_info}{m}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    max_bets = 15000

    H = (f"  {'Config':<42} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} "
         f"{'Tm':>5} {'Exits':>20}")
    S = (f"  {'─'*42} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} "
         f"{'─'*5} {'─'*20}")

    print()
    print("=" * 130)
    print("  MAMBA v2.0.1 TRAIL OPTIMIZER — NO MULTIPLIER GATE")
    print(f"  {num:,} sessions | D65 IOL3.0x div10000 | ${bank:,}")
    print("  Trail fires immediately when profit < floor (even mid-IOL)")
    print("=" * 130)

    for stop in [10, 15, 20, 30]:
        print(f"\n  {'='*60}")
        print(f"  STOP = {stop}%")
        print(f"  {'='*60}")

        # Baseline
        print(f"\n  --- Baseline ---")
        print(H); print(S)
        r_bl = sim(bank, num, max_bets, seed, stop, 0, 0)
        pr("No trail", r_bl)
        bl = r_bl['median']

        # Full sweep
        all_r = []
        for act in [1, 2, 3, 4, 5, 8]:
            for lock in [30, 40, 50, 60, 70, 80]:
                if act >= stop:
                    continue
                tag = f"act={act}% lock={lock}%"
                r = sim(bank, num, max_bets, seed, stop, act, lock)
                r['tag'] = tag
                r['act'] = act
                r['lock'] = lock
                r['score'] = r['median'] * (1 - r['bust_pct'] / 100)
                all_r.append(r)

        by_score = sorted(all_r, key=lambda r: r['score'], reverse=True)
        print(f"\n  TOP 15 BY SCORE (median × survival):")
        print(H); print(S)
        for r in by_score[:15]:
            pr(r['tag'] + f" [s={r['score']:.0f}]", r, bl)

        # Show how lock% now differentiates at same activate%
        for act in [2, 3, 5]:
            if act >= stop:
                continue
            subset = [r for r in all_r if r['act'] == act]
            if subset:
                print(f"\n  Lock% comparison at activate={act}%:")
                print(H); print(S)
                for r in sorted(subset, key=lambda r: r['lock']):
                    pr(r['tag'], r, bl)

    # ============================================================
    # TRAILING-ONLY (no fixed stop)
    # ============================================================
    print(f"\n  {'='*60}")
    print(f"  TRAILING-ONLY (no fixed stop)")
    print(f"  {'='*60}")
    print(H); print(S)

    r_bl = sim(bank, num, max_bets, seed, 0, 0, 0)
    pr("No trail, no stop", r_bl)

    for act in [1, 2, 3, 5]:
        for lock in [30, 40, 50, 60, 70, 80]:
            tag = f"trail-only act={act}% lock={lock}%"
            r = sim(bank, num, max_bets, seed, 0, act, lock)
            pr(tag, r)

    # ============================================================
    # SUMMARY
    # ============================================================
    print()
    print("=" * 130)
    print("  OPTIMAL TRAILING STOP CONFIG")
    print("=" * 130)
    print(f"\n  {'Stop%':<8} {'Best Config':<30} {'Median':>9} {'Bust%':>7} {'Win%':>7} {'AvgTrailP&L':>12} {'vs NoBust':>10}")
    print(f"  {'─'*8} {'─'*30} {'─'*9} {'─'*7} {'─'*7} {'─'*12} {'─'*10}")

    for stop in [10, 15, 20, 30, 0]:
        bl_r = sim(bank, num, max_bets, seed, stop, 0, 0)
        best = None
        best_score = -999999
        for act in [1, 2, 3, 4, 5, 8]:
            for lock in [30, 40, 50, 60, 70, 80]:
                if stop > 0 and act >= stop:
                    continue
                r = sim(bank, num, max_bets, seed, stop, act, lock)
                score = r['median'] * (1 - r['bust_pct'] / 100)
                if score > best_score:
                    best_score = score
                    best = r
                    best['tag'] = f"act={act}% lock={lock}%"
        bust_delta = best['bust_pct'] - bl_r['bust_pct']
        label = f"{stop}%" if stop > 0 else "none"
        print(f"  {label:<8} {best['tag']:<30} ${best['median']:>+8.2f} {best['bust_pct']:>6.1f}% {best['win_pct']:>6.1f}% ${best['avg_trail_pnl']:>+10.2f}  bust {bust_delta:>+.1f}%")
    print("=" * 130)
