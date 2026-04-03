#!/usr/bin/env python3
"""
Comprehensive Blackjack Strategy Comparison — Monte Carlo Simulator v2.0
Tests 15 betting systems head-to-head with identical outcome sequences.

Usage:
  python3 strategy-comparison.py              # Full comparison (all 3 phases)
  python3 strategy-comparison.py --quick      # Quick 2000-session test
  python3 strategy-comparison.py --phase1     # Phase 1 only (head-to-head)
  python3 strategy-comparison.py --sessions N # Custom session count
"""

import random
import sys
import time

# ============================================================
# BLACKJACK OUTCOME MODEL (8-deck, perfect basic strategy)
# Calibrated: probs sum to 1.0000, house edge = 0.495%
# ============================================================

BJ_OUTCOMES = [
    # (probability, payout_multiplier, unit_change, label)
    (0.0475, +1.5, -1, "blackjack"),
    (0.3318, +1.0, -1, "win"),
    (0.4292, -1.0, +1, "loss"),
    (0.0848,  0.0,  0, "push"),
    (0.0532, +2.0, -2, "double_win"),
    (0.0418, -2.0, +2, "double_loss"),
    (0.0048, +2.0, -2, "split_win"),
    (0.0056, -2.0, +2, "split_loss"),
    (0.0005,  0.0,  0, "split_push"),
    (0.0004, +4.0, -4, "splitdbl_win"),
    (0.0004, -4.0, +4, "splitdbl_loss"),
]

# Pre-compute cumulative probabilities for fast sampling
_CUM_PROBS = []
_cum = 0
for _p, _, _, _ in BJ_OUTCOMES:
    _cum += _p
    _CUM_PROBS.append(_cum)


def random_outcome():
    """Pick random BJ outcome using pre-computed cumulative probabilities."""
    r = random.random()
    for i, cp in enumerate(_CUM_PROBS):
        if r < cp:
            _, payout, uc, label = BJ_OUTCOMES[i]
            return (payout, uc, label)
    _, payout, uc, label = BJ_OUTCOMES[-1]
    return (payout, uc, label)


def verify_model():
    """Verify outcome model integrity."""
    total_prob = sum(o[0] for o in BJ_OUTCOMES)
    ev = sum(o[0] * o[1] for o in BJ_OUTCOMES)
    edge = -ev * 100
    print(f"  Model: BJ 8-deck | probs={total_prob:.4f} | house edge={edge:.3f}%")
    return edge


# ============================================================
# STRATEGY BASE CLASS
# ============================================================

class Strategy:
    name = "Base"

    def __init__(self, unit, max_bet, **kwargs):
        self.unit = unit
        self.max_bet = max_bet
        self.bet = unit

    def update(self, payout, is_win, is_loss, balance):
        """Process outcome, set self.bet for next hand."""
        raise NotImplementedError

    def reset(self):
        """Reset strategy to initial state (for vault-and-continue)."""
        self.bet = self.unit


# ============================================================
# NEGATIVE PROGRESSIONS (raise on loss)
# ============================================================

class Flat(Strategy):
    name = "Flat"
    def update(self, payout, is_win, is_loss, balance):
        self.bet = self.unit


class Martingale(Strategy):
    name = "Martingale"
    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.bet = self.unit
        elif is_loss:
            self.bet = min(self.bet * 2, self.max_bet)


class GrandMartingale(Strategy):
    name = "Grand Martingale"
    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.bet = self.unit
        elif is_loss:
            self.bet = min(self.bet * 2 + self.unit, self.max_bet)


class DAlembert(Strategy):
    name = "D'Alembert"
    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.bet = max(self.bet - self.unit, self.unit)
        elif is_loss:
            self.bet = min(self.bet + self.unit, self.max_bet)


class FibonacciStrat(Strategy):
    name = "Fibonacci"
    FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]

    def __init__(self, unit, max_bet, **kwargs):
        super().__init__(unit, max_bet)
        self.pos = 0

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.pos = max(0, self.pos - 2)
        elif is_loss:
            self.pos = min(self.pos + 1, len(self.FIB) - 1)
        self.bet = min(self.FIB[self.pos] * self.unit, self.max_bet)

    def reset(self):
        self.bet = self.unit
        self.pos = 0


