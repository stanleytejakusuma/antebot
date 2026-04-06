#!/usr/bin/env python3
"""
MAMBA Vault/Stop Optimizer — Find best (vaultPct, stopTotalPct) pair
Tests the winning config D65/IOL3.0x/div10000 across vault+stop combos.

Usage:
  python3 mamba-vault-sweep.py          # Full (5k sessions)
  python3 mamba-vault-sweep.py --quick  # Quick (2k sessions)
"""

import random
import sys
import time
from itertools import product

# ============================================================
# DICE MODEL
# ============================================================

CHANCE = 65
WIN_PROB = CHANCE / 100.0
WIN_PAYOUT = 99.0 / CHANCE - 1.0  # +0.523x
IOL = 3.0
DIVIDER = 10000

def sim(bank, num, max_bets, seed, vault_pct, stop_total_pct):
    profits = []
    busts = 0
    total_vaulted_all = 0
    total_wagered_all = 0
    session_bets_all = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base_bet = bank / DIVIDER
        current_mult = 1.0
        profit = 0.0
        vaulted = 0.0
        profit_at_vault = 0.0
        start_bal = bank
        wagered = 0.0
        bets_played = 0

        vault_thresh = start_bal * vault_pct / 100 if vault_pct > 0 else 0
        stop_thresh = bank * stop_total_pct / 100 if stop_total_pct > 0 else 0

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            total_bet = base_bet * current_mult
            if total_bet > bal * 0.95:
                current_mult = 1.0
                total_bet = base_bet

            if total_bet > bal:
                total_bet = bal
            if total_bet < 0.001:
                busts += 1
                break

            wagered += total_bet
            bets_played += 1

            if random.random() < WIN_PROB:
                profit += total_bet * WIN_PAYOUT
                current_mult = 1.0
            else:
                profit -= total_bet
                current_mult *= IOL
                next_bet = base_bet * current_mult
                if next_bet > (bank + profit) * 0.95:
                    current_mult = 1.0

            if bank + profit <= 0:
                busts += 1
                break

            # Vault
            if vault_thresh > 0 and current_mult <= 1.01:
                cp = profit - profit_at_vault
                if cp >= vault_thresh:
                    vaulted += cp
                    profit_at_vault = profit
                    new_bal = bank + profit - vaulted
                    if new_bal > 0:
                        start_bal = new_bal
                        base_bet = start_bal / DIVIDER
                        vault_thresh = start_bal * vault_pct / 100

            # Stop
            if stop_thresh > 0 and profit >= stop_thresh and current_mult <= 1.01:
                break

        total_vaulted_all += vaulted
        total_wagered_all += wagered
        session_bets_all += bets_played
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
        'avg_vault': total_vaulted_all / n,
        'avg_wager': total_wagered_all / n,
        'avg_bets': session_bets_all / n,
    }


