#!/usr/bin/env python3
"""
MAMBA Improvements Test — Trailing Stop, Bet Cap, Declining IOL
Tests three improvements individually and in combination.

Usage:
  python3 mamba-improvements.py          # Full (5k sessions)
  python3 mamba-improvements.py --quick  # Quick (2k sessions)
"""

import random
import sys
from itertools import product

CHANCE = 65
WIN_PROB = CHANCE / 100.0
WIN_PAYOUT = 99.0 / CHANCE - 1.0


class MambaBase:
    """Pure MAMBA baseline: constant IOL 3.0x."""
    def __init__(self, base, iol=3.0):
        self.base = base
        self.iol = iol
        self.bet = base
        self.mult = 1.0

    def on_win(self):
        self.mult = 1.0
        self.bet = self.base

    def on_loss(self, balance):
        self.mult *= self.iol
        self.bet = self.base * self.mult
        # Soft bust
        if self.bet > balance * 0.95:
            self.mult = 1.0
            self.bet = self.base


class MambaTrailingStop:
    """MAMBA + Trailing stop: lock profits when they decline."""
    def __init__(self, base, iol=3.0):
        self.base = base
        self.iol = iol
        self.bet = base
        self.mult = 1.0

    def on_win(self):
        self.mult = 1.0
        self.bet = self.base

    def on_loss(self, balance):
        self.mult *= self.iol
        self.bet = self.base * self.mult
        if self.bet > balance * 0.95:
            self.mult = 1.0
            self.bet = self.base


class MambaBetCap:
    """MAMBA + Percentage bet cap: never bet more than X% of balance."""
    def __init__(self, base, iol=3.0, cap_pct=10):
        self.base = base
        self.iol = iol
        self.cap_pct = cap_pct
        self.bet = base
        self.mult = 1.0

    def on_win(self):
        self.mult = 1.0
        self.bet = self.base

    def on_loss(self, balance):
        self.mult *= self.iol
        self.bet = self.base * self.mult
        # Percentage cap
        max_bet = balance * self.cap_pct / 100
        if self.bet > max_bet:
            self.bet = max_bet
        # Soft bust
        if self.bet > balance * 0.95:
            self.mult = 1.0
            self.bet = self.base


class MambaDecliningIOL:
    """MAMBA + Declining IOL: lower multiplier at deep loss streaks."""
    def __init__(self, base, iol_schedule=None):
        self.base = base
        # Default: aggressive early, defensive late
        self.iol_schedule = iol_schedule or [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5]
        self.bet = base
        self.mult = 1.0
        self.ls = 0

    def on_win(self):
        self.mult = 1.0
        self.bet = self.base
        self.ls = 0

    def on_loss(self, balance):
        idx = min(self.ls, len(self.iol_schedule) - 1)
        iol = self.iol_schedule[idx]
        self.ls += 1
        self.mult *= iol
        self.bet = self.base * self.mult
        if self.bet > balance * 0.95:
            self.mult = 1.0
            self.bet = self.base
            self.ls = 0


class MambaCombo:
    """MAMBA + All three improvements combined."""
    def __init__(self, base, iol_schedule=None, cap_pct=10):
        self.base = base
        self.iol_schedule = iol_schedule or [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5]
        self.cap_pct = cap_pct
        self.bet = base
        self.mult = 1.0
        self.ls = 0

    def on_win(self):
        self.mult = 1.0
        self.bet = self.base
        self.ls = 0

    def on_loss(self, balance):
        idx = min(self.ls, len(self.iol_schedule) - 1)
        iol = self.iol_schedule[idx]
        self.ls += 1
        self.mult *= iol
        self.bet = self.base * self.mult
        # Percentage cap
        max_bet = balance * self.cap_pct / 100
        if self.bet > max_bet:
            self.bet = max_bet
        # Soft bust
        if self.bet > balance * 0.95:
            self.mult = 1.0
            self.bet = self.base
            self.ls = 0


