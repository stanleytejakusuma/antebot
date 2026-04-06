#!/usr/bin/env python3
"""
MAMBA Vault Optimizer — FIXED balance tracking
Previous sim had a bug: vault didn't reduce available balance.
This version correctly tracks actual_balance = bank + profit - vaulted.

Reports TOTAL ASSETS (balance + vault) as the key metric.
"""

import random
import sys
import time
from itertools import product

CHANCE = 65
WIN_PROB = CHANCE / 100.0
WIN_PAYOUT = 99.0 / CHANCE - 1.0
IOL = 3.0
DIVIDER = 10000


def sim(bank, num, max_bets, seed, vault_pct, stop_total_pct):
    results = []
    busts = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base_bet = bank / DIVIDER
        current_mult = 1.0
        profit = 0.0          # cumulative P&L (never changes on vault)
        vaulted = 0.0         # total extracted to vault
        profit_at_vault = 0.0
        start_bal = bank
        bets_played = 0

        # Vault threshold based on current start_bal (rebases after vault)
        vault_thresh = start_bal * vault_pct / 100 if vault_pct > 0 else 0
        # Stop based on ORIGINAL bank (fixed, doesn't rebase)
        stop_thresh = bank * stop_total_pct / 100 if stop_total_pct > 0 else 0

        for _ in range(max_bets):
            # ACTUAL balance = bank + profit - vaulted
            actual_bal = bank + profit - vaulted

            if actual_bal <= 0:
                busts += 1
                break

            total_bet = base_bet * current_mult

            # Soft bust: if bet exceeds 95% of ACTUAL balance
            if total_bet > actual_bal * 0.95:
                current_mult = 1.0
                total_bet = base_bet

            # Cap bet to actual balance
            if total_bet > actual_bal:
                total_bet = actual_bal
            if total_bet < 0.001:
                busts += 1
                break

            bets_played += 1

            # Dice roll
            if random.random() < WIN_PROB:
                profit += total_bet * WIN_PAYOUT
                current_mult = 1.0
            else:
                profit -= total_bet
                current_mult *= IOL
                # Pre-check next bet for soft bust
                next_bet = base_bet * current_mult
                actual_after = bank + profit - vaulted
                if actual_after > 0 and next_bet > actual_after * 0.95:
                    current_mult = 1.0

            # Bust check on actual balance
            actual_bal = bank + profit - vaulted
            if actual_bal <= 0:
                busts += 1
                break

            # Vault check
            if vault_thresh > 0 and current_mult <= 1.01:
                current_profit = profit - profit_at_vault
                if current_profit >= vault_thresh:
                    vault_amount = current_profit
                    vaulted += vault_amount
                    profit_at_vault = profit
                    # Adaptive rebase: new start_bal = actual balance after vault
                    actual_bal = bank + profit - vaulted
                    if actual_bal > 0:
                        start_bal = actual_bal
                        base_bet = start_bal / DIVIDER
                        vault_thresh = start_bal * vault_pct / 100

            # Stop check (based on cumulative profit, fixed threshold)
            if stop_thresh > 0 and profit >= stop_thresh and current_mult <= 1.01:
                break

        # Session end
        actual_bal_final = max(0, bank + profit - vaulted)
        total_assets = actual_bal_final + vaulted
        pnl = total_assets - bank  # true P&L

        results.append({
            'pnl': pnl,
            'profit': profit,
            'vaulted': vaulted,
            'balance': actual_bal_final,
            'total_assets': total_assets,
            'bets': bets_played,
            'busted': actual_bal_final <= 0.01,
        })

    # Aggregate
    pnls = sorted([r['pnl'] for r in results])
    n = len(pnls)
    bust_count = sum(1 for r in results if r['busted'])
    win_count = sum(1 for r in results if r['pnl'] > 0)
    avg_vault = sum(r['vaulted'] for r in results) / n
    avg_bets = sum(r['bets'] for r in results) / n
    avg_bal = sum(r['balance'] for r in results) / n

    # Bust loss analysis
    bust_losses = [-r['pnl'] for r in results if r['busted']]
    avg_bust_loss = sum(bust_losses) / len(bust_losses) if bust_losses else 0
    avg_bust_vault = sum(r['vaulted'] for r in results if r['busted']) / bust_count if bust_count else 0

    return {
        'median': pnls[n // 2],
        'mean': sum(pnls) / n,
        'bust_pct': bust_count / n * 100,
        'win_pct': win_count / n * 100,
        'p10': pnls[n // 10],
        'p90': pnls[9 * n // 10],
        'avg_vault': avg_vault,
        'avg_bets': avg_bets,
        'avg_bal': avg_bal,
        'avg_bust_loss': avg_bust_loss,
        'avg_bust_vault': avg_bust_vault,
    }


def print_row(tag, r, baseline=None):
    marker = ""
    if baseline is not None and r['median'] > baseline:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    mins = r['avg_bets'] / 10 / 60
    vault_info = f"v${r['avg_vault']:>6.1f}" if r['avg_vault'] > 0.5 else f"v$  0.0"
    print(f"  {tag:<38} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} "
          f"{vault_info} {r['avg_bets']:>6.0f}b {mins:>5.1f}m{marker}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    max_bets = 50000

    hdr = (f"  {'Config':<38} {'Median':>9} {'Mean':>9} "
           f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} "
           f"{'AvgVlt':>7} {'Bets':>7} {'Time':>6}")
    sep = (f"  {'─' * 38} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6} {'─' * 9} {'─' * 9} "
           f"{'─' * 7} {'─' * 7} {'─' * 6}")

    print()
    print("=" * 120)
    print("  MAMBA VAULT OPTIMIZER — FIXED BALANCE MODEL")
    print(f"  {num:,} sessions x {max_bets:,} max bets | D65 IOL3.0x div10000 | ${bank:,}")
    print(f"  Key metric: TOTAL ASSETS (balance + vault) — P&L = total_assets - bank")
    print("=" * 120)

    # ============================================================
    # SECTION 1: STOP-ONLY BASELINES (no vault)
    # ============================================================
    print("\n  --- STOP-ONLY BASELINES (vault=0) ---")
    print(hdr); print(sep)

    baselines = {}
    for stop in [0, 5, 8, 10, 15, 20, 30, 50]:
        tag = f"v0/s{stop}%" if stop > 0 else "v0/no-stop"
        r = sim(bank, num, max_bets, seed, 0, stop)
        print_row(tag, r)
        baselines[stop] = r

    # ============================================================
    # SECTION 2: VAULT + STOP COMBOS
    # ============================================================
    print(f"\n  --- VAULT + STOP COMBOS ---")
    print(hdr); print(sep)

    all_results = []
    for vault_pct in [1, 2, 3, 5, 8, 10]:
        for stop_pct in [0, 5, 8, 10, 15, 20, 30, 50]:
            tag = f"v{vault_pct}/s{stop_pct}%" if stop_pct > 0 else f"v{vault_pct}/grind"
            r = sim(bank, num, max_bets, seed, vault_pct, stop_pct)
            r['tag'] = tag
            r['vault_pct'] = vault_pct
            r['stop_pct'] = stop_pct
            all_results.append(r)

    # Print vault-only (grind) results
    print("\n  Vault-only (no stop) — grind until bust or max bets:")
    print(hdr); print(sep)
    for r in all_results:
        if r['stop_pct'] == 0:
            baseline_val = baselines[0]['median']
            print_row(r['tag'], r, baseline_val)

    # Print key stop levels with vault comparison
    for stop in [5, 8, 10, 15, 20]:
        print(f"\n  Stop={stop}% — vault comparison:")
        print(hdr); print(sep)
        baseline_val = baselines[stop]['median']
        print_row(f"v0/s{stop}% (baseline)", baselines[stop])
        for r in all_results:
            if r['stop_pct'] == stop:
                print_row(r['tag'], r, baseline_val)

    # ============================================================
    # SECTION 3: BUST LOSS ANALYSIS
    # ============================================================
    print(f"\n  --- BUST LOSS ANALYSIS (how much vault saves on bust) ---")
    print(f"  {'Config':<38} {'Bust%':>6} {'AvgBustLoss':>12} {'AvgBustVault':>13} {'Saved':>8}")
    print(f"  {'─' * 38} {'─' * 6} {'─' * 12} {'─' * 13} {'─' * 8}")

    for stop in [8, 10, 0]:
        for vault_pct in [0, 1, 2, 3, 5]:
            matches = [r for r in all_results if r['vault_pct'] == vault_pct and r['stop_pct'] == stop]
            if not matches:
                if vault_pct == 0:
                    r = baselines[stop]
                else:
                    continue
            else:
                r = matches[0]
            tag = f"v{vault_pct}/s{stop}%" if stop > 0 else f"v{vault_pct}/grind"
            saved = bank - r['avg_bust_loss'] if r['avg_bust_loss'] > 0 else 0
            print(f"  {tag:<38} {r['bust_pct']:>5.1f}% ${r['avg_bust_loss']:>10.2f} ${r['avg_bust_vault']:>11.2f} ${saved:>6.2f}")
        print()

    # ============================================================
    # SECTION 4: TOP CONFIGS
    # ============================================================
    by_med = sorted(all_results, key=lambda r: r['median'], reverse=True)

    print(f"\n  TOP 15 BY MEDIAN (all):")
    print(hdr); print(sep)
    for r in by_med[:15]:
        print_row(r['tag'], r)

    safe = [r for r in all_results if r['bust_pct'] < 10]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 10 BY MEDIAN (bust < 10%):")
    print(hdr); print(sep)
    for r in safe[:10]:
        print_row(r['tag'], r)

    # $/hour
    for_hour = [(r, r['median'] / max(r['avg_bets'] / 10 / 3600, 0.001))
                for r in all_results if r['median'] > 0]
    for_hour.sort(key=lambda x: x[1], reverse=True)
    print(f"\n  TOP 10 BY $/HOUR:")
    print(hdr); print(sep)
    for r, dph in for_hour[:10]:
        tag = r['tag'] + f" (${dph:.0f}/hr)"
        print_row(tag, r)

    # ============================================================
    # SUMMARY
    # ============================================================
    print()
    print("=" * 120)
    print("  SUMMARY")
    print("=" * 120)
    print(f"\n  Baseline (v0/s8%): median ${baselines[8]['median']:+.2f} | bust {baselines[8]['bust_pct']:.1f}%")
    if by_med:
        print(f"  Best overall:      median ${by_med[0]['median']:+.2f} | bust {by_med[0]['bust_pct']:.1f}% | {by_med[0]['tag']}")
    if safe:
        print(f"  Best safe (<10%):  median ${safe[0]['median']:+.2f} | bust {safe[0]['bust_pct']:.1f}% | {safe[0]['tag']}")

    # Vault impact summary
    print(f"\n  VAULT IMPACT AT STOP=8%:")
    for vpct in [0, 1, 2, 3, 5]:
        matches = [r for r in all_results if r['vault_pct'] == vpct and r['stop_pct'] == 8]
        if matches:
            r = matches[0]
        elif vpct == 0:
            r = baselines[8]
        else:
            continue
        saved = bank - r['avg_bust_loss'] if r['avg_bust_loss'] > 0 else 0
        print(f"    vault={vpct}%: median ${r['median']:+.2f} | bust {r['bust_pct']:.1f}% | "
              f"win {r['win_pct']:.1f}% | avg vault on bust: ${r['avg_bust_vault']:.1f} | saved: ${saved:.1f}")
    print("=" * 120)