class Labouchere(Strategy):
    name = "Labouchere"

    def __init__(self, unit, max_bet, starting_list=None, **kwargs):
        super().__init__(unit, max_bet)
        self.starting_list = starting_list or [1, 2, 3]
        self.seq = list(self.starting_list)
        self.bet = self._calc_bet()

    def _calc_bet(self):
        if not self.seq:
            self.seq = list(self.starting_list)
        if len(self.seq) == 1:
            return min(self.seq[0] * self.unit, self.max_bet)
        return min((self.seq[0] + self.seq[-1]) * self.unit, self.max_bet)

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            if len(self.seq) >= 2:
                self.seq.pop(0)
                self.seq.pop(-1)
            elif len(self.seq) == 1:
                self.seq.pop(0)
            # Cycle complete — restart
            if not self.seq:
                self.seq = list(self.starting_list)
        elif is_loss:
            bet_units = max(1, round(self.bet / self.unit))
            self.seq.append(bet_units)
        self.bet = self._calc_bet()

    def reset(self):
        self.seq = list(self.starting_list)
        self.bet = self._calc_bet()


class OscarsGrind(Strategy):
    name = "Oscar's Grind"

    def __init__(self, unit, max_bet, **kwargs):
        super().__init__(unit, max_bet)
        self.cycle_profit = 0.0

    def update(self, payout, is_win, is_loss, balance):
        hand_pnl = self.bet * payout
        self.cycle_profit += hand_pnl

        if is_win:
            if self.cycle_profit >= self.unit:
                # Cycle complete (+1u goal reached), reset
                self.cycle_profit = 0.0
                self.bet = self.unit
            else:
                # Increase by 1u, cap so we don't overshoot +1u goal
                needed = self.unit - self.cycle_profit
                self.bet = min(self.bet + self.unit, needed, self.max_bet)
                self.bet = max(self.bet, self.unit)
        # loss and push: keep same bet

    def reset(self):
        self.bet = self.unit
        self.cycle_profit = 0.0


# ============================================================
# POSITIVE PROGRESSIONS (raise on win)
# ============================================================

class Paroli(Strategy):
    name = "Paroli"

    def __init__(self, unit, max_bet, limit=3, **kwargs):
        super().__init__(unit, max_bet)
        self.limit = limit
        self.streak = 0

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.streak += 1
            if self.streak >= self.limit:
                self.bet = self.unit
                self.streak = 0
            else:
                self.bet = min(self.bet * 2, self.max_bet)
        elif is_loss:
            self.bet = self.unit
            self.streak = 0

    def reset(self):
        self.bet = self.unit
        self.streak = 0


class System1326(Strategy):
    name = "1-3-2-6"

    def __init__(self, unit, max_bet, sequence=None, **kwargs):
        super().__init__(unit, max_bet)
        self.sequence = sequence or [1, 3, 2, 6]
        self.step = 0
        self.bet = min(self.sequence[0] * self.unit, self.max_bet)

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.step += 1
            if self.step >= len(self.sequence):
                self.step = 0
        elif is_loss:
            self.step = 0
        self.bet = min(self.sequence[self.step] * self.unit, self.max_bet)

    def reset(self):
        self.step = 0
        self.bet = min(self.sequence[0] * self.unit, self.max_bet)


class ReverseDAlembert(Strategy):
    name = "Reverse D'Alembert"
    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.bet = min(self.bet + self.unit, self.max_bet)
        elif is_loss:
            self.bet = max(self.bet - self.unit, self.unit)


class ReverseFibonacci(Strategy):
    name = "Reverse Fibonacci"
    FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]

    def __init__(self, unit, max_bet, **kwargs):
        super().__init__(unit, max_bet)
        self.pos = 0

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.pos = min(self.pos + 1, len(self.FIB) - 1)
        elif is_loss:
            self.pos = max(0, self.pos - 2)
        self.bet = min(self.FIB[self.pos] * self.unit, self.max_bet)

    def reset(self):
        self.bet = self.unit
        self.pos = 0


