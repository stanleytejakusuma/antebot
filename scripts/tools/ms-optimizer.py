#!/usr/bin/env python3
"""
Momentum Shift Parameter Optimizer
Sweeps parameter permutations and ranks by two objectives:
  1. PROFIT: highest median net profit
  2. WAGER: highest wager volume (for VIP promotion grinding)

Usage:
  python3 ms-optimizer.py              # Full sweep (~10-15 min)
  python3 ms-optimizer.py --quick      # Quick sweep (~2 min)
"""

import random
import sys
import time
from itertools import product

# ============================================================
# BJ OUTCOME MODEL (same as strategy-comparison.py)
# ============================================================

BJ_OUTCOMES = [
    # (prob, payout, unit_change, label, wager_mult)
    (0.0475, +1.5, -1, "blackjack",     1),
    (0.3318, +1.0, -1, "win",           1),
    (0.4292, -1.0, +1, "loss",          1),
    (0.0848,  0.0,  0, "push",          1),
    (0.0532, +2.0, -2, "double_win",    2),
    (0.0418, -2.0, +2, "double_loss",   2),
    (0.0048, +2.0, -2, "split_win",     2),
    (0.0056, -2.0, +2, "split_loss",    2),
    (0.0005,  0.0,  0, "split_push",    2),
    (0.0004, +4.0, -4, "splitdbl_win",  4),
    (0.0004, -4.0, +4, "splitdbl_loss", 4),
]

_CUM = []
_c = 0
for _p, _, _, _, _ in BJ_OUTCOMES:
    _c += _p
    _CUM.append(_c)

def random_outcome():
    r = random.random()
    for i, cp in enumerate(_CUM):
        if r < cp:
            o = BJ_OUTCOMES[i]
            return o[1], o[2], o[3], o[4]  # payout, uc, label, wager_mult
    o = BJ_OUTCOMES[-1]
    return o[1], o[2], o[3], o[4]


# ============================================================
# STRATEGIES
# ============================================================

class MomentumShift:
    def __init__(self, unit, max_bet, recovery_threshold=5, recovery_exit=2,
                 cap_streak=3, cap_max=2, **kwargs):
        self.unit = unit
        self.max_bet = max_bet
        self.bet = unit
        self.recovery_threshold = recovery_threshold
        self.recovery_exit = recovery_exit
        self.cap_streak = cap_streak
        self.cap_max = cap_max
        self.mode = 'cruise'
        self.deficit = 0.0
        self.win_streak = 0
        self.cap_count = 0

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.win_streak += 1
            self.deficit = max(0, self.deficit - self.bet * abs(payout))
        elif is_loss:
            self.win_streak = 0
            self.deficit += self.bet * abs(payout)

        if self.mode == 'cruise':
            if self.deficit > self.recovery_threshold * self.unit:
                self.mode = 'recovery'
            elif self.win_streak >= self.cap_streak:
                self.mode = 'capitalize'
                self.cap_count = 0
        elif self.mode == 'recovery':
            if self.deficit < self.recovery_exit * self.unit:
                self.mode = 'cruise'
        elif self.mode == 'capitalize':
            self.cap_count += 1
            if is_loss or self.cap_count >= self.cap_max:
                self.mode = 'cruise'
                self.win_streak = 0

        if self.mode == 'cruise':
            self.bet = self.unit
        elif self.mode == 'recovery':
            if is_loss:
                self.bet += self.unit
            elif is_win:
                self.bet -= self.unit
        elif self.mode == 'capitalize':
            if is_win:
                self.bet = self.bet * 2
            elif is_loss:
                self.bet = self.unit
            # push: preserve

        self.bet = max(self.unit, min(self.bet, self.max_bet))


class OscarsGrind:
    def __init__(self, unit, max_bet, **kwargs):
        self.unit = unit
        self.max_bet = max_bet
        self.bet = unit
        self.cycle_profit = 0.0

    def update(self, payout, is_win, is_loss, balance):
        self.cycle_profit += self.bet * payout
        if is_win:
            if self.cycle_profit >= self.unit:
                self.cycle_profit = 0.0
                self.bet = self.unit
            else:
                needed = self.unit - self.cycle_profit
                self.bet = min(self.bet + self.unit, needed, self.max_bet)
                self.bet = max(self.bet, self.unit)


