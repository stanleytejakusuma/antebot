#!/usr/bin/env python3
"""
MAMBA Dice Optimizer — IOL profit strategy on dice
Sweeps chance × IOL × divider to find optimal config.
Compares vs COBRA roulette baseline.

Dice model: win at C/100 probability, payout = 99/C multiplier.
House edge: 1% always (regardless of chance).

Usage:
  python3 mamba-optimizer.py          # Full sweep (5k sessions)
  python3 mamba-optimizer.py --quick  # Quick (2k sessions)
"""

import random
import sys
import time
from itertools import product

# ============================================================
# DICE MODEL
# ============================================================

def dice_win(chance):
    """Returns True with probability chance/100."""
    return random.random() < chance / 100.0

def dice_payout(chance):
    """Net payout fraction on win: (99/chance - 1)."""
    return 99.0 / chance - 1.0


# ============================================================
# COBRA ROULETTE BASELINE (for comparison)
# ============================================================

COBRA_COVERED = 23
COBRA_WIN_FRAC = 36.0 / COBRA_COVERED - 1.0  # +0.565x
COBRA_WIN_PROB = COBRA_COVERED / 37.0  # 62.2%


# ============================================================
# SIMULATOR
# ============================================================

def sim_dice(chance, iol, divider, bank=1000, num=5000, max_bets=10000,
             seed=42, vault_pct=0, stop_total_pct=0, brake_at=0):
    """
    Simulate dice IOL strategy.
    Returns stats dict.
    """
    win_payout = dice_payout(chance)  # e.g., +0.523x at 65%
    win_prob = chance / 100.0

    profits = []
    busts = 0
    total_wagered_all = 0
    max_ls_seen = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base_bet = bank / divider
        current_mult = 1.0
        profit = 0.0
        wagered = 0.0
        vaulted = 0.0
        profit_at_vault = 0.0
        ls = 0
        max_ls = 0
        start_bal = bank
        is_braking = False

        vault_thresh = start_bal * vault_pct / 100 if vault_pct > 0 else 0
        stop_thresh = bank * stop_total_pct / 100 if stop_total_pct > 0 else 0

        for bet_num in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            total_bet = base_bet * current_mult
            if total_bet > bal * 0.95:
                # Soft bust: reset to base
                current_mult = 1.0
                total_bet = base_bet
                is_braking = False

            if total_bet > bal:
                total_bet = bal
            if total_bet < 0.001:
                busts += 1
                break

            wagered += total_bet

            # Dice roll
            if random.random() < win_prob:
                # Win
                profit += total_bet * win_payout
                ls = 0
                current_mult = 1.0
                is_braking = False
            else:
                # Loss
                profit -= total_bet
                ls += 1
                if ls > max_ls:
                    max_ls = ls

                if is_braking:
                    # Stay flat during brake
                    pass
                elif brake_at > 0 and ls >= brake_at:
                    # Activate brake: hold bet flat
                    is_braking = True
                else:
                    current_mult *= iol

            # Bust check
            if bank + profit <= 0:
                busts += 1
                break

            # Vault check
            if vault_thresh > 0 and current_mult <= 1.01 and not is_braking:
                current_profit = profit - profit_at_vault
                if current_profit >= vault_thresh:
                    vaulted += current_profit
                    profit_at_vault = profit
                    new_bal = bank + profit - vaulted
                    if new_bal > 0:
                        start_bal = new_bal
                        base_bet = start_bal / divider
                        vault_thresh = start_bal * vault_pct / 100

            # Stop check
            if stop_thresh > 0 and profit >= stop_thresh and current_mult <= 1.01:
                break

        if max_ls > max_ls_seen:
            max_ls_seen = max_ls
        total_wagered_all += wagered
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
        'max_ls': max_ls_seen,
        'avg_wager': total_wagered_all / n,
    }


