#!/usr/bin/env python3
"""
UpDown D'Alembert vs VIPER — Head-to-Head Monte Carlo Comparison

Tests Swen's asymmetric D'Alembert from Antebot forum against VIPER v2.
Sweeps unitUp/unitDown ratios, bet caps, and action weighting.

Usage:
  python3 updown-vs-viper.py          # Full sweep (5k sessions)
  python3 updown-vs-viper.py --quick  # Quick (2k sessions)
"""

import random
import sys
import time
from itertools import product

# ============================================================
# BLACKJACK OUTCOME MODEL (8-deck, perfect basic strategy)
# Calibrated: house edge = 0.495%
# ============================================================

BJ_OUTCOMES = [
    # (probability, payout_multiplier, action_weight, label)
    (0.0475, +1.5, 1, "blackjack"),
    (0.3318, +1.0, 1, "win"),
    (0.4292, -1.0, 1, "loss"),
    (0.0848,  0.0, 0, "push"),
    (0.0532, +2.0, 2, "double_win"),
    (0.0418, -2.0, 2, "double_loss"),
    (0.0048, +2.0, 2, "split_win"),
    (0.0056, -2.0, 2, "split_loss"),
    (0.0005,  0.0, 0, "split_push"),
    (0.0004, +4.0, 4, "splitdbl_win"),
    (0.0004, -4.0, 4, "splitdbl_loss"),
]

_CUM_PROBS = []
_cum = 0
for _p, _, _, _ in BJ_OUTCOMES:
    _cum += _p
    _CUM_PROBS.append(_cum)


def random_outcome():
    r = random.random()
    for i, cp in enumerate(_CUM_PROBS):
        if r < cp:
            _, payout, aw, label = BJ_OUTCOMES[i]
            return (payout, aw, label)
    _, payout, aw, label = BJ_OUTCOMES[-1]
    return (payout, aw, label)


# ============================================================
# STRATEGIES
# ============================================================

class VIPER:
    """VIPER v2: Martingale 2x (Strike) + flat brake (Coil) + Paroli 2x (Capitalize)."""
    def __init__(self, base, brake_at=10, cap_streak=2, cap_max=2):
        self.base = base
        self.brake_at = brake_at
        self.cap_streak = cap_streak
        self.cap_max = cap_max
        self.bet = base
        self.mode = 'strike'
        self.ls = 0
        self.ws = 0
        self.cap_count = 0
        self.brake_bet = base  # bet level when brake activates

    def update(self, payout, action_weight, label):
        is_win = payout > 0
        is_push = payout == 0

        if is_push:
            return

        if is_win:
            self.ws += 1
            self.ls = 0
        else:
            self.ws = 0
            self.ls += 1

        if self.mode == 'strike':
            if is_win:
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'cap'
                    self.cap_count = 0
                    self.bet = self.base * 2
            else:
                if self.brake_at > 0 and self.ls >= self.brake_at:
                    self.mode = 'coil'
                    self.brake_bet = self.bet
                else:
                    self.bet *= 2  # Martingale 2x

        elif self.mode == 'coil':
            # Flat bet at brake level
            if is_win:
                self.mode = 'strike'
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'cap'
                    self.cap_count = 0
                    self.bet = self.base * 2

        elif self.mode == 'cap':
            self.cap_count += 1
            if not is_win or self.cap_count >= self.cap_max:
                self.mode = 'strike'
                self.ws = 0
                self.bet = self.base
            elif is_win:
                self.bet = min(self.bet * 2, self.base * 100)

        self.bet = max(self.base, self.bet)


