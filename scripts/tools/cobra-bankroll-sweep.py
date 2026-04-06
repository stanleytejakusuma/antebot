#!/usr/bin/env python3
"""
COBRA v4 Bankroll Optimizer — Pure 23-number equal-weight coverage
Sweeps divider + IOL for multiple bankroll sizes.

COBRA v4 payout model:
  - 23 numbers covered (18 color + 5 extra), equal bet per number
  - Win (23/37): payout = 36 * (totalBet/23) - totalBet = +0.565x totalBet
  - Miss (14/37): payout = -1.0x totalBet

Usage:
  python3 cobra-bankroll-sweep.py          # Full sweep (5k sessions)
  python3 cobra-bankroll-sweep.py --quick  # Quick (2k sessions)
"""

import random
import sys
import time
from itertools import product

# ============================================================
# COBRA v4 PAYOUT MODEL — Pure 23-number bets
# ============================================================

COVERED_COUNT = 23
WIN_FRACTION = 36.0 / COVERED_COUNT - 1.0  # +0.5652x

def spin_result():
    """Returns net payout as fraction of total bet."""
    n = random.randint(0, 36)
    if n < COVERED_COUNT:
        # Simplification: 23/37 chance of hitting any covered number
        # Actual: specific numbers, but probability is identical
        return WIN_FRACTION  # +0.565x
    else:
        return -1.0

# More accurate: use actual number set
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
EXTRA = {2, 4, 6, 8, 10}
COVERED = RED | EXTRA  # 23 numbers

def spin_result_accurate():
    """Accurate model using actual number set."""
    n = random.randint(0, 36)
    if n in COVERED:
        return WIN_FRACTION
    else:
        return -1.0


# ============================================================
# SIMULATOR
# ============================================================