class DAlembert:
    def __init__(self, unit, max_bet, **kwargs):
        self.unit = unit
        self.max_bet = max_bet
        self.bet = unit

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.bet = max(self.bet - self.unit, self.unit)
        elif is_loss:
            self.bet = min(self.bet + self.unit, self.max_bet)


class DAlembertAW:
    """Action-weighted D'Alembert: uses payout magnitude for step size."""
    def __init__(self, unit, max_bet, **kwargs):
        self.unit = unit
        self.max_bet = max_bet
        self.bet = unit
        self.peak_profit = 0.0
        self.total_profit = 0.0

    def update(self, payout, is_win, is_loss, balance):
        self.total_profit += self.bet * payout
        weight = abs(payout)  # 1 for normal, 2 for double/split, 4 for split+double
        w_units = max(1, round(weight))

        if is_win:
            # Reset to base at profit peak (classic D'Alembert reset)
            if self.total_profit >= self.peak_profit:
                self.peak_profit = self.total_profit
                self.bet = self.unit
            else:
                self.bet = max(self.bet - w_units * self.unit, self.unit)
        elif is_loss:
            self.bet = min(self.bet + w_units * self.unit, self.max_bet)


class Flat:
    def __init__(self, unit, max_bet, **kwargs):
        self.unit = unit
        self.max_bet = max_bet
        self.bet = unit

    def update(self, payout, is_win, is_loss, balance):
        pass


# ============================================================
# SIMULATOR
# ============================================================

def simulate_session(strategy, outcomes, bankroll, stop_loss):
    profit = 0.0
    peak = 0.0
    max_dd = 0.0
    total_wagered = 0.0
    hands = 0

    for payout, uc, label, wmult in outcomes:
        balance = bankroll + profit
        if balance <= 0:
            break

        bet = min(strategy.bet, balance)
        if bet <= 0:
            break

        hands += 1
        total_wagered += bet * wmult  # Actual amount wagered (including doubles/splits)
        hand_profit = bet * payout
        profit += hand_profit

        if profit > peak:
            peak = profit
        dd = peak - profit
        if dd > max_dd:
            max_dd = dd

        if stop_loss > 0 and profit <= -stop_loss:
            return profit, total_wagered, True, hands, max_dd

        is_win = payout > 0
        is_loss = payout < 0
        strategy.update(payout, is_win, is_loss, bankroll + profit)

    return profit, total_wagered, False, hands, max_dd


# ============================================================
# SWEEP
# ============================================================