class UpDownDAlembert:
    """
    Asymmetric D'Alembert from Antebot forum.
    - unitUp: amount to add on loss
    - unitDown: amount to subtract on win
    - Action-weighted: doubles adjust by 2x unit, splits by 2x, split+dbl by 4x
    - Optional bet cap: reset to base when bet > capMultiple * base AND in profit
    - Reset to base when bet drops to unitDown level
    """
    def __init__(self, base, unit_up, unit_down, cap_multiple=0, action_weighted=True):
        self.base = base
        self.unit_up = unit_up
        self.unit_down = unit_down
        self.cap_multiple = cap_multiple  # 0 = no cap
        self.action_weighted = action_weighted
        self.bet = base
        self.session_profit = 0.0

    def update(self, payout, action_weight, label):
        is_win = payout > 0
        is_push = payout == 0

        # Track session profit
        self.session_profit += payout * self.bet

        if is_push:
            return

        # Determine adjustment multiplier
        if self.action_weighted:
            adj_mult = max(1, action_weight)
        else:
            adj_mult = 1

        if is_win:
            self.bet -= self.unit_down * adj_mult
        else:
            self.bet += self.unit_up * adj_mult

        # Floor at base
        if self.bet <= self.base:
            self.bet = self.base

        # Cap check: if bet > N*base AND in profit, reset
        if self.cap_multiple > 0 and self.bet > self.base * self.cap_multiple:
            if self.session_profit > 0:
                self.bet = self.base


class ClassicDAlembert:
    """Classic D'Alembert: unit = startBet, up 1u on loss, down 1u on win."""
    def __init__(self, base, action_weighted=True):
        self.base = base
        self.action_weighted = action_weighted
        self.bet = base

    def update(self, payout, action_weight, label):
        is_win = payout > 0
        is_push = payout == 0

        if is_push:
            return

        if self.action_weighted:
            adj_mult = max(1, action_weight)
        else:
            adj_mult = 1

        if is_win:
            self.bet -= self.base * adj_mult
        else:
            self.bet += self.base * adj_mult

        if self.bet < self.base:
            self.bet = self.base


# ============================================================
# SIMULATOR
# ============================================================