def sim_cobra(bank, divider, iol, num_sessions=5000, max_spins=5000, seed=42,
              vault_pct=0, stop_total_pct=0):
    """
    Simulate COBRA v4: pure IOL on 23-number coverage.
    Returns stats dict.
    """
    profits = []
    busts = 0
    total_vaulted_all = 0
    max_ls_seen = 0

    for s in range(num_sessions):
        random.seed(seed * 100000 + s)

        base_bet = bank / divider
        current_mult = 1.0
        profit = 0.0
        vaulted = 0.0
        profit_at_last_vault = 0.0
        ls = 0
        max_ls = 0

        vault_thresh = bank * vault_pct / 100 if vault_pct > 0 else 0
        stop_thresh = bank * stop_total_pct / 100 if stop_total_pct > 0 else 0

        for spin in range(max_spins):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            total_bet = base_bet * current_mult
            if total_bet > bal:
                total_bet = bal  # all-in

            if total_bet < 0.001:
                busts += 1
                break

            n = random.randint(0, 36)
            if n in COVERED:
                payout_net = total_bet * WIN_FRACTION
                profit += payout_net
                ls = 0
                current_mult = 1.0
            else:
                profit -= total_bet
                ls += 1
                if ls > max_ls:
                    max_ls = ls
                current_mult *= iol

            # Vault check
            if vault_thresh > 0 and current_mult <= 1.01:
                current_profit = profit - profit_at_last_vault
                if current_profit >= vault_thresh:
                    vaulted += current_profit
                    profit_at_last_vault = profit
                    # Adaptive rebase
                    new_bank = bank + profit - vaulted
                    # Don't rebase if it would make bank negative
                    if new_bank > 0:
                        base_bet = new_bank / divider

            # Stop check
            if stop_thresh > 0 and profit >= stop_thresh and current_mult <= 1.01:
                break

            # Bust check
            if bank + profit <= 0:
                busts += 1
                break

        if max_ls > max_ls_seen:
            max_ls_seen = max_ls
        total_vaulted_all += vaulted
        profits.append(profit)

    profits.sort()
    n = len(profits)
    return {
        'median': profits[n // 2],
        'mean': sum(profits) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in profits if p > 0) / n * 100,
        'p10': profits[n // 10],
        'p25': profits[n // 4],
        'p75': profits[3 * n // 4],
        'p90': profits[9 * n // 10],
        'max_ls': max_ls_seen,
        'avg_vault': total_vaulted_all / n,
    }


def print_row(tag, r, baseline_med=None):
    marker = ""
    if baseline_med is not None and r['median'] > baseline_med:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    print(f"  {tag:<45} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} LS{r['max_ls']:>2}{marker}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    seed = 42

    hdr = (f"  {'Config':<45} {'Median':>9} {'Mean':>9} "
           f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'MxLS':>4}")
    sep = (f"  {'─' * 45} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6} {'─' * 9} {'─' * 9} {'─' * 4}")

    print()
    print("=" * 110)
    print("  COBRA v4 BANKROLL OPTIMIZER — Pure 23-Number Coverage")
    print(f"  {num:,} sessions x 5,000 spins | Win: +{WIN_FRACTION*100:.1f}% | Coverage: 23/37 (62.2%)")
    print("=" * 110)

    # ============================================================
    # SECTION 1: $50 BANKROLL — Find optimal div/IOL
    # ============================================================

    for bankroll in [50, 100, 250, 1000]:
        print(f"\n  === BANKROLL: ${bankroll} ===")

        # --- IOL x DIVIDER sweep ---
        print(f"\n  --- IOL x DIVIDER (no vault, no stop) ---")
        print(hdr); print(sep)

        results = []
        for iol, div in product(
            [2.0, 2.5, 3.0, 3.5, 4.0, 5.0],
            [5000, 8000, 10000, 15000, 20000, 31526],
        ):
            tag = f"${bankroll} div={div:>5} IOL={iol}x"
            r = sim_cobra(bankroll, div, iol, num)
            r['iol'] = iol
            r['div'] = div
            results.append((tag, r))

        # Sort by median descending
        results.sort(key=lambda x: x[1]['median'], reverse=True)
        for tag, r in results[:15]:
            print_row(tag, r)

        # --- Best config WITH vault ---
        if bankroll <= 100:
            print(f"\n  --- TOP 5 WITH VAULT (vault=10%, stop=20%) ---")
            print(hdr); print(sep)

            # Take top 5 configs and add vault
            for tag, r in results[:5]:
                iol = r['iol']
                div = r['div']
                tag_v = f"${bankroll} d={div} IOL={iol}x +vault"
                rv = sim_cobra(bankroll, div, iol, num, vault_pct=10, stop_total_pct=20)
                print_row(tag_v, rv, r['median'])

            print(f"\n  --- TOP 5 WITH VAULT (vault=5%, stop=10%) ---")
            print(hdr); print(sep)

            for tag, r in results[:5]:
                iol = r['iol']
                div = r['div']
                tag_v = f"${bankroll} d={div} IOL={iol}x +vault"
                rv = sim_cobra(bankroll, div, iol, num, vault_pct=5, stop_total_pct=10)
                print_row(tag_v, rv, r['median'])

    # ============================================================
    # SECTION 2: SURVIVABILITY ANALYSIS
    # ============================================================

    print(f"\n  === SURVIVABILITY: Max Loss Streak Before Bust ===")
    print(f"  {'Config':<45} {'MaxLS':>6} {'Cumulative Cost':>16} {'% of Bank':>10}")
    print(f"  {'─' * 45} {'─' * 6} {'─' * 16} {'─' * 10}")

    for bankroll in [50, 100, 250, 1000]:
        for div in [5000, 10000, 20000]:
            for iol in [2.0, 3.0, 4.0]:
                base = bankroll / div
                cumulative = 0
                streak = 0
                bet = base
                while cumulative + bet <= bankroll:
                    cumulative += bet
                    streak += 1
                    bet *= iol
                pct = cumulative / bankroll * 100
                tag = f"${bankroll} div={div} IOL={iol}x"
                print(f"  {tag:<45} {streak:>6} ${cumulative:>14.4f} {pct:>9.1f}%")
        print()

    # ============================================================
    # SECTION 3: RECOMMENDED CONFIGS
    # ============================================================

    print("=" * 110)
    print("  RECOMMENDED CONFIGS BY BANKROLL")
    print("=" * 110)

    for bankroll, configs in [
        (50,   [(5000, 2.0), (5000, 2.5), (8000, 2.5), (10000, 3.0), (8000, 3.0)]),
        (100,  [(5000, 2.5), (8000, 3.0), (10000, 3.0), (10000, 2.5), (15000, 3.0)]),
        (250,  [(8000, 3.0), (10000, 3.0), (10000, 2.5), (15000, 3.5)]),
        (1000, [(10000, 3.0), (10000, 3.5), (15000, 3.0), (20000, 3.5)]),
    ]:
        print(f"\n  ${bankroll} bankroll:")
        print(hdr); print(sep)
        for div, iol in configs:
            tag = f"div={div} IOL={iol}x"
            r = sim_cobra(bankroll, div, iol, num)
            print_row(tag, r)
        # With vault
        print(f"  + vault configs:")
        for div, iol in configs[:2]:
            tag = f"div={div} IOL={iol}x +v5/s10"
            r = sim_cobra(bankroll, div, iol, num, vault_pct=5, stop_total_pct=10)
            print_row(tag, r)

    print()
    print("=" * 110)