def print_row(tag, r, baseline_med=None):
    marker = ""
    if baseline_med is not None and r['median'] > baseline_med:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    wgr = r['avg_wager'] / 1000
    bets = r['avg_bets']
    # Estimate session time at 10 bets/s
    mins = bets / 10 / 60
    print(f"  {tag:<40} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} "
          f"{wgr:>5.1f}x {bets:>6.0f}b {mins:>5.1f}m{marker}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    max_bets = 50000  # cap at 50k to keep sim tractable

    hdr = (f"  {'Config':<40} {'Median':>9} {'Mean':>9} "
           f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} "
           f"{'Wgr':>6} {'Bets':>7} {'Time':>6}")
    sep = (f"  {'─' * 40} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 7} {'─' * 6}")

    print()
    print("=" * 125)
    print("  MAMBA VAULT/STOP OPTIMIZER — D65 IOL3.0x div10000")
    print(f"  {num:,} sessions x {max_bets:,} max bets | ${bank:,} bankroll | ~10 bets/s live")
    print("=" * 125)

    # ============================================================
    # SECTION 1: No vault, no stop (baseline)
    # ============================================================
    print("\n  --- BASELINE (no vault, no stop) ---")
    print(hdr); print(sep)
    r_raw = sim(bank, num, max_bets, seed, 0, 0)
    print_row("No vault, no stop", r_raw)
    raw_med = r_raw['median']

    # ============================================================
    # SECTION 2: Stop only (no vault)
    # ============================================================
    print(f"\n  --- STOP ONLY (no vault) ---")
    print(hdr); print(sep)

    for stop in [5, 8, 10, 15, 20, 25, 30, 50]:
        tag = f"stop={stop}%"
        r = sim(bank, num, max_bets, seed, 0, stop)
        print_row(tag, r, raw_med)

    # ============================================================
    # SECTION 3: Vault only (no stop)
    # ============================================================
    print(f"\n  --- VAULT ONLY (no stop) ---")
    print(hdr); print(sep)

    for vault in [1, 2, 3, 5, 8, 10, 15, 20]:
        tag = f"vault={vault}%"
        r = sim(bank, num, max_bets, seed, vault, 0)
        print_row(tag, r, raw_med)

    # ============================================================
    # SECTION 4: FULL SWEEP vault × stop
    # ============================================================
    print(f"\n  --- FULL SWEEP: vault × stop ---")

    all_results = []
    t0 = time.time()
    for vault_pct, stop_pct in product(
        [0, 1, 2, 3, 5, 8, 10],
        [0, 5, 8, 10, 15, 20, 25, 30, 50],
    ):
        if vault_pct == 0 and stop_pct == 0:
            continue
        tag = f"v{vault_pct}/s{stop_pct}" if stop_pct > 0 else f"v{vault_pct}/grind"
        if vault_pct == 0:
            tag = f"nv/s{stop_pct}"
        r = sim(bank, num, max_bets, seed, vault_pct, stop_pct)
        r['tag'] = tag
        r['vault_pct'] = vault_pct
        r['stop_pct'] = stop_pct
        all_results.append(r)

    elapsed = time.time() - t0
    print(f"  {len(all_results)} configs in {elapsed:.0f}s")

    # Top 20 by median
    by_med = sorted(all_results, key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 20 BY MEDIAN:")
    print(hdr); print(sep)
    for r in by_med[:20]:
        print_row(r['tag'], r, raw_med)

    # Top by win rate (bust < 10%)
    safe = [r for r in all_results if r['bust_pct'] < 10]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 15 BY MEDIAN (bust < 10%):")
    print(hdr); print(sep)
    for r in safe[:15]:
        print_row(r['tag'], r, raw_med)

    # Top by win rate (bust < 5%)
    vsafe = [r for r in all_results if r['bust_pct'] < 5]
    vsafe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 10 BY MEDIAN (bust < 5%):")
    print(hdr); print(sep)
    for r in vsafe[:10]:
        print_row(r['tag'], r, raw_med)

    # Best by $/hour (median / avg_minutes)
    print(f"\n  TOP 10 BY $/HOUR (median / session time):")
    print(hdr); print(sep)
    for_hour = [(r, r['median'] / max(r['avg_bets'] / 10 / 3600, 0.001)) for r in all_results if r['median'] > 0]
    for_hour.sort(key=lambda x: x[1], reverse=True)
    for r, dph in for_hour[:10]:
        tag = r['tag'] + f" (${dph:.0f}/hr)"
        print_row(tag, r, raw_med)

    # ============================================================
    # SECTION 5: RECOMMENDED CONFIGS
    # ============================================================
    print(f"\n  --- RECOMMENDED CONFIGS (repeat with different dividers) ---")
    print(hdr); print(sep)

    # Take top 3 vault/stop combos and test at different dividers
    best_combos = []
    seen = set()
    for r in by_med:
        key = (r['vault_pct'], r['stop_pct'])
        if key not in seen and r['bust_pct'] < 15:
            seen.add(key)
            best_combos.append(key)
            if len(best_combos) >= 4:
                break

    for vpct, spct in best_combos:
        for div in [8000, 10000, 15000, 20000]:
            old_div = DIVIDER
            tag = f"v{vpct}/s{spct} div={div}"
            # Inline sim with different divider
            profits = []
            busts_count = 0
            total_w = 0
            total_b = 0
            for s in range(num):
                random.seed(seed * 100000 + s)
                base_bet = bank / div
                current_mult = 1.0
                profit = 0.0
                vaulted = 0.0
                profit_at_vault = 0.0
                start_bal = bank
                wagered = 0.0
                bets_count = 0
                vault_thresh = start_bal * vpct / 100 if vpct > 0 else 0
                stop_thresh = bank * spct / 100 if spct > 0 else 0

                for _ in range(max_bets):
                    bal = bank + profit
                    if bal <= 0:
                        busts_count += 1
                        break
                    tb = base_bet * current_mult
                    if tb > bal * 0.95:
                        current_mult = 1.0
                        tb = base_bet
                    if tb > bal: tb = bal
                    if tb < 0.001:
                        busts_count += 1
                        break
                    wagered += tb
                    bets_count += 1
                    if random.random() < WIN_PROB:
                        profit += tb * WIN_PAYOUT
                        current_mult = 1.0
                    else:
                        profit -= tb
                        current_mult *= IOL
                        nb = base_bet * current_mult
                        if nb > (bank + profit) * 0.95:
                            current_mult = 1.0
                    if bank + profit <= 0:
                        busts_count += 1
                        break
                    if vault_thresh > 0 and current_mult <= 1.01:
                        cp = profit - profit_at_vault
                        if cp >= vault_thresh:
                            vaulted += cp
                            profit_at_vault = profit
                            new_bal = bank + profit - vaulted
                            if new_bal > 0:
                                start_bal = new_bal
                                base_bet = start_bal / div
                                vault_thresh = start_bal * vpct / 100
                    if stop_thresh > 0 and profit >= stop_thresh and current_mult <= 1.01:
                        break
                total_w += wagered
                total_b += bets_count
                profits.append(profit)

            profits.sort()
            n = len(profits)
            rr = {
                'median': profits[n // 2],
                'mean': sum(profits) / n,
                'bust_pct': busts_count / n * 100,
                'win_pct': sum(1 for p in profits if p > 0) / n * 100,
                'p10': profits[n // 10],
                'p90': profits[9 * n // 10],
                'avg_wager': total_w / n,
                'avg_bets': total_b / n,
            }
            print_row(tag, rr, raw_med)
        print()

    # ============================================================
    # SUMMARY
    # ============================================================
    best = by_med[0]
    best_safe = safe[0] if safe else by_med[0]
    best_vsafe = vsafe[0] if vsafe else by_med[0]

    print("=" * 125)
    print("  SUMMARY — Best (vaultPct, stopTotalPct) for MAMBA D65/IOL3.0x/div10000")
    print("=" * 125)
    print(f"\n  Raw baseline (no v/s):  median ${raw_med:+.2f} | bust {r_raw['bust_pct']:.1f}% | {r_raw['avg_bets']:.0f} bets")
    print(f"  Best overall:           median ${best['median']:+.2f} | bust {best['bust_pct']:.1f}% | win {best['win_pct']:.1f}% | {best['tag']}")
    print(f"  Best safe (<10% bust):  median ${best_safe['median']:+.2f} | bust {best_safe['bust_pct']:.1f}% | win {best_safe['win_pct']:.1f}% | {best_safe['tag']}")
    print(f"  Best v.safe (<5% bust): median ${best_vsafe['median']:+.2f} | bust {best_vsafe['bust_pct']:.1f}% | win {best_vsafe['win_pct']:.1f}% | {best_vsafe['tag']}")

    # $/hour champions
    if for_hour:
        hr_tag, hr_dph = for_hour[0][0]['tag'], for_hour[0][1]
        print(f"  Best $/hour:            ${hr_dph:.0f}/hr | {for_hour[0][0]['tag']}")
    print("=" * 125)