class ReverseLabouchere(Strategy):
    name = "Reverse Labouchere"

    def __init__(self, unit, max_bet, starting_list=None, max_list_len=10, **kwargs):
        super().__init__(unit, max_bet)
        self.starting_list = starting_list or [1, 2, 3]
        self.max_list_len = max_list_len
        self.seq = list(self.starting_list)
        self.bet = self._calc_bet()

    def _calc_bet(self):
        if not self.seq:
            self.seq = list(self.starting_list)
        if len(self.seq) == 1:
            return min(self.seq[0] * self.unit, self.max_bet)
        return min((self.seq[0] + self.seq[-1]) * self.unit, self.max_bet)

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            bet_units = max(1, round(self.bet / self.unit))
            self.seq.append(bet_units)
            # Cap list to prevent infinite growth on streaks
            if len(self.seq) > self.max_list_len:
                self.seq = list(self.starting_list)
        elif is_loss:
            if len(self.seq) >= 2:
                self.seq.pop(0)
                self.seq.pop(-1)
            elif len(self.seq) == 1:
                self.seq.pop(0)
            if not self.seq:
                self.seq = list(self.starting_list)
        self.bet = self._calc_bet()

    def reset(self):
        self.seq = list(self.starting_list)
        self.bet = self._calc_bet()


# ============================================================
# HYBRID / OTHER
# ============================================================

class Percentage(Strategy):
    name = "Percentage"

    def __init__(self, unit, max_bet, bankroll=1000, **kwargs):
        super().__init__(unit, max_bet)
        self.pct = unit / bankroll  # Calibrate so initial bet = unit

    def update(self, payout, is_win, is_loss, balance):
        # Bet = fixed % of current balance (self-regulating)
        self.bet = max(self.unit * 0.1, min(balance * self.pct, self.max_bet))


class Hollandish(Strategy):
    name = "Hollandish"

    def __init__(self, unit, max_bet, **kwargs):
        super().__init__(unit, max_bet)
        self.level = 1
        self.group_count = 0
        self.group_profit = 0.0

    def update(self, payout, is_win, is_loss, balance):
        self.group_profit += self.bet * payout
        self.group_count += 1

        if self.group_count >= 3:
            if self.group_profit < 0:
                self.level += 1  # Increase after losing group
            else:
                self.level = 1   # Reset after profitable group
            self.group_count = 0
            self.group_profit = 0.0

        self.bet = min(self.level * self.unit, self.max_bet)

    def reset(self):
        self.bet = self.unit
        self.level = 1
        self.group_count = 0
        self.group_profit = 0.0


class MomentumShift(Strategy):
    name = "Momentum Shift"

    def __init__(self, unit, max_bet, recovery_threshold=5, recovery_exit=2,
                 cap_streak=3, cap_max=2, **kwargs):
        super().__init__(unit, max_bet)
        self.recovery_threshold = recovery_threshold
        self.recovery_exit = recovery_exit
        self.cap_streak = cap_streak
        self.cap_max = cap_max
        self.mode = 'cruise'
        self.deficit = 0.0
        self.win_streak = 0
        self.cap_count = 0

    def update(self, payout, is_win, is_loss, balance):
        # Update deficit and streak
        if is_win:
            self.win_streak += 1
            self.deficit = max(0, self.deficit - self.bet * abs(payout))
        elif is_loss:
            self.win_streak = 0
            self.deficit += self.bet * abs(payout)
        # push: no change to deficit or streak

        # Mode transitions
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

        # Bet sizing
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
            else:
                self.bet = self.unit

        self.bet = max(self.unit, min(self.bet, self.max_bet))

    def reset(self):
        self.bet = self.unit
        self.mode = 'cruise'
        self.deficit = 0.0
        self.win_streak = 0
        self.cap_count = 0


# ============================================================
# STRATEGY REGISTRY
# ============================================================

