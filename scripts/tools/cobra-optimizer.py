#!/usr/bin/env python3
"""
COBRA Roulette Optimizer — Strike/Coil/Capitalize on Profit R/B coverage
Sweeps brake, capitalize, IOL params. Compares vs baseline Profit R/B.

Usage:
  python3 cobra-optimizer.py          # Full sweep
  python3 cobra-optimizer.py --quick  # Quick 2000 sessions
"""

import random
import sys
import time
from itertools import product

# ============================================================
# ROULETTE MODEL — Profit R/B coverage
# ============================================================

UNCOVERED = {0, 4, 9, 12, 13, 21, 25, 36}
SMALL = {1, 16, 24, 31, 33}
# Big = 1-36 minus uncovered minus small = 24 numbers

def spin_payout(n):
    """Returns net payout as fraction of total bet."""
    if n in UNCOVERED:
        return -1.0
    elif n in SMALL:
        return -0.72
    else:
        return 0.44

# ============================================================
# STRATEGIES
# ============================================================

class ProfitRB:
    """Baseline: Profit R/B with IOL, no brake, no capitalize."""
    def __init__(self, base, iol=3.5):
        self.base = base
        self.iol = iol
        self.bet = base
    def update(self, payout):
        if payout > 0:
            self.bet = self.base
        else:
            self.bet *= self.iol

class Cobra:
    """COBRA: Strike (IOL) + Coil (brake) + Capitalize (Paroli on streaks)."""
    def __init__(self, base, iol=3.5, brake_at=6, cap_streak=3, cap_max=2):
        self.base = base
        self.iol = iol
        self.brake_at = brake_at
        self.cap_streak = cap_streak
        self.cap_max = cap_max
        self.bet = base
        self.mode = 'strike'
        self.ls = 0
        self.ws = 0
        self.cap_count = 0
        # Counters
        self.strike_spins = 0
        self.coil_spins = 0
        self.cap_spins = 0
        self.coil_activations = 0

    def update(self, payout):
        is_win = payout > 0

        if is_win:
            self.ws += 1
            self.ls = 0
        else:
            self.ws = 0
            self.ls += 1

        prev = self.mode

        if self.mode == 'strike':
            self.strike_spins += 1
            if is_win:
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'cap'
                    self.cap_count = 0
                    self.bet = self.base * 2
            else:
                if self.brake_at > 0 and self.ls >= self.brake_at:
                    self.mode = 'coil'
                    self.coil_activations += 1
                else:
                    self.bet *= self.iol

        elif self.mode == 'coil':
            self.coil_spins += 1
            if is_win:
                self.mode = 'strike'
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'cap'
                    self.cap_count = 0
                    self.bet = self.base * 2

        elif self.mode == 'cap':
            self.cap_spins += 1
            self.cap_count += 1
            if not is_win or self.cap_count >= self.cap_max:
                self.mode = 'strike'
                self.ws = 0
                self.bet = self.base
            elif is_win:
                self.bet = min(self.bet * 2, self.base * 100)

        self.bet = max(self.base, self.bet)


# ============================================================
# SIMULATOR
# ============================================================

