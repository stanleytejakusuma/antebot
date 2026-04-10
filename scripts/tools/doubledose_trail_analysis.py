#!/usr/bin/env python3
"""Analyze whether trailing stop improves DoubleDose outcomes.

Simulates DoubleDose's exact mechanics:
  - Start at chance=98%, bet=base (balance/divider)
  - On loss: betSize *= 3, chance *= 1.05
  - On win: betSize = base, chance = 98 (then *= 0.98 → 96.04)
  - On first 5-win streak: chance = 25 (then *= 0.98 → 24.5)
  - resetOnProfit/resetOnLoss: cycle reset (internal state only)

Tests: no trail vs various trail configurations.
"""
import random
import statistics
import numpy as np


def simulate_doubledose(bank=1000, divider=1000000, num_bets=5000,
                        stop_profit_pct=20, stop_loss_pct=10,
                        reset_profit_pct=2.5, reset_loss_pct=5,
                        trail_act_pct=0, trail_lock_pct=0,
                        seed=None):
    """Simulate one DoubleDose session. Returns (profit, peak_profit, bets_played)."""
    rng = random.Random(seed)

    base = bank / divider
    bet = base
    chance = 98.0
    initial_chance = 98.0
    min_chance = 0.01
    max_chance = 98.0

    profit = 0.0
    peak_profit = 0.0
    internal_profit = 0.0  # cycle profit (resets)
    streak = 0
    first_5_streak_fired = False
    bets_played = 0

    stop_profit = bank * stop_profit_pct / 100
    stop_loss = bank * stop_loss_pct / 100
    reset_profit = bank * reset_profit_pct / 100
    reset_loss = bank * reset_loss_pct / 100

    # Trailing stop state
    trail_active = False
    trail_floor = 0.0
    trail_threshold = bank * trail_act_pct / 100 if trail_act_pct > 0 else None

    for _ in range(num_bets):
        # Win/loss at current chance
        win = rng.random() * 100 < chance

        if win:
            payout_mult = 99.0 / chance
            net = bet * (payout_mult - 1)
            profit += net
            internal_profit += net
            streak = max(1, streak + 1) if streak >= 0 else 1
        else:
            profit -= bet
            internal_profit -= bet
            streak = min(-1, streak - 1) if streak <= 0 else -1

        bets_played += 1
        if profit > peak_profit:
            peak_profit = profit

        # --- Strategy blocks (order matches script) ---

        # Block 1: On loss → bet *= 3
        if not win:
            bet *= 3

        # Block 2: On win → reset chance
        if win:
            chance = initial_chance

        # Block 3: On win → reset bet
        if win:
            bet = base

        # Block 6: First 5-win streak → chance = 25
        if win and streak == 5 and not first_5_streak_fired:
            chance = 25
            first_5_streak_fired = True

        # Block 7: On loss → chance *= 1.05
        if not win:
            chance *= 1.05

        # Block 8: On win → chance *= 0.98
        if win:
            chance *= 0.98

        # Clamp chance
        chance = min(max(chance, min_chance), max_chance)

        # --- Cycle reset ---
        if (reset_profit > 0 and internal_profit >= reset_profit) or \
           (reset_loss > 0 and -internal_profit >= reset_loss):
            bet = base
            chance = initial_chance
            internal_profit = 0
            streak = 0
            first_5_streak_fired = False

        # --- Trailing stop ---
        if trail_threshold is not None:
            if not trail_active and profit >= trail_threshold:
                trail_active = True
            if trail_active:
                trail_floor = peak_profit * trail_lock_pct / 100
                if profit <= trail_floor:
                    return (profit, peak_profit, bets_played, 'trail')

        # --- Stop profit ---
        if stop_profit > 0 and profit >= stop_profit:
            return (profit, peak_profit, bets_played, 'profit')

        # --- Stop loss (predictive: would next bet breach?) ---
        if stop_loss > 0 and profit - bet <= -stop_loss:
            return (profit, peak_profit, bets_played, 'loss')

    return (profit, peak_profit, bets_played, 'maxbets')