DEFAULT_STRATEGIES = [
    # (display_name, class, kwargs)
    ("Flat",                Flat,              {}),
    ("Martingale",          Martingale,        {}),
    ("Grand Martingale",    GrandMartingale,   {}),
    ("D'Alembert",          DAlembert,         {}),
    ("Fibonacci",           FibonacciStrat,    {}),
    ("Labouchere",          Labouchere,        {"starting_list": [1, 2, 3]}),
    ("Oscar's Grind",       OscarsGrind,       {}),
    ("Paroli",              Paroli,            {"limit": 3}),
    ("1-3-2-6",             System1326,        {}),
    ("Reverse D'Alembert",  ReverseDAlembert,  {}),
    ("Reverse Fibonacci",   ReverseFibonacci,  {}),
    ("Reverse Labouchere",  ReverseLabouchere, {"starting_list": [1, 2, 3]}),
    ("Percentage",          Percentage,        {}),
    ("Hollandish",          Hollandish,        {}),
    ("Momentum Shift",      MomentumShift,     {}),
]


# ============================================================
# SIMULATOR
# ============================================================

def simulate_session(strategy, session_outcomes, bankroll, stop_loss, vault_target=0):
    """Simulate one session with a given strategy and pre-generated outcomes."""
    profit = 0.0
    peak = 0.0
    max_drawdown = 0.0
    hands = 0
    vault_total = 0.0
    vaults = 0

    for payout, _, label in session_outcomes:
        balance = bankroll + profit
        if balance <= 0:
            break

        bet = min(strategy.bet, balance)
        if bet <= 0:
            break

        hands += 1
        hand_profit = bet * payout
        profit += hand_profit

        if profit > peak:
            peak = profit
        dd = peak - profit
        if dd > max_drawdown:
            max_drawdown = dd

        if profit <= -stop_loss:
            return {
                'profit': profit, 'bust': True, 'hands': hands,
                'max_dd': max_drawdown, 'peak': peak,
                'vault_total': vault_total, 'vaults': vaults,
            }

        is_win = payout > 0
        is_loss = payout < 0
        strategy.update(payout, is_win, is_loss, bankroll + profit)

        # Vault-and-continue: bank profits when at base bet
        if vault_target > 0 and profit >= vault_target and strategy.bet <= strategy.unit * 1.01:
            vault_total += profit
            vaults += 1
            profit = 0.0
            peak = 0.0
            strategy.reset()

    return {
        'profit': profit, 'bust': False, 'hands': hands,
        'max_dd': max_drawdown, 'peak': peak,
        'vault_total': vault_total, 'vaults': vaults,
    }


def run_comparison(strategies, num_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed, vault_target=0):
    """Run all strategies against identical outcome sequences."""
    unit = bankroll / divider
    max_bet = unit * max_mult

    results = {name: [] for name, _, _ in strategies}

    t0 = time.time()
    for s in range(num_sessions):
        if s % 500 == 0 and s > 0:
            elapsed = time.time() - t0
            rate = s / elapsed
            eta = (num_sessions - s) / rate
            print(f"\r  Session {s:,}/{num_sessions:,} ({elapsed:.1f}s, ~{eta:.0f}s left)   ", end='', flush=True)

        # Deterministic seed per session — all strategies see identical outcomes
        random.seed(seed * 100000 + s)
        session_outcomes = [random_outcome() for _ in range(max_hands)]

        for name, cls, kwargs in strategies:
            strat = cls(unit=unit, max_bet=max_bet, bankroll=bankroll, **kwargs)
            result = simulate_session(strat, session_outcomes, bankroll, stop_loss, vault_target)
            results[name].append(result)

    elapsed = time.time() - t0
    print(f"\r  Done: {num_sessions:,} sessions in {elapsed:.1f}s" + " " * 30)
    return results


# ============================================================
# STATISTICS & OUTPUT
# ============================================================