def sim(tag, strat_fn, num=5000, max_spins=2000, bank=1000, seed=42):
    profits, busts = [], 0
    for s in range(num):
        random.seed(seed * 100000 + s)
        st = strat_fn()
        profit = 0.0
        for _ in range(max_spins):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break
            bet = min(st.bet, bal)
            if bet <= 0:
                busts += 1
                break
            n = random.randint(0, 36)
            payout = spin_payout(n)
            profit += bet * payout
            if bank + profit <= 0:
                busts += 1
                break
            st.update(payout)
        profits.append(profit)
    profits.sort()
    n = len(profits)
    return {
        'median': profits[n // 2],
        'mean': sum(profits) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in profits if p > 0) / n * 100,
        'p10': profits[n // 10],
        'p90': profits[9 * n // 10],
    }

def print_row(tag, r, baseline_med=None):
    marker = ""
    if baseline_med and r['median'] > baseline_med:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    print(f"  {tag:<48} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} {r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% ${r['p10']:>+8.2f} ${r['p90']:>+8.2f}{marker}")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42

    hdr = f"  {'Config':<48} {'Median':>9} {'Mean':>9} {'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9}"
    sep = f"  {'─'*48} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9}"

    print()
    print("=" * 105)
    print("  COBRA ROULETTE OPTIMIZER")
    print(f"  {num:,} sessions x 2,000 spins | ${bank:,} bankroll")
    print("=" * 105)

    # === BASELINES ===
    print("\n  --- BASELINES (Profit R/B) ---")
    print(hdr); print(sep)

    baselines = {}
    for div in [2574, 9008, 31526]:
        r = sim(f"R/B div={div} IOL=3.5x", lambda d=div: ProfitRB(bank / d, 3.5), num)
        print_row(f"Profit R/B div={div} IOL=3.5x", r)
        baselines[div] = r

    rb_med = baselines[9008]['median']

    # === IOL MULTIPLIER SWEEP ===
    print(f"\n  --- IOL MULTIPLIER (div=9008, no brake, no cap) ---")
    print(hdr); print(sep)

    for iol in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        r = sim(f"R/B IOL={iol}x", lambda i=iol: ProfitRB(bank / 9008, i), num)
        print_row(f"R/B div=9008 IOL={iol}x", r, rb_med)

    # === BRAKE SWEEP (COIL only, no capitalize) ===
    print(f"\n  --- BRAKE THRESHOLD (IOL=3.5x, no capitalize) ---")
    print(hdr); print(sep)

    for div in [9008]:
        for ba in [3, 4, 5, 6, 7, 0]:
            label = f"off" if ba == 0 else f"{ba}"
            r = sim(f"COBRA brake@{label} div={div}", lambda d=div, b=ba: Cobra(bank / d, 3.5, b, 99, 0), num)
            print_row(f"COBRA brake@{label} div={div} (no cap)", r, rb_med)

    # === CAPITALIZE SWEEP (no brake) ===
    print(f"\n  --- CAPITALIZE (IOL=3.5x, no brake) ---")
    print(hdr); print(sep)

    for cs, cm in [(2, 1), (2, 2), (3, 1), (3, 2), (3, 3), (4, 2)]:
        r = sim(f"COBRA cap s{cs}/c{cm}", lambda s=cs, m=cm: Cobra(bank / 9008, 3.5, 0, s, m), num)
        print_row(f"COBRA cap s{cs}/c{cm} div=9008 (no brake)", r, rb_med)

    # === FULL SWEEP: BRAKE x CAPITALIZE ===
    print(f"\n  --- FULL SWEEP: BRAKE x CAPITALIZE (IOL=3.5x, div=9008) ---")
    print(hdr); print(sep)

    results = []
    t0 = time.time()
    configs = []
    for ba, cs, cm, iol, div in product(
        [4, 5, 6, 7, 0],       # brake_at (0=off)
        [2, 3, 4],              # cap_streak
        [1, 2, 3],              # cap_max
        [3.0, 3.5, 4.0],        # IOL
        [9008],                  # divider
    ):
        configs.append((ba, cs, cm, iol, div))

    for idx, (ba, cs, cm, iol, div) in enumerate(configs):
        if idx % 20 == 0 and idx > 0:
            elapsed = time.time() - t0
            print(f"\r  Config {idx}/{len(configs)} ({elapsed:.0f}s)   ", end='', flush=True)

        tag = f"b{ba if ba > 0 else 'X'} s{cs}/c{cm} iol{iol} d{div}"
        r = sim(tag, lambda b=ba, s=cs, m=cm, i=iol, d=div: Cobra(bank / d, i, b, s, m), num)
        r['tag'] = tag
        r['cfg'] = (ba, cs, cm, iol, div)
        results.append(r)

    elapsed = time.time() - t0
    print(f"\r  Done: {len(configs)} configs in {elapsed:.0f}s" + " " * 30)

    # Top 20 by median
    by_med = sorted(results, key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 20 BY MEDIAN:")
    print(hdr); print(sep)
    for r in by_med[:20]:
        print_row(r['tag'], r, rb_med)

    # Top 20 by median with bust < 10%
    safe = [r for r in results if r['bust_pct'] < 10]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 20 BY MEDIAN (bust < 10%):")
    print(hdr); print(sep)
    for r in safe[:20]:
        print_row(r['tag'], r, rb_med)

    # === BEST CONFIGS ACROSS DIVIDERS ===
    print(f"\n  --- BEST COBRA vs R/B ACROSS DIVIDERS ---")
    print(hdr); print(sep)

    # Find best config
    best = by_med[0]
    ba, cs, cm, iol, _ = best['cfg']

    for div in [2574, 9008, 31526]:
        r_rb = sim(f"R/B div={div}", lambda d=div: ProfitRB(bank / d, 3.5), num)
        r_co = sim(f"COBRA best div={div}", lambda d=div, b=ba, s=cs, m=cm, i=iol: Cobra(bank / d, i, b, s, m), num)
        print_row(f"Profit R/B div={div}", r_rb)
        print_row(f"COBRA ({best['tag']}) div={div}", r_co, r_rb['median'])
        print()

    # === SUMMARY ===
    best_overall = by_med[0]
    best_safe = safe[0] if safe else by_med[0]

    print("=" * 105)
    print("  SUMMARY")
    print("=" * 105)
    print(f"\n  Profit R/B baseline (div=9008):  median ${rb_med:+.2f} | bust {baselines[9008]['bust_pct']:.1f}%")
    print(f"  COBRA best overall:             median ${best_overall['median']:+.2f} | bust {best_overall['bust_pct']:.1f}% | {best_overall['tag']}")
    print(f"  COBRA best safe (<10% bust):    median ${best_safe['median']:+.2f} | bust {best_safe['bust_pct']:.1f}% | {best_safe['tag']}")

    beats = best_overall['median'] > rb_med
    print(f"\n  VERDICT: COBRA {'BEATS' if beats else 'does NOT beat'} Profit R/B by ${best_overall['median'] - rb_med:+.2f}")
    print("=" * 105)