def run_mc(label, num_sessions=5000, **kwargs):
    """Run Monte Carlo and return stats dict."""
    results = []
    for i in range(num_sessions):
        p, peak, bets, exit_type = simulate_doubledose(seed=42*100000 + i, **kwargs)
        results.append((p, peak, bets, exit_type))

    profits = [r[0] for r in results]
    peaks = [r[1] for r in results]
    bets_list = [r[2] for r in results]
    exits = [r[3] for r in results]

    sorted_p = sorted(profits)
    n = len(profits)

    def pctl(data, pct):
        idx = pct / 100.0 * (len(data) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(data) - 1)
        frac = idx - lo
        return data[lo] + frac * (data[hi] - data[lo])

    exit_counts = {}
    for e in exits:
        exit_counts[e] = exit_counts.get(e, 0) + 1

    return {
        'label': label,
        'median': statistics.median(profits),
        'mean': statistics.mean(profits),
        'p10': pctl(sorted_p, 10),
        'p90': pctl(sorted_p, 90),
        'win_pct': sum(1 for p in profits if p > 0) / n * 100,
        'avg_peak': statistics.mean(peaks),
        'avg_bets': statistics.mean(bets_list),
        'exits': exit_counts,
    }


def pr(r):
    exits_str = ', '.join(f'{k}:{v}' for k, v in sorted(r['exits'].items()))
    print("  {:<50} ${:>+8.2f} ${:>+8.2f} {:>5.1f}% ${:>+8.2f} ${:>+8.2f}  pk${:>6.2f}  ~{:>5.0f}b  {}".format(
        r['label'], r['median'], r['mean'], r['win_pct'],
        r['p10'], r['p90'], r['avg_peak'], r['avg_bets'], exits_str))


H = "  {:<50} {:>9} {:>9} {:>6} {:>9} {:>9}  {:>8}  {:>6}  {}".format(
    'Config', 'Med', 'Mean', 'Win%', 'P10', 'P90', 'AvgPeak', 'Bets', 'Exits')
S = "  {} {} {} {} {} {} {} {} {}".format(
    '-'*50, '-'*9, '-'*9, '-'*6, '-'*9, '-'*9, '-'*8, '-'*6, '-'*10)


def main():
    N = 5000
    BETS = 10000  # max bets per session

    print()
    print("=" * 140)
    print("  DOUBLEDOSE TRAILING STOP ANALYSIS")
    print(f"  {N} sessions | $1000 bank | div=1M | {BETS} max bets")
    print("=" * 140)

    base = dict(bank=1000, divider=1000000, num_bets=BETS,
                stop_profit_pct=20, stop_loss_pct=10,
                reset_profit_pct=2.5, reset_loss_pct=5)

    # ============================================
    # SECTION 1: Baseline (no trail)
    # ============================================
    print("\n  === BASELINE (no trailing stop) ===")
    print(H); print(S)

    r = run_mc("No trail (current config)", N, **base)
    pr(r)

    # ============================================
    # SECTION 2: Various stop-profit levels (no trail)
    # ============================================
    print("\n  === TIGHTER STOP-PROFIT (no trail) ===")
    print(H); print(S)

    for sp in [3, 5, 8, 10, 15]:
        r = run_mc(f"stopProfit={sp}% (no trail)", N,
                   **{**base, 'stop_profit_pct': sp})
        pr(r)

    # ============================================
    # SECTION 3: Trailing stop configurations
    # ============================================
    print("\n  === TRAILING STOP CONFIGS ===")
    print(H); print(S)

    for act, lock in [(1, 60), (2, 60), (3, 60), (5, 60),
                      (2, 50), (2, 70), (2, 80),
                      (1, 80), (3, 50)]:
        r = run_mc(f"Trail act={act}% lock={lock}%", N,
                   **{**base, 'trail_act_pct': act, 'trail_lock_pct': lock})
        pr(r)

    # ============================================
    # SECTION 4: Trail + tighter stop-profit combo
    # ============================================
    print("\n  === TRAIL + TIGHTER STOP-PROFIT ===")
    print(H); print(S)

    for sp, act, lock in [(5, 2, 60), (5, 3, 60), (8, 2, 60),
                          (8, 3, 70), (10, 2, 60), (3, 1, 70)]:
        r = run_mc(f"stopProfit={sp}% + trail {act}/{lock}", N,
                   **{**base, 'stop_profit_pct': sp,
                      'trail_act_pct': act, 'trail_lock_pct': lock})
        pr(r)

    print()
    print("=" * 140)


if __name__ == "__main__":
    main()