def sim(strat_fn, bank=1000, num=5000, max_bets=10000, seed=42,
        stop_pct=15, trailing_stop=False, trail_activate_pct=5, trail_lock_pct=50):
    """
    Simulate with optional trailing stop.
    trailing_stop: enable trailing stop
    trail_activate_pct: % profit to activate trailing stop
    trail_lock_pct: % of peak profit as the floor (stop if profit drops below)
    """
    pnls = []
    busts = 0
    trail_stops = 0
    target_stops = 0
    total_bets = 0
    max_bets_in_session = 0

    for s in range(num):
        random.seed(seed * 100000 + s)
        st = strat_fn()
        profit = 0.0
        peak_profit = 0.0
        bets = 0
        stop_thresh = bank * stop_pct / 100
        trail_active = False
        trail_floor = 0.0

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            bet = st.bet
            if bet > bal:
                bet = bal
            if bet < 0.001:
                busts += 1
                break

            bets += 1
            won = random.random() < WIN_PROB
            if won:
                profit += bet * WIN_PAYOUT
                st.on_win()
            else:
                profit -= bet
                new_bal = bank + profit
                if new_bal <= 0:
                    busts += 1
                    break
                st.on_loss(new_bal)

            # Track peak
            if profit > peak_profit:
                peak_profit = profit

            # Trailing stop logic
            if trailing_stop:
                activate_thresh = bank * trail_activate_pct / 100
                if not trail_active and profit >= activate_thresh:
                    trail_active = True
                if trail_active:
                    trail_floor = peak_profit * trail_lock_pct / 100
                    if profit <= trail_floor and st.mult <= 1.01:
                        trail_stops += 1
                        break

            # Fixed stop
            if stop_thresh > 0 and profit >= stop_thresh and st.mult <= 1.01:
                target_stops += 1
                break

        total_bets += bets
        if bets > max_bets_in_session:
            max_bets_in_session = bets
        pnls.append(profit)

    pnls.sort()
    n = len(pnls)
    return {
        'median': pnls[n // 2],
        'mean': sum(pnls) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n * 100,
        'p10': pnls[n // 10],
        'p90': pnls[9 * n // 10],
        'avg_bets': total_bets / n,
        'trail_stops': trail_stops,
        'target_stops': target_stops,
    }


def pr(tag, r, bl=None):
    m = " **" if bl and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 10 / 60
    ts = f" ts={r['trail_stops']}" if r.get('trail_stops', 0) > 0 else ""
    print(f"  {tag:<55} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {t:>5.1f}m{ts}{m}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    base = bank / 10000

    H = (f"  {'Config':<55} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Tm':>6}")
    S = (f"  {'─'*55} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*6}")

    print()
    print("=" * 120)
    print("  MAMBA IMPROVEMENTS — Trailing Stop / Bet Cap / Declining IOL")
    print(f"  {num:,} sessions | D65 div=10000 | ${bank:,}")
    print("=" * 120)

    for stop in [8, 10, 15, 20, 30]:
        print(f"\n  {'='*60}")
        print(f"  STOP = {stop}%")
        print(f"  {'='*60}")

        # === BASELINE ===
        print(f"\n  --- Baseline ---")
        print(H); print(S)
        r_bl = sim(lambda: MambaBase(base), bank, num, seed=seed, stop_pct=stop)
        pr("MAMBA Pure IOL 3.0x", r_bl)
        bl = r_bl['median']

        # === IMPROVEMENT 1: TRAILING STOP ===
        print(f"\n  --- Trailing Stop (activate at X%, lock Y% of peak) ---")
        print(H); print(S)

        for act, lock in [(3, 40), (3, 50), (3, 60), (5, 40), (5, 50), (5, 60),
                          (5, 70), (8, 50), (8, 60), (10, 50)]:
            tag = f"Trailing: activate@{act}% lock@{lock}%"
            r = sim(lambda: MambaBase(base), bank, num, seed=seed, stop_pct=stop,
                    trailing_stop=True, trail_activate_pct=act, trail_lock_pct=lock)
            pr(tag, r, bl)

        # === IMPROVEMENT 2: BET CAP ===
        print(f"\n  --- Percentage Bet Cap ---")
        print(H); print(S)

        for cap in [5, 8, 10, 15, 20, 30, 50]:
            tag = f"Bet cap {cap}% of balance"
            r = sim(lambda c=cap: MambaBetCap(base, 3.0, c), bank, num, seed=seed, stop_pct=stop)
            pr(tag, r, bl)

        # === IMPROVEMENT 3: DECLINING IOL ===
        print(f"\n  --- Declining IOL ---")
        print(H); print(S)

        schedules = [
            ([3.0]*9, "Constant 3.0x (baseline)"),
            ([3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5], "3.0x4→2.0x2→1.5x3"),
            ([3.0, 3.0, 3.0, 2.5, 2.0, 1.5, 1.5, 1.5, 1.5], "3.0x3→2.5→2.0→1.5x4"),
            ([3.0, 3.0, 2.5, 2.0, 2.0, 1.5, 1.5, 1.0, 1.0], "3.0x2→2.5→2.0x2→1.5x2→flat"),
            ([3.0, 3.0, 3.0, 3.0, 3.0, 2.0, 1.5, 1.0, 1.0], "3.0x5→2.0→1.5→flat×2"),
            ([2.5, 2.5, 2.5, 2.5, 2.0, 2.0, 1.5, 1.5, 1.5], "2.5x4→2.0x2→1.5x3"),
            ([3.5, 3.0, 2.5, 2.0, 1.5, 1.5, 1.0, 1.0, 1.0], "3.5→3.0→2.5→2.0→1.5x2→flat"),
            ([3.0, 3.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.0, 1.0], "3.0x4→flat (hard brake@5)"),
        ]

        for sched, label in schedules:
            tag = f"IOL: {label}"
            r = sim(lambda s=sched: MambaDecliningIOL(base, s), bank, num, seed=seed, stop_pct=stop)
            pr(tag, r, bl)

        # === COMBOS ===
        print(f"\n  --- Best Combos ---")
        print(H); print(S)

        combos = [
            ("Trail@5/50 + Cap10%",
             lambda: MambaBetCap(base, 3.0, 10),
             True, 5, 50),
            ("Trail@5/50 + Cap15%",
             lambda: MambaBetCap(base, 3.0, 15),
             True, 5, 50),
            ("Trail@5/60 + Cap10%",
             lambda: MambaBetCap(base, 3.0, 10),
             True, 5, 60),
            ("Trail@3/50 + DeclIOL",
             lambda: MambaDecliningIOL(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5]),
             True, 3, 50),
            ("Trail@5/50 + DeclIOL",
             lambda: MambaDecliningIOL(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5]),
             True, 5, 50),
            ("Trail@5/50 + DeclIOL + Cap10%",
             lambda: MambaCombo(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5], 10),
             True, 5, 50),
            ("Trail@5/50 + DeclIOL + Cap15%",
             lambda: MambaCombo(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5], 15),
             True, 5, 50),
            ("Trail@5/60 + DeclIOL + Cap10%",
             lambda: MambaCombo(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5], 10),
             True, 5, 60),
            ("Cap10% + DeclIOL (no trail)",
             lambda: MambaCombo(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5], 10),
             False, 0, 0),
            ("Cap15% + DeclIOL (no trail)",
             lambda: MambaCombo(base, [3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.5, 1.5, 1.5], 15),
             False, 0, 0),
        ]

        for label, fn, ts, ta, tl in combos:
            r = sim(fn, bank, num, seed=seed, stop_pct=stop,
                    trailing_stop=ts, trail_activate_pct=ta, trail_lock_pct=tl)
            pr(label, r, bl)

    # === SUMMARY across stop levels ===
    print()
    print("=" * 120)
    print("  SUMMARY — Best config per stop level")
    print("=" * 120)

    for stop in [8, 10, 15, 20]:
        all_configs = []

        # Baseline
        r = sim(lambda: MambaBase(base), bank, num, seed=seed, stop_pct=stop)
        all_configs.append(("Baseline", r))

        # Best trailing
        r = sim(lambda: MambaBase(base), bank, num, seed=seed, stop_pct=stop,
                trailing_stop=True, trail_activate_pct=5, trail_lock_pct=50)
        all_configs.append(("Trail@5/50", r))

        # Best cap
        r = sim(lambda: MambaBetCap(base, 3.0, 10), bank, num, seed=seed, stop_pct=stop)
        all_configs.append(("Cap10%", r))

        # Best declining
        r = sim(lambda: MambaDecliningIOL(base, [3.0,3.0,3.0,3.0,2.0,2.0,1.5,1.5,1.5]),
                bank, num, seed=seed, stop_pct=stop)
        all_configs.append(("DeclIOL", r))

        # Best combo
        r = sim(lambda: MambaCombo(base, [3.0,3.0,3.0,3.0,2.0,2.0,1.5,1.5,1.5], 10),
                bank, num, seed=seed, stop_pct=stop,
                trailing_stop=True, trail_activate_pct=5, trail_lock_pct=50)
        all_configs.append(("Trail+Decl+Cap10", r))

        print(f"\n  Stop={stop}%:")
        print(f"  {'Config':<25} {'Median':>9} {'Mean':>9} {'Bust%':>6} {'Win%':>6} {'P10':>9}")
        print(f"  {'─'*25} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9}")
        for label, r in all_configs:
            print(f"  {label:<25} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} {r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% ${r['p10']:>+8.2f}")
    print("=" * 120)