def run_sweep(configs, num_sessions, max_hands, bankroll, stop_loss, seed):
    """Run all configurations. Returns list of result dicts."""
    results = []
    total = len(configs)

    t0 = time.time()
    for idx, cfg in enumerate(configs):
        if idx % 10 == 0 and idx > 0:
            elapsed = time.time() - t0
            rate = idx / elapsed
            eta = (total - idx) / rate
            print(f"\r  Config {idx}/{total} ({elapsed:.0f}s, ~{eta:.0f}s left)   ", end='', flush=True)

        profits = []
        wagers = []
        busts = 0
        dds = []

        for s in range(num_sessions):
            random.seed(seed * 100000 + s)
            outcomes = [random_outcome() for _ in range(max_hands)]

            unit = bankroll / cfg['divider']
            max_bet = unit * cfg['max_mult']

            strat = cfg['cls'](
                unit=unit, max_bet=max_bet,
                recovery_threshold=cfg.get('rec_thresh', 5),
                recovery_exit=cfg.get('rec_exit', 2),
                cap_streak=cfg.get('cap_streak', 3),
                cap_max=cfg.get('cap_max', 2),
            )

            profit, wagered, bust, hands, dd = simulate_session(
                strat, outcomes, bankroll, stop_loss
            )

            profits.append(profit)
            wagers.append(wagered)
            if bust:
                busts += 1
            dds.append(dd)

        profits.sort()
        n = len(profits)
        avg_wager = sum(wagers) / n

        results.append({
            'label': cfg['label'],
            'cfg': cfg,
            'mean': sum(profits) / n,
            'median': profits[n // 2],
            'p10': profits[n // 10],
            'p90': profits[9 * n // 10],
            'bust_pct': busts / n * 100,
            'win_pct': sum(1 for p in profits if p > 0) / n * 100,
            'avg_dd': sum(dds) / n,
            'avg_wager': avg_wager,
            'wager_ratio': avg_wager / bankroll,
            'cost_per_wager': -sum(profits) / max(sum(wagers), 1) * 100,  # % lost per $ wagered
        })

    elapsed = time.time() - t0
    print(f"\r  Done: {total} configs in {elapsed:.0f}s" + " " * 30)
    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num_sessions = 1000 if quick else 3000
    max_hands = 2000
    bankroll = 1000
    stop_loss = 300
    seed = 42

    print()
    print("=" * 115)
    print("  STRATEGY PARAMETER OPTIMIZER (MS + Oscar + D'Alembert + Flat)")
    print(f"  {num_sessions:,} sessions x {max_hands:,} hands | Bankroll: ${bankroll:,} | Stop: -${stop_loss}")
    print(f"  Dual objective: PROFIT (median) vs WAGER (volume)")
    print("=" * 115)

    # Build parameter grid
    configs = []

    # Momentum Shift sweep
    for cap_max, cap_streak, rec_thresh, rec_exit, max_mult in product(
        [2, 3, 4, 5],       # capitalizeMaxBets
        [2, 3, 4],           # capitalizeStreak
        [5, 8, 12, 20],      # recoveryThreshold
        [2, 3, 5],           # recoveryExit
        [10, 15, 20],        # maxBetMultiple
    ):
        # Skip invalid: exit must be less than threshold
        if rec_exit >= rec_thresh:
            continue

        label = f"MS c{cap_max}/s{cap_streak} r{rec_thresh}/{rec_exit} x{max_mult}"
        configs.append({
            'label': label,
            'cls': MomentumShift,
            'divider': 2000,
            'max_mult': max_mult,
            'rec_thresh': rec_thresh,
            'rec_exit': rec_exit,
            'cap_streak': cap_streak,
            'cap_max': cap_max,
        })

    # Add baselines and D'Alembert variants
    for max_mult in [10, 15, 20]:
        configs.append({
            'label': f"Oscar's Grind x{max_mult}",
            'cls': OscarsGrind,
            'divider': 2000,
            'max_mult': max_mult,
            'rec_thresh': 5, 'rec_exit': 2, 'cap_streak': 3, 'cap_max': 2,
        })
        configs.append({
            'label': f"D'Alembert x{max_mult}",
            'cls': DAlembert,
            'divider': 2000,
            'max_mult': max_mult,
            'rec_thresh': 5, 'rec_exit': 2, 'cap_streak': 3, 'cap_max': 2,
        })
        configs.append({
            'label': f"D'Alembert AW x{max_mult}",
            'cls': DAlembertAW,
            'divider': 2000,
            'max_mult': max_mult,
            'rec_thresh': 5, 'rec_exit': 2, 'cap_streak': 3, 'cap_max': 2,
        })
        configs.append({
            'label': f"Flat x{max_mult}",
            'cls': Flat,
            'divider': 2000,
            'max_mult': max_mult,
            'rec_thresh': 5, 'rec_exit': 2, 'cap_streak': 3, 'cap_max': 2,
        })

    print(f"\n  Sweeping {len(configs)} configurations...")
    results = run_sweep(configs, num_sessions, max_hands, bankroll, stop_loss, seed)

    # ── TOP 20 BY MEDIAN PROFIT ──
    by_profit = sorted(results, key=lambda r: r['median'], reverse=True)

    print()
    print("=" * 115)
    print("  TOP 25: PROFIT STRATEGY (ranked by median profit)")
    print("=" * 115)
    print(f"  {'Rank':>4} {'Config':<32} {'Median':>8} {'Mean':>8} {'Bust%':>6} {'Win%':>6} {'AvgDD':>7} {'Wager':>8} {'Cost/W':>7}")
    print(f"  {'─'*4} {'─'*32} {'─'*8} {'─'*8} {'─'*6} {'─'*6} {'─'*7} {'─'*8} {'─'*7}")

    for i, r in enumerate(by_profit[:25]):
        marker = " *" if r['median'] > 0 else ""
        print(
            f"  {i+1:>4} {r['label']:<32}"
            f" ${r['median']:>+7.2f}"
            f" ${r['mean']:>+7.2f}"
            f" {r['bust_pct']:>5.1f}%"
            f" {r['win_pct']:>5.1f}%"
            f" ${r['avg_dd']:>6.0f}"
            f" ${r['avg_wager']:>7.0f}"
            f" {r['cost_per_wager']:>6.3f}%"
            f"{marker}"
        )

    # ── TOP 20 BY WAGER VOLUME ──
    by_wager = sorted(results, key=lambda r: r['avg_wager'], reverse=True)

    print()
    print("=" * 115)
    print("  TOP 25: WAGER STRATEGY (ranked by wager volume)")
    print(f"  Cost/Wager = % of wagered amount lost (lower = cheaper wagering)")
    print("=" * 115)
    print(f"  {'Rank':>4} {'Config':<32} {'Wager':>8} {'W/Bank':>7} {'Cost/W':>7} {'Median':>8} {'Bust%':>6} {'Win%':>6}")
    print(f"  {'─'*4} {'─'*32} {'─'*8} {'─'*7} {'─'*7} {'─'*8} {'─'*6} {'─'*6}")

    for i, r in enumerate(by_wager[:25]):
        print(
            f"  {i+1:>4} {r['label']:<32}"
            f" ${r['avg_wager']:>7.0f}"
            f" {r['wager_ratio']:>6.1f}x"
            f" {r['cost_per_wager']:>6.3f}%"
            f" ${r['median']:>+7.2f}"
            f" {r['bust_pct']:>5.1f}%"
            f" {r['win_pct']:>5.1f}%"
        )

    # ── PARETO FRONTIER ──
    # Find configs that are not dominated (no other config is better in BOTH profit AND wager)
    print()
    print("=" * 115)
    print("  PARETO FRONTIER (best tradeoff: profit vs wager)")
    print(f"  No config on this list is beaten by another in BOTH median profit AND wager volume")
    print("=" * 115)

    pareto = []
    for r in results:
        dominated = False
        for other in results:
            if other is r:
                continue
            if other['median'] >= r['median'] and other['avg_wager'] >= r['avg_wager']:
                if other['median'] > r['median'] or other['avg_wager'] > r['avg_wager']:
                    dominated = True
                    break
        if not dominated:
            pareto.append(r)

    pareto.sort(key=lambda r: r['median'], reverse=True)
    print(f"  {'#':>3} {'Config':<32} {'Median':>8} {'Wager':>8} {'W/Bank':>7} {'Cost/W':>7} {'Bust%':>6} {'Win%':>6}")
    print(f"  {'─'*3} {'─'*32} {'─'*8} {'─'*8} {'─'*7} {'─'*7} {'─'*6} {'─'*6}")

    for i, r in enumerate(pareto):
        print(
            f"  {i+1:>3} {r['label']:<32}"
            f" ${r['median']:>+7.2f}"
            f" ${r['avg_wager']:>7.0f}"
            f" {r['wager_ratio']:>6.1f}x"
            f" {r['cost_per_wager']:>6.3f}%"
            f" {r['bust_pct']:>5.1f}%"
            f" {r['win_pct']:>5.1f}%"
        )

    # ── SUMMARY ──
    best_profit = by_profit[0]
    best_wager = by_wager[0]

    print()
    print("=" * 115)
    print(f"  BEST FOR PROFIT: {best_profit['label']}")
    print(f"    Median: ${best_profit['median']:+.2f} | Bust: {best_profit['bust_pct']:.1f}% | Wager: ${best_profit['avg_wager']:.0f} ({best_profit['wager_ratio']:.1f}x)")
    print()
    print(f"  BEST FOR WAGER: {best_wager['label']}")
    print(f"    Wager: ${best_wager['avg_wager']:.0f} ({best_wager['wager_ratio']:.1f}x) | Cost: {best_wager['cost_per_wager']:.3f}%/$ | Median: ${best_wager['median']:+.2f}")
    print("=" * 115)