def sim_cobra(divider, iol, bank=1000, num=5000, max_bets=5000, seed=42,
              vault_pct=0, stop_total_pct=0):
    """COBRA roulette baseline for comparison."""
    profits = []
    busts = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base_bet = bank / divider
        current_mult = 1.0
        profit = 0.0
        vaulted = 0.0
        profit_at_vault = 0.0
        start_bal = bank

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

            n = random.randint(0, 36)
            if n < COBRA_COVERED:
                profit += total_bet * COBRA_WIN_FRAC
                current_mult = 1.0
            else:
                profit -= total_bet
                current_mult *= iol

            if bank + profit <= 0:
                busts += 1
                break

            if vault_thresh > 0 and current_mult <= 1.01:
                cp = profit - profit_at_vault
                if cp >= vault_thresh:
                    vaulted += cp
                    profit_at_vault = profit
                    new_bal = bank + profit - vaulted
                    if new_bal > 0:
                        start_bal = new_bal
                        base_bet = start_bal / divider
                        vault_thresh = start_bal * vault_pct / 100

            if stop_thresh > 0 and profit >= stop_thresh and current_mult <= 1.01:
                break

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
    if baseline_med is not None and r['median'] > baseline_med:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    wgr = r.get('avg_wager', 0) / 1000
    mls = r.get('max_ls', 0)
    print(f"  {tag:<52} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f}"
          f"{f' {wgr:>5.1f}x' if wgr > 0 else ''}"
          f"{f' LS{mls:>2}' if mls > 0 else ''}{marker}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42

    hdr = (f"  {'Config':<52} {'Median':>9} {'Mean':>9} "
           f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Wgr':>6} {'MxLS':>4}")
    sep = (f"  {'─' * 52} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6} {'─' * 9} {'─' * 9} {'─' * 6} {'─' * 4}")

    print()
    print("=" * 120)
    print("  MAMBA DICE OPTIMIZER — IOL Profit on Dice")
    print(f"  {num:,} sessions x 10,000 bets | ${bank:,} bankroll")
    print("=" * 120)

    # ============================================================
    # SECTION 1: COBRA BASELINES
    # ============================================================
    print("\n  --- COBRA ROULETTE BASELINES ---")
    print(hdr); print(sep)

    cobra_configs = [(10000, 3.0), (10000, 2.5), (15000, 3.0)]
    cobra_baselines = {}
    for div, iol in cobra_configs:
        tag = f"COBRA div={div} IOL={iol}x (roulette, 5k spins)"
        r = sim_cobra(div, iol, bank, num, max_bets=5000, seed=seed)
        print_row(tag, r)
        cobra_baselines[(div, iol)] = r

    cobra_v5s10 = sim_cobra(10000, 3.0, bank, num, max_bets=5000, seed=seed,
                            vault_pct=5, stop_total_pct=10)
    print_row("COBRA div=10k IOL=3.0x v5/s10", cobra_v5s10)

    cobra_med = cobra_baselines[(10000, 3.0)]['median']

    # ============================================================
    # SECTION 2: CHANCE SWEEP (fixed IOL=3.0x, div=10000)
    # ============================================================
    print(f"\n  --- DICE CHANCE SWEEP (IOL=3.0x, div=10000, no vault) ---")
    print(hdr); print(sep)

    for chance in [40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]:
        wp = dice_payout(chance)
        tag = f"Dice {chance}% (payout +{wp:.3f}x)"
        r = sim_dice(chance, 3.0, 10000, bank, num, seed=seed)
        print_row(tag, r, cobra_med)

    # ============================================================
    # SECTION 3: IOL SWEEP at best chances
    # ============================================================
    print(f"\n  --- IOL SWEEP (div=10000, no vault) ---")
    print(hdr); print(sep)

    for chance in [55, 60, 65, 70, 75]:
        for iol in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
            tag = f"Dice {chance}% IOL={iol}x"
            r = sim_dice(chance, iol, 10000, bank, num, seed=seed)
            print_row(tag, r, cobra_med)
        print()

    # ============================================================
    # SECTION 4: DIVIDER SWEEP at promising configs
    # ============================================================
    print(f"\n  --- DIVIDER SWEEP (top configs, no vault) ---")
    print(hdr); print(sep)

    promising = [
        (60, 3.0), (65, 3.0), (65, 2.5), (70, 2.5), (70, 3.0), (75, 2.5),
    ]
    for chance, iol in promising:
        for div in [5000, 8000, 10000, 15000, 20000]:
            tag = f"Dice {chance}% IOL={iol}x div={div}"
            r = sim_dice(chance, iol, div, bank, num, seed=seed)
            print_row(tag, r, cobra_med)
        print()

    # ============================================================
    # SECTION 5: VAULT + STOP configs
    # ============================================================
    print(f"\n  --- VAULT + STOP (top configs) ---")
    print(hdr); print(sep)

    vault_configs = [
        (3, 0),   # vault 3%, no stop (grind)
        (5, 10),  # vault 5%, stop 10% (safe session)
        (3, 10),  # vault 3%, stop 10%
        (5, 20),  # vault 5%, stop 20%
    ]
    top_configs = [
        (60, 3.0, 10000), (65, 3.0, 10000), (65, 2.5, 10000),
        (70, 2.5, 10000), (70, 3.0, 10000), (65, 3.0, 8000),
    ]

    for chance, iol, div in top_configs:
        for vpct, spct in vault_configs:
            v_label = f"v{vpct}" if vpct > 0 else "nv"
            s_label = f"/s{spct}" if spct > 0 else ""
            tag = f"Dice {chance}% IOL={iol}x div={div} {v_label}{s_label}"
            r = sim_dice(chance, iol, div, bank, num, seed=seed,
                        vault_pct=vpct, stop_total_pct=spct)
            print_row(tag, r, cobra_med)
        print()

    # ============================================================
    # SECTION 6: BRAKE SWEEP
    # ============================================================
    print(f"\n  --- BRAKE SWEEP (VIPER-style coil) ---")
    print(hdr); print(sep)

    for chance, iol, div in [(65, 3.0, 10000), (70, 3.0, 10000), (60, 3.0, 10000)]:
        for brake in [0, 5, 6, 7, 8, 10]:
            b_label = f"brake@{brake}" if brake > 0 else "no-brake"
            tag = f"Dice {chance}% IOL={iol}x div={div} {b_label}"
            r = sim_dice(chance, iol, div, bank, num, seed=seed, brake_at=brake)
            print_row(tag, r, cobra_med)
        print()

    # ============================================================
    # SECTION 7: FULL SWEEP — Find absolute best
    # ============================================================
    print(f"\n  --- FULL SWEEP ---")
    t0 = time.time()
    all_results = []

    for chance, iol, div in product(
        [55, 60, 65, 70, 75, 80],
        [2.0, 2.5, 3.0, 3.5, 4.0],
        [5000, 8000, 10000, 15000, 20000],
    ):
        tag = f"D{chance} I{iol} d{div}"
        r = sim_dice(chance, iol, div, bank, num, seed=seed)
        r['tag'] = tag
        r['cfg'] = (chance, iol, div)
        all_results.append(r)

    elapsed = time.time() - t0
    print(f"  {len(all_results)} configs in {elapsed:.0f}s")

    # Top 20 by median
    by_med = sorted(all_results, key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 20 BY MEDIAN:")
    print(hdr); print(sep)
    for r in by_med[:20]:
        print_row(r['tag'], r, cobra_med)

    # Top 20 safe (bust < 15%)
    safe = [r for r in all_results if r['bust_pct'] < 15]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 20 BY MEDIAN (bust < 15%):")
    print(hdr); print(sep)
    for r in safe[:20]:
        print_row(r['tag'], r, cobra_med)

    # Top 20 very safe (bust < 5%)
    vsafe = [r for r in all_results if r['bust_pct'] < 5]
    vsafe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 10 BY MEDIAN (bust < 5%):")
    print(hdr); print(sep)
    for r in vsafe[:10]:
        print_row(r['tag'], r, cobra_med)

    # ============================================================
    # SECTION 8: BEST CONFIGS WITH VAULT
    # ============================================================
    print(f"\n  --- BEST CONFIGS + VAULT ---")
    print(hdr); print(sep)

    for r in by_med[:5]:
        chance, iol, div = r['cfg']
        # No vault
        print_row(f"D{chance} I{iol} d{div} (raw)", r, cobra_med)
        # v3 grind
        rv3 = sim_dice(chance, iol, div, bank, num, seed=seed,
                       vault_pct=3, stop_total_pct=0)
        print_row(f"D{chance} I{iol} d{div} v3/grind", rv3, cobra_med)
        # v5/s10
        rv5 = sim_dice(chance, iol, div, bank, num, seed=seed,
                       vault_pct=5, stop_total_pct=10)
        print_row(f"D{chance} I{iol} d{div} v5/s10", rv5, cobra_med)
        print()

    # ============================================================
    # SUMMARY
    # ============================================================
    best = by_med[0]
    best_safe = safe[0] if safe else by_med[0]

    print("=" * 120)
    print("  SUMMARY")
    print("=" * 120)
    print(f"\n  COBRA baseline (div=10k, IOL=3.0x): median ${cobra_med:+.2f} | bust {cobra_baselines[(10000,3.0)]['bust_pct']:.1f}%")
    print(f"  MAMBA best overall:  median ${best['median']:+.2f} | bust {best['bust_pct']:.1f}% | {best['tag']}")
    print(f"  MAMBA best safe:     median ${best_safe['median']:+.2f} | bust {best_safe['bust_pct']:.1f}% | {best_safe['tag']}")

    beats = best['median'] > cobra_med
    print(f"\n  VERDICT: MAMBA {'BEATS' if beats else 'does NOT beat'} COBRA by ${best['median'] - cobra_med:+.2f}")
    print(f"  Edge advantage: dice 1.0% vs roulette 2.7% = {(2.7-1.0)/2.7*100:.0f}% less house drain")

    # Speed-adjusted comparison
    # COBRA: ~5 bets/s, MAMBA: ~10 bets/s
    cobra_per_hour = cobra_med / (5000 / 5 / 3600)  # profit per hour
    mamba_per_hour = best['median'] / (10000 / 10 / 3600)
    print(f"\n  $/hour estimate (COBRA @5/s, MAMBA @10/s):")
    print(f"    COBRA: ${cobra_per_hour:+.2f}/hr")
    print(f"    MAMBA: ${mamba_per_hour:+.2f}/hr")
    print("=" * 120)