def aggregate(results):
    """Compute summary statistics for a list of session results."""
    # Net = vault_total + remaining profit (what you walk away with)
    nets = sorted([r.get('vault_total', 0) + r['profit'] for r in results])
    profits = sorted([r['profit'] for r in results])
    n = len(nets)
    busts = sum(1 for r in results if r['bust'])
    wins = sum(1 for r in results if r.get('vault_total', 0) + r['profit'] > 0)
    avg_vaults = sum(r.get('vaults', 0) for r in results) / n
    avg_vaulted = sum(r.get('vault_total', 0) for r in results) / n

    return {
        'mean':      sum(nets) / n,
        'median':    nets[n // 2],
        'p5':        nets[n // 20],
        'p10':       nets[n // 10],
        'p25':       nets[n // 4],
        'p75':       nets[3 * n // 4],
        'p90':       nets[9 * n // 10],
        'p95':       nets[19 * n // 20],
        'best':      nets[-1],
        'worst':     nets[0],
        'bust_pct':  busts / n * 100,
        'win_pct':   wins / n * 100,
        'avg_dd':    sum(r['max_dd'] for r in results) / n,
        'avg_hands': sum(r['hands'] for r in results) / n,
        'avg_peak':  sum(r['peak'] for r in results) / n,
        'avg_vaults': avg_vaults,
        'avg_vaulted': avg_vaulted,
    }


def print_phase1_table(results_dict, bankroll, divider, max_mult, stop_loss, num_sessions, max_hands, seed):
    """Print ranked comparison table."""
    agg = {}
    for name, results in results_dict.items():
        agg[name] = aggregate(results)

    ranked = sorted(agg.items(), key=lambda x: x[1]['median'], reverse=True)

    print()
    print("=" * 115)
    print("  PHASE 1: HEAD-TO-HEAD COMPARISON")
    print(f"  {len(ranked)} strategies x {num_sessions:,} sessions x {max_hands:,} hands | Seed: {seed}")
    print(f"  Bankroll: ${bankroll:,.0f} | Unit: ${bankroll/divider:.2f} (div={divider}) | Cap: {max_mult}x | Stop: -${stop_loss}")
    print("=" * 115)
    print()
    print(f"{'Rank':>4}  {'Strategy':<22} {'Mean':>9} {'MEDIAN':>9} {'P10':>8} {'P90':>8} {'Bust%':>6} {'Win%':>6} {'AvgDD':>8} {'Hands':>6}")
    print(f"{'':>4}  {'':>22} {'':>9} {'':>9} {'':>8} {'':>8} {'':>6} {'':>6} {'':>8} {'':>6}")

    for rank, (name, st) in enumerate(ranked, 1):
        marker = " ***" if st['median'] > 0 else ""
        print(
            f"{rank:>4}  {name:<22}"
            f" ${st['mean']:>+8.2f}"
            f" ${st['median']:>+8.2f}"
            f" ${st['p10']:>+7.0f}"
            f" ${st['p90']:>+7.0f}"
            f" {st['bust_pct']:>5.1f}%"
            f" {st['win_pct']:>5.1f}%"
            f" ${st['avg_dd']:>7.0f}"
            f" {st['avg_hands']:>5.0f}"
            f"{marker}"
        )

    print()
    print("  *** = positive median (more than half of sessions profitable)")
    print()
    return ranked


# ============================================================
# PHASE 2: PARAMETER SWEEPS
# ============================================================

def run_phase2(top5, num_sessions, max_hands, bankroll, stop_loss, seed):
    """Sweep dividers and strategy-specific variants."""
    print()
    print("=" * 115)
    print(f"  PHASE 2: PARAMETER SWEEPS ({num_sessions:,} sessions each)")
    print("=" * 115)

    # --- 2A: Divider x Cap sweep for top 5 ---
    print("\n  2A: DIVIDER x CAP SWEEP (top 5 strategies)")
    dividers = [500, 1000, 2000, 5000]
    caps = [10, 20]

    for div in dividers:
        for cap in caps:
            results = run_comparison(top5, num_sessions, max_hands, bankroll, div, cap, stop_loss, seed)

            items = []
            for name, res_list in results.items():
                st = aggregate(res_list)
                items.append((name, st))
            items.sort(key=lambda x: x[1]['median'], reverse=True)

            print(f"\n  div={div}, cap={cap}x, unit=${bankroll/div:.2f}")
            print(f"  {'Strategy':<22} {'Mean':>9} {'Median':>9} {'Bust%':>6} {'Win%':>6} {'AvgDD':>8}")
            for name, st in items:
                print(
                    f"  {name:<22}"
                    f" ${st['mean']:>+8.2f}"
                    f" ${st['median']:>+8.2f}"
                    f" {st['bust_pct']:>5.1f}%"
                    f" {st['win_pct']:>5.1f}%"
                    f" ${st['avg_dd']:>7.0f}"
                )

    # --- 2B: Strategy-specific variants ---
    print(f"\n{'─'*115}")
    print("  2B: STRATEGY-SPECIFIC VARIANTS (div=2000, cap=10x)")
    print(f"{'─'*115}")

    variants = [
        # Paroli win-cap variants
        ("Paroli-2",              Paroli,            {"limit": 2}),
        ("Paroli-3",              Paroli,            {"limit": 3}),
        ("Paroli-4",              Paroli,            {"limit": 4}),
        # 1-3-2-6 family
        ("1-3-2-6",               System1326,        {"sequence": [1, 3, 2, 6]}),
        ("1-3-2-4",               System1326,        {"sequence": [1, 3, 2, 4]}),
        ("1-2-3-5",               System1326,        {"sequence": [1, 2, 3, 5]}),
        # Labouchere starting lists
        ("Labouch [1,2,3]",       Labouchere,        {"starting_list": [1, 2, 3]}),
        ("Labouch [1,1,1,1]",     Labouchere,        {"starting_list": [1, 1, 1, 1]}),
        ("Labouch [1,2,3,4,5]",   Labouchere,        {"starting_list": [1, 2, 3, 4, 5]}),
        # Momentum Shift threshold variants
        ("MS rec=3/1 cap=3/2",    MomentumShift,     {"recovery_threshold": 3, "recovery_exit": 1, "cap_streak": 3, "cap_max": 2}),
        ("MS rec=5/2 cap=3/2",    MomentumShift,     {"recovery_threshold": 5, "recovery_exit": 2, "cap_streak": 3, "cap_max": 2}),
        ("MS rec=8/3 cap=3/2",    MomentumShift,     {"recovery_threshold": 8, "recovery_exit": 3, "cap_streak": 3, "cap_max": 2}),
        ("MS rec=5/2 cap=2/2",    MomentumShift,     {"recovery_threshold": 5, "recovery_exit": 2, "cap_streak": 2, "cap_max": 2}),
        ("MS rec=5/2 cap=3/3",    MomentumShift,     {"recovery_threshold": 5, "recovery_exit": 2, "cap_streak": 3, "cap_max": 3}),
        ("MS rec=5/2 cap=4/2",    MomentumShift,     {"recovery_threshold": 5, "recovery_exit": 2, "cap_streak": 4, "cap_max": 2}),
    ]

    results = run_comparison(variants, num_sessions, max_hands, bankroll, 2000, 10, stop_loss, seed)

    items = []
    for name, res_list in results.items():
        st = aggregate(res_list)
        items.append((name, st))
    items.sort(key=lambda x: x[1]['median'], reverse=True)

    print(f"\n  {'Variant':<22} {'Mean':>9} {'Median':>9} {'Bust%':>6} {'Win%':>6} {'AvgDD':>8} {'P10':>8} {'P90':>8}")
    for name, st in items:
        marker = " *" if st['median'] > 0 else ""
        print(
            f"  {name:<22}"
            f" ${st['mean']:>+8.2f}"
            f" ${st['median']:>+8.2f}"
            f" {st['bust_pct']:>5.1f}%"
            f" {st['win_pct']:>5.1f}%"
            f" ${st['avg_dd']:>7.0f}"
            f" ${st['p10']:>+7.0f}"
            f" ${st['p90']:>+7.0f}"
            f"{marker}"
        )


# ============================================================
# PHASE 3: DETAILED ANALYSIS
# ============================================================

def run_phase3(top3, num_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed):
    """Percentile distribution and risk metrics for top strategies."""
    unit = bankroll / divider
    max_bet = unit * max_mult

    print()
    print("=" * 115)
    print(f"  PHASE 3: DETAILED ANALYSIS (top 3)")
    print(f"  {num_sessions:,} sessions x {max_hands:,} hands | div={divider}, cap={max_mult}x")
    print("=" * 115)

    for name, cls, kwargs in top3:
        results = []
        for s in range(num_sessions):
            random.seed(seed * 100000 + s)
            session_outcomes = [random_outcome() for _ in range(max_hands)]
            strat = cls(unit=unit, max_bet=max_bet, bankroll=bankroll, **kwargs)
            result = simulate_session(strat, session_outcomes, bankroll, stop_loss)
            results.append(result)

        profits = sorted([r['profit'] for r in results])
        dds = sorted([r['max_dd'] for r in results])
        peaks = sorted([r['peak'] for r in results])
        n = len(results)
        busts = sum(1 for r in results if r['bust'])

        print(f"\n  {name}")
        print(f"  {'='*50}")
        print(f"  Sessions:      {n:,}")
        print(f"  Bust rate:     {busts/n*100:.2f}% ({busts}/{n})")
        print(f"  Win rate:      {sum(1 for p in profits if p > 0)/n*100:.1f}%")
        print(f"  Break-even:    {sum(1 for p in profits if p == 0)/n*100:.1f}%")
        print(f"  ")
        print(f"  Profit Distribution:")
        print(f"    Worst:       ${profits[0]:>+.2f}")
        print(f"    P5:          ${profits[n//20]:>+.2f}")
        print(f"    P10:         ${profits[n//10]:>+.2f}")
        print(f"    P25:         ${profits[n//4]:>+.2f}")
        print(f"    MEDIAN:      ${profits[n//2]:>+.2f}")
        print(f"    P75:         ${profits[3*n//4]:>+.2f}")
        print(f"    P90:         ${profits[9*n//10]:>+.2f}")
        print(f"    P95:         ${profits[19*n//20]:>+.2f}")
        print(f"    Best:        ${profits[-1]:>+.2f}")
        print(f"  ")
        print(f"  Risk Metrics:")
        print(f"    Mean profit: ${sum(profits)/n:>+.2f}")
        print(f"    Std dev:     ${(sum((p - sum(profits)/n)**2 for p in profits)/n)**0.5:.2f}")
        print(f"    Avg peak:    ${sum(peaks)/n:.2f}")
        print(f"    Avg max DD:  ${sum(dds)/n:.2f}")
        print(f"    Worst DD:    ${max(dds):.2f}")
        print(f"    Avg hands:   {sum(r['hands'] for r in results)/n:.0f}")
        print(f"    Sharpe-ish:  {(sum(profits)/n) / max((sum((p - sum(profits)/n)**2 for p in profits)/n)**0.5, 0.01):.3f}")


# ============================================================
# PHASE 4: VAULT-AND-CONTINUE COMPARISON
# ============================================================

def run_vault_comparison(strategies, num_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed):
    """Test how vault-and-continue changes strategy performance."""
    vault_targets = [0, 25, 50, 100]

    print()
    print("=" * 115)
    print(f"  PHASE 4: VAULT-AND-CONTINUE COMPARISON")
    print(f"  {num_sessions:,} sessions x {max_hands:,} hands | div={divider}, cap={max_mult}x")
    print(f"  Vault targets: {vault_targets} | Vault only when bet = unit (safe state)")
    print("=" * 115)

    # Collect results for all strategy × vault_target combos
    all_data = {}  # {strategy_name: {vault_target: aggregate_stats}}

    for vt in vault_targets:
        label = f"vault=${vt}" if vt > 0 else "no vault"
        print(f"\n  Running: {label}...")
        results = run_comparison(strategies, num_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed, vault_target=vt)

        for name, res_list in results.items():
            if name not in all_data:
                all_data[name] = {}
            all_data[name][vt] = aggregate(res_list)

    # Print comparison table
    print(f"\n{'─'*115}")
    print(f"  VAULT IMPACT SUMMARY (net = vaulted + remaining profit)")
    print(f"{'─'*115}")

    # Header
    header = f"  {'Strategy':<22}"
    for vt in vault_targets:
        label = "No Vault" if vt == 0 else f"Vault ${vt}"
        header += f" | {label:>30}"
    print(header)

    subheader = f"  {'':22}"
    for _ in vault_targets:
        subheader += f" | {'Median':>8} {'Bust%':>6} {'Win%':>6} {'Vaults':>6}"
    print(subheader)
    print(f"  {'─'*22}" + (" |" + " " + "─" * 29) * len(vault_targets))

    # Sort strategies by best vault median
    strat_order = sorted(all_data.keys(), key=lambda n: max(all_data[n][vt]['median'] for vt in vault_targets), reverse=True)

    for name in strat_order:
        row = f"  {name:<22}"
        for vt in vault_targets:
            st = all_data[name][vt]
            row += f" | ${st['median']:>+7.2f} {st['bust_pct']:>5.1f}% {st['win_pct']:>5.1f}% {st['avg_vaults']:>5.1f}"
        print(row)

    # Best combo
    best_name, best_vt, best_med = "", 0, -99999
    for name in all_data:
        for vt in vault_targets:
            med = all_data[name][vt]['median']
            if med > best_med:
                best_med = med
                best_name = name
                best_vt = vt

    best_bust = all_data[best_name][best_vt]['bust_pct']
    print(f"\n  BEST COMBO: {best_name} + vault ${best_vt} → median ${best_med:+.2f}, bust {best_bust:.1f}%")

    return all_data


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    phase1_only = "--phase1" in sys.argv

    num_sessions = 2000 if quick else 10000
    for i, arg in enumerate(sys.argv):
        if arg == "--sessions" and i + 1 < len(sys.argv):
            num_sessions = int(sys.argv[i + 1])

    max_hands = 2000
    bankroll = 1000
    divider = 2000
    max_mult = 10
    stop_loss = 300
    seed = 42

    print()
    print("=" * 115)
    print("  BLACKJACK STRATEGY COMPARISON — Monte Carlo Simulator v2.0")
    print(f"  {len(DEFAULT_STRATEGIES)} strategies | {num_sessions:,} sessions x {max_hands:,} hands per session")
    print(f"  Bankroll: ${bankroll:,.0f} | Stop loss: -${stop_loss} | Seed: {seed} (identical outcomes for all)")
    print(f"  All strategies are -EV. This comparison measures VARIANCE MANAGEMENT, not edge.")
    print("=" * 115)
    print()

    verify_model()

    # Phase 1
    print(f"\n  PHASE 1: Running {len(DEFAULT_STRATEGIES)} strategies head-to-head...")
    results = run_comparison(
        DEFAULT_STRATEGIES, num_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed
    )
    ranked = print_phase1_table(
        results, bankroll, divider, max_mult, stop_loss, num_sessions, max_hands, seed
    )

    if phase1_only:
        print("  (--phase1 flag: skipping phases 2 & 3)")
        sys.exit(0)

    # Phase 2: parameter sweeps
    top5_names = [name for name, _ in ranked[:5]]
    top5 = [(n, c, k) for n, c, k in DEFAULT_STRATEGIES if n in top5_names]

    phase2_sessions = max(num_sessions // 2, 1000)
    run_phase2(top5, phase2_sessions, max_hands, bankroll, stop_loss, seed)

    # Phase 3: detailed analysis of top 3
    top3_names = [name for name, _ in ranked[:3]]
    top3 = [(n, c, k) for n, c, k in DEFAULT_STRATEGIES if n in top3_names]

    run_phase3(top3, num_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed)

    # Phase 4: vault-and-continue comparison (top 5)
    vault_sessions = max(num_sessions // 2, 1000)
    run_vault_comparison(top5, vault_sessions, max_hands, bankroll, divider, max_mult, stop_loss, seed)

    print()
    print("=" * 115)
    print("  SIMULATION COMPLETE")
    print(f"  Top strategy by median: {ranked[0][0]} (${ranked[0][1]['median']:+.2f})")
    print(f"  Safest (lowest bust):   {min(ranked, key=lambda x: x[1]['bust_pct'])[0]}"
          f" ({min(ranked, key=lambda x: x[1]['bust_pct'])[1]['bust_pct']:.1f}%)")
    print(f"  Highest win rate:       {max(ranked, key=lambda x: x[1]['win_pct'])[0]}"
          f" ({max(ranked, key=lambda x: x[1]['win_pct'])[1]['win_pct']:.1f}%)")
    print("=" * 115)