def sim(tag, strat_fn, num=5000, max_hands=5000, bank=1000, seed=42,
        vault_pct=5, stop_total_pct=10):
    profits, busts = [], 0
    total_wagered_all = 0

    for s in range(num):
        random.seed(seed * 100000 + s)
        st = strat_fn()
        profit = 0.0
        wagered = 0.0
        vaulted = 0.0
        profit_at_vault = 0.0
        start_bal = bank

        for hand in range(max_hands):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            bet = min(st.bet, bal)
            if bet <= 0:
                busts += 1
                break

            payout, aw, label = random_outcome()
            hand_pnl = payout * bet
            profit += hand_pnl
            wagered += bet * (1 + max(0, aw - 1))  # account for doubles/splits

            if bank + profit <= 0:
                busts += 1
                break

            st.update(payout, aw, label)

            # Vault check
            if vault_pct > 0 and st.bet <= st.base * 1.01:
                vault_thresh = start_bal * vault_pct / 100
                current_profit = profit - profit_at_vault
                if current_profit >= vault_thresh:
                    vaulted += current_profit
                    profit_at_vault = profit
                    start_bal = bank + profit - vaulted
                    if hasattr(st, 'base'):
                        # Don't rebase for d'alembert — keep original units
                        pass

            # Stop check
            if stop_total_pct > 0 and profit >= bank * stop_total_pct / 100:
                if st.bet <= st.base * 1.01:
                    break

        profits.append(profit)
        total_wagered_all += wagered

    profits.sort()
    n = len(profits)
    return {
        'median': profits[n // 2],
        'mean': sum(profits) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in profits if p > 0) / n * 100,
        'p10': profits[n // 10],
        'p90': profits[9 * n // 10],
        'avg_wager': total_wagered_all / n,
    }


def print_row(tag, r, baseline_med=None):
    marker = ""
    if baseline_med is not None and r['median'] > baseline_med:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    wager_x = r['avg_wager'] / 1000
    print(f"  {tag:<50} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {wager_x:>4.1f}x{marker}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42

    hdr = (f"  {'Config':<50} {'Median':>9} {'Mean':>9} "
           f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Wgr':>5}")
    sep = (f"  {'─' * 50} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6} {'─' * 9} {'─' * 9} {'─' * 5}")

    print()
    print("=" * 115)
    print("  UPDOWN D'ALEMBERT vs VIPER — Head-to-Head")
    print(f"  {num:,} sessions x 5,000 hands | $1,000 bankroll | vault 5% / stop 10%")
    print("=" * 115)

    # === BASELINES ===
    print("\n  --- BASELINES ---")
    print(hdr); print(sep)

    # VIPER v2 (our champion)
    div = 6000
    r_viper = sim("VIPER v2 (Mart2x brake@10 cap2/2)",
                  lambda: VIPER(bank / div, brake_at=10, cap_streak=2, cap_max=2), num)
    print_row("VIPER v2 (Mart2x brake@10 cap2/2) div=6k", r_viper)
    viper_med = r_viper['median']

    # Classic D'Alembert (unit = base)
    r_classic = sim("Classic D'Alembert (unit=base) div=6k",
                    lambda: ClassicDAlembert(bank / 6000, action_weighted=True), num)
    print_row("Classic D'Alembert (unit=base) div=6k AW", r_classic, viper_med)

    r_classic20 = sim("Classic D'Alembert div=20k",
                      lambda: ClassicDAlembert(bank / 20000, action_weighted=True), num)
    print_row("Classic D'Alembert (unit=base) div=20k AW", r_classic20, viper_med)

    # Flat
    r_flat = sim("Flat", lambda: ClassicDAlembert(bank / 6000, action_weighted=False), num)
    # Hack: flat by making it never change — actually let me just test inline
    # Skip flat, focus on the comparison

    # === SWEN'S EXACT CONFIG ===
    print(f"\n  --- SWEN'S CONFIG (unit=$0.0005, startBet=$0.01) ---")
    print(hdr); print(sep)

    # Swen: startBet=0.01, unit=0.0005 (5% of base)
    r_swen = sim("Swen original (unit=5% of base)",
                 lambda: UpDownDAlembert(0.01, 0.0005, 0.0005), num)
    print_row("Swen: up=0.0005 down=0.0005 base=0.01", r_swen, viper_med)

    # With 3x cap
    r_swen_cap = sim("Swen + 3x cap",
                     lambda: UpDownDAlembert(0.01, 0.0005, 0.0005, cap_multiple=3), num)
    print_row("Swen: up=0.0005 down=0.0005 cap@3x", r_swen_cap, viper_med)

    # === ASYMMETRIC SWEEP ===
    print(f"\n  --- ASYMMETRIC D'ALEMBERT (up ≠ down, div=6000) ---")
    print(hdr); print(sep)

    base = bank / 6000
    configs = []

    # Symmetric first
    for ratio in [0.25, 0.5, 1.0]:
        u = base * ratio
        tag = f"Symmetric unit={ratio:.0%} of base"
        r = sim(tag, lambda u=u: UpDownDAlembert(base, u, u), num)
        print_row(tag, r, viper_med)

    # Asymmetric: up faster than down
    print()
    for up_r, down_r in [(1.0, 0.5), (1.0, 0.25), (1.5, 0.5), (1.5, 1.0),
                          (2.0, 0.5), (2.0, 1.0), (0.5, 1.0), (0.5, 1.5)]:
        u_up = base * up_r
        u_dn = base * down_r
        tag = f"Up={up_r:.1f}x Down={down_r:.1f}x base"
        r = sim(tag, lambda u=u_up, d=u_dn: UpDownDAlembert(base, u, d), num)
        configs.append((tag, r))
        print_row(tag, r, viper_med)

    # === ASYMMETRIC + CAP SWEEP ===
    print(f"\n  --- ASYMMETRIC + BET CAP (div=6000) ---")
    print(hdr); print(sep)

    for up_r, down_r, cap in product(
        [0.5, 1.0, 1.5, 2.0],
        [0.25, 0.5, 1.0],
        [3, 5, 10, 0],
    ):
        if up_r == down_r and cap == 0:
            continue  # already tested
        u_up = base * up_r
        u_dn = base * down_r
        cap_label = f"cap@{cap}x" if cap > 0 else "nocap"
        tag = f"Up={up_r:.1f}x Dn={down_r:.1f}x {cap_label}"
        r = sim(tag, lambda u=u_up, d=u_dn, c=cap: UpDownDAlembert(base, u, d, cap_multiple=c), num)
        configs.append((tag, r))

    # Sort by median
    configs.sort(key=lambda x: x[1]['median'], reverse=True)

    print(f"\n  TOP 20 BY MEDIAN:")
    print(hdr); print(sep)
    for tag, r in configs[:20]:
        print_row(tag, r, viper_med)

    # Top with bust < 15%
    safe = [(t, r) for t, r in configs if r['bust_pct'] < 15]
    safe.sort(key=lambda x: x[1]['median'], reverse=True)
    print(f"\n  TOP 10 BY MEDIAN (bust < 15%):")
    print(hdr); print(sep)
    for tag, r in safe[:10]:
        print_row(tag, r, viper_med)

    # === DIVIDER SWEEP FOR BEST CONFIG ===
    if configs:
        best_tag, best_r = configs[0]
        print(f"\n  --- BEST CONFIG ACROSS DIVIDERS ---")
        print(f"  Best: {best_tag}")
        print(hdr); print(sep)

        for div in [3000, 4000, 6000, 8000, 10000, 15000, 20000]:
            b = bank / div
            # Parse the best config params... just use top config manually
            # Re-run VIPER and best UpDown at each divider
            rv = sim(f"VIPER div={div}",
                     lambda d=div: VIPER(bank / d, brake_at=10, cap_streak=2, cap_max=2), num)
            print_row(f"VIPER div={div}", rv)

        print()
        # Find which up/down ratio won
        # Re-test top 3 at multiple dividers
        for tag, r in configs[:3]:
            print(f"  Testing '{tag}' across dividers:")
            for div in [3000, 6000, 10000, 20000]:
                b = bank / div
                # Approximate — use same ratio
                # Extract up/down from tag
                parts = tag.split()
                try:
                    up_r = float(parts[0].split('=')[1].replace('x', ''))
                    dn_r = float(parts[1].split('=')[1].replace('x', ''))
                    cap_str = parts[2] if len(parts) > 2 else "nocap"
                    cap = int(cap_str.replace('cap@', '').replace('x', '')) if 'cap@' in cap_str else 0
                except:
                    continue
                ru = sim(f"{tag} div={div}",
                         lambda d=div, u=up_r, dn=dn_r, c=cap:
                         UpDownDAlembert(bank / d, bank / d * u, bank / d * dn, cap_multiple=c), num)
                print_row(f"  div={div}", ru, viper_med)
            print()

    # === SUMMARY ===
    print("=" * 115)
    print("  SUMMARY")
    print("=" * 115)
    print(f"\n  VIPER v2 baseline:     median ${viper_med:+.2f} | bust {r_viper['bust_pct']:.1f}% | win {r_viper['win_pct']:.1f}%")
    if configs:
        best_tag, best_r = configs[0]
        print(f"  Best UpDown overall:   median ${best_r['median']:+.2f} | bust {best_r['bust_pct']:.1f}% | win {best_r['win_pct']:.1f}% | {best_tag}")
        if safe:
            safe_tag, safe_r = safe[0]
            print(f"  Best UpDown safe:      median ${safe_r['median']:+.2f} | bust {safe_r['bust_pct']:.1f}% | win {safe_r['win_pct']:.1f}% | {safe_tag}")

    beats = configs[0][1]['median'] > viper_med if configs else False
    print(f"\n  VERDICT: UpDown D'Alembert {'BEATS' if beats else 'does NOT beat'} VIPER")
    if configs:
        delta = configs[0][1]['median'] - viper_med
        print(f"  Delta: ${delta:+.2f}")
    print("=" * 115)
