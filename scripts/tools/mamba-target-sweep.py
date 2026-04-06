#!/usr/bin/env python3
"""
MAMBA Target Sweep — Variable multiplier targets during different modes
Tests dynamic target switching: base target for IOL, different target for capitalize.
Also tests: variable base target (not just 65%), dual-target strategies, and
progressive target systems.

Usage:
  python3 mamba-target-sweep.py          # Full (5k sessions)
  python3 mamba-target-sweep.py --quick  # Quick (2k sessions)
"""

import random
import sys
import time
from itertools import product


# ============================================================
# DICE HELPERS
# ============================================================

def win_payout(chance):
    """Net payout fraction: 99/chance - 1"""
    return 99.0 / chance - 1.0


# ============================================================
# STRATEGIES
# ============================================================

class MambaBase:
    """Pure MAMBA: single target, IOL on loss."""
    def __init__(self, base, iol, chance):
        self.base = base
        self.iol = iol
        self.chance = chance
        self.wp = chance / 100.0
        self.payout = win_payout(chance)
        self.bet = base
        self.ws = 0

    def get_bet_and_chance(self):
        return self.bet, self.chance

    def update(self, won):
        if won:
            self.ws += 1
            self.bet = self.base
        else:
            self.ws = 0
            self.bet *= self.iol


class MambaCapTarget:
    """
    MAMBA + Capitalize with TARGET SWITCHING.
    Base mode: chance_base (e.g., 65%) with IOL
    Cap mode: chance_cap (e.g., 50%, 33%) with bet multiplier
    """
    def __init__(self, base, iol, chance_base, chance_cap,
                 cap_streak=3, cap_max=3, cap_bet_mult=1.0):
        self.base = base
        self.iol = iol
        self.chance_base = chance_base
        self.chance_cap = chance_cap
        self.wp_base = chance_base / 100.0
        self.wp_cap = chance_cap / 100.0
        self.payout_base = win_payout(chance_base)
        self.payout_cap = win_payout(chance_cap)
        self.cap_streak = cap_streak
        self.cap_max = cap_max
        self.cap_bet_mult = cap_bet_mult  # bet size multiplier during cap
        self.bet = base
        self.ws = 0
        self.mode = 'strike'
        self.cap_count = 0
        self.active_chance = chance_base

    def get_bet_and_chance(self):
        return self.bet, self.active_chance

    def update(self, won):
        if won:
            self.ws += 1
        else:
            self.ws = 0

        if self.mode == 'strike':
            if won:
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'cap'
                    self.cap_count = 0
                    self.bet = self.base * self.cap_bet_mult
                    self.active_chance = self.chance_cap
            else:
                self.bet *= self.iol
                self.active_chance = self.chance_base

        elif self.mode == 'cap':
            self.cap_count += 1
            if won:
                if self.cap_count >= self.cap_max:
                    self.mode = 'strike'
                    self.ws = 0
                    self.bet = self.base
                    self.active_chance = self.chance_base
                else:
                    self.bet = min(self.bet * self.cap_bet_mult, self.base * 50)
            else:
                self.mode = 'strike'
                self.ws = 0
                self.bet *= self.iol
                self.active_chance = self.chance_base

        self.bet = max(self.base, self.bet)


class DualTarget:
    """
    Alternating dual-target: switch between two targets.
    Mode A: high chance (safe, IOL recovery)
    Mode B: low chance (high payout, profit extraction)
    Switch to B after N consecutive wins, back to A on any loss.
    """
    def __init__(self, base, iol, chance_safe, chance_risky,
                 switch_streak=3, risky_max=2, risky_bet_mult=1.0):
        self.base = base
        self.iol = iol
        self.chance_safe = chance_safe
        self.chance_risky = chance_risky
        self.switch_streak = switch_streak
        self.risky_max = risky_max
        self.risky_bet_mult = risky_bet_mult
        self.bet = base
        self.ws = 0
        self.mode = 'safe'
        self.risky_count = 0
        self.active_chance = chance_safe

    def get_bet_and_chance(self):
        return self.bet, self.active_chance

    def update(self, won):
        if won:
            self.ws += 1
        else:
            self.ws = 0

        if self.mode == 'safe':
            if won:
                self.bet = self.base
                if self.ws >= self.switch_streak:
                    self.mode = 'risky'
                    self.risky_count = 0
                    self.bet = self.base * self.risky_bet_mult
                    self.active_chance = self.chance_risky
            else:
                self.bet *= self.iol
                self.active_chance = self.chance_safe

        elif self.mode == 'risky':
            self.risky_count += 1
            if won:
                if self.risky_count >= self.risky_max:
                    self.mode = 'safe'
                    self.ws = 0
                    self.bet = self.base
                    self.active_chance = self.chance_safe
                else:
                    self.bet = min(self.bet * self.risky_bet_mult, self.base * 50)
            else:
                self.mode = 'safe'
                self.ws = 0
                self.bet *= self.iol
                self.active_chance = self.chance_safe

        self.bet = max(self.base, self.bet)


class ProgressiveTarget:
    """
    Progressive target: start at high chance, lower target on each consecutive win.
    Each win: target moves toward riskier payout. Any loss: reset to base target + IOL.
    Like a ladder climbing toward higher multipliers on streaks.
    """
    def __init__(self, base, iol, chances, bet_mults=None):
        # chances = [65, 55, 45, 35] — progressive ladder
        self.base = base
        self.iol = iol
        self.chances = chances
        self.bet_mults = bet_mults or [1.0] * len(chances)
        self.bet = base
        self.ws = 0
        self.level = 0
        self.active_chance = chances[0]

    def get_bet_and_chance(self):
        return self.bet, self.active_chance

    def update(self, won):
        if won:
            self.ws += 1
            self.bet = self.base * self.bet_mults[min(self.level, len(self.bet_mults) - 1)]
            self.level = min(self.level + 1, len(self.chances) - 1)
            self.active_chance = self.chances[self.level]
        else:
            self.ws = 0
            self.level = 0
            self.active_chance = self.chances[0]
            self.bet *= self.iol

        self.bet = max(self.base, self.bet)


# ============================================================
# SIMULATOR
# ============================================================

def sim(strat_fn, bank=1000, num=5000, max_bets=10000, seed=42, stop_pct=15):
    pnls = []
    busts = 0
    total_wager = 0
    total_bets = 0

    for s in range(num):
        random.seed(seed * 100000 + s)
        st = strat_fn()
        profit = 0.0
        wagered = 0.0
        bets = 0
        stop_thresh = bank * stop_pct / 100

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            bet, chance = st.get_bet_and_chance()
            wp = chance / 100.0

            if bet > bal * 0.95:
                st.bet = st.base
                st.active_chance = st.chances[0] if hasattr(st, 'chances') else getattr(st, 'chance_base', getattr(st, 'chance_safe', getattr(st, 'chance', 65)))
                bet = st.base
            if bet > bal:
                bet = bal
            if bet < 0.001:
                busts += 1
                break

            wagered += bet
            bets += 1

            won = random.random() < wp
            if won:
                profit += bet * win_payout(chance)
            else:
                profit -= bet

            if bank + profit <= 0:
                busts += 1
                break

            st.update(won)

            if stop_thresh > 0 and profit >= stop_thresh:
                if st.bet <= st.base * 1.5:
                    break

        pnls.append(profit)
        total_wager += wagered
        total_bets += bets

    pnls.sort()
    n = len(pnls)
    return {
        'median': pnls[n // 2],
        'mean': sum(pnls) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n * 100,
        'p10': pnls[n // 10],
        'p90': pnls[9 * n // 10],
        'avg_wager': total_wager / n,
        'avg_bets': total_bets / n,
    }


def pr(tag, r, bl=None):
    m = " **" if bl and r['median'] > bl else (" *" if r['median'] > 0 else "")
    w = r['avg_wager'] / 1000
    t = r['avg_bets'] / 10 / 60
    print(f"  {tag:<55} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {w:>5.1f}x {t:>4.1f}m{m}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    base = bank / 10000

    H = (f"  {'Config':<55} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Wgr':>6} {'Tm':>5}")
    S = (f"  {'─'*55} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*6} {'─'*5}")

    print()
    print("=" * 125)
    print("  MAMBA TARGET SWEEP — Variable Multiplier Strategies")
    print(f"  {num:,} sessions | div=10000 | ${bank:,} | stop=15%")
    print("=" * 125)

    stop = 15

    # ============================================================
    # BASELINES
    # ============================================================
    print("\n  --- BASELINES (single target, pure IOL) ---")
    print(H); print(S)

    for ch in [50, 55, 60, 65, 70, 75, 80]:
        iol = 3.0
        tag = f"Pure IOL {ch}% (payout +{win_payout(ch):.2f}x)"
        r = sim(lambda c=ch: MambaBase(base, iol, c), bank, num, seed=seed, stop_pct=stop)
        pr(tag, r)

    bl65 = sim(lambda: MambaBase(base, 3.0, 65), bank, num, seed=seed, stop_pct=stop)
    bl = bl65['median']
    print(f"\n  Baseline (65% IOL 3.0x): median ${bl:+.2f}")

    # ============================================================
    # CAPITALIZE WITH TARGET SWITCH
    # ============================================================
    print(f"\n  --- CAPITALIZE: SAME BET SIZE, DIFFERENT TARGET ---")
    print(f"  (Base=65%, IOL 3.0x, cap after 3 wins, 3 cap bets, bet=1x base)")
    print(H); print(S)

    pr("Baseline: 65% pure IOL", bl65, bl)
    for cap_ch in [65, 60, 55, 50, 45, 40, 33, 25]:
        tag = f"Cap target {cap_ch}% (+{win_payout(cap_ch):.2f}x) bet=1x"
        r = sim(lambda c=cap_ch: MambaCapTarget(base, 3.0, 65, c, 3, 3, 1.0),
                bank, num, seed=seed, stop_pct=stop)
        pr(tag, r, bl)

    print(f"\n  --- CAPITALIZE: HIGHER TARGET + BIGGER BET ---")
    print(H); print(S)

    for cap_ch, cap_bm in product([65, 50, 40, 33], [1.0, 2.0, 3.0]):
        tag = f"Cap {cap_ch}% bet={cap_bm}x (s3/c3)"
        r = sim(lambda c=cap_ch, b=cap_bm: MambaCapTarget(base, 3.0, 65, c, 3, 3, b),
                bank, num, seed=seed, stop_pct=stop)
        pr(tag, r, bl)

    # ============================================================
    # DUAL TARGET STRATEGY
    # ============================================================
    print(f"\n  --- DUAL TARGET: SAFE MODE + RISKY MODE ---")
    print(f"  (Safe=IOL recovery, Risky=profit extraction on streaks)")
    print(H); print(S)

    for safe_ch, risky_ch, streak, rmax, rbm in [
        (65, 50, 3, 2, 1.0),
        (65, 50, 3, 2, 2.0),
        (65, 40, 3, 2, 1.0),
        (65, 40, 3, 2, 2.0),
        (65, 33, 3, 2, 1.0),
        (65, 33, 3, 1, 2.0),
        (70, 50, 3, 2, 1.0),
        (70, 40, 3, 2, 1.0),
        (70, 50, 3, 2, 2.0),
        (75, 50, 3, 2, 1.0),
        (75, 40, 3, 2, 1.0),
        (75, 33, 3, 1, 1.0),
        (80, 50, 3, 2, 1.0),
        (80, 40, 3, 2, 1.0),
        (65, 50, 2, 3, 1.0),
        (65, 50, 4, 2, 1.0),
        (65, 25, 3, 1, 1.0),  # sniper: 4x target for 1 bet
        (65, 10, 3, 1, 1.0),  # ultra sniper: 9.9x target for 1 bet
        (75, 25, 4, 1, 1.0),  # conservative base, sniper cap
    ]:
        tag = f"Dual {safe_ch}%/{risky_ch}% s{streak}/r{rmax}/b{rbm}x"
        r = sim(lambda sc=safe_ch, rc=risky_ch, st=streak, rm=rmax, rb=rbm:
                DualTarget(base, 3.0, sc, rc, st, rm, rb),
                bank, num, seed=seed, stop_pct=stop)
        pr(tag, r, bl)

    # ============================================================
    # PROGRESSIVE TARGET LADDER
    # ============================================================
    print(f"\n  --- PROGRESSIVE TARGET LADDER ---")
    print(f"  (Each consecutive win moves to riskier target)")
    print(H); print(S)

    ladders = [
        ([65, 60, 55, 50], [1, 1, 1, 1], "65→60→55→50 flat"),
        ([65, 55, 45, 35], [1, 1, 1, 1], "65→55→45→35 flat"),
        ([65, 50, 33, 25], [1, 1, 1, 1], "65→50→33→25 flat"),
        ([65, 65, 50, 50], [1, 1, 2, 2], "65→65→50→50 +bet"),
        ([65, 65, 65, 50], [1, 1, 1, 2], "65x3→50x2 +bet"),
        ([70, 60, 50, 40], [1, 1, 1, 1], "70→60→50→40 flat"),
        ([75, 65, 50, 33], [1, 1, 1, 1], "75→65→50→33 flat"),
        ([75, 75, 50, 50], [1, 1, 2, 2], "75x2→50x2 +bet"),
        ([80, 65, 50, 33], [1, 1, 1, 1], "80→65→50→33 flat"),
        ([65, 50, 50, 50], [1, 2, 2, 2], "65→50 bet ramp"),
        ([65, 65, 33, 33], [1, 1, 1, 1], "65x2→33x2 sniper"),
        ([75, 50, 25], [1, 1, 1], "75→50→25 3-step"),
        ([80, 50, 25], [1, 1, 1], "80→50→25 3-step"),
        ([65, 40, 20, 10], [1, 1, 1, 1], "65→40→20→10 deep sniper"),
    ]

    for chances, mults, label in ladders:
        tag = f"Ladder: {label}"
        r = sim(lambda c=chances, m=mults: ProgressiveTarget(base, 3.0, c, m),
                bank, num, seed=seed, stop_pct=stop)
        pr(tag, r, bl)

    # ============================================================
    # FULL SWEEP: best ideas across stop%
    # ============================================================
    print(f"\n  --- BEST IDEAS ACROSS STOP LEVELS ---")

    best_ideas = [
        ("Pure 65% IOL", lambda: MambaBase(base, 3.0, 65)),
        ("Cap 65%→65% bet=3x s3c3", lambda: MambaCapTarget(base, 3.0, 65, 65, 3, 3, 3.0)),
        ("Cap 65%→50% bet=1x s3c3", lambda: MambaCapTarget(base, 3.0, 65, 50, 3, 3, 1.0)),
        ("Cap 65%→50% bet=2x s3c3", lambda: MambaCapTarget(base, 3.0, 65, 50, 3, 3, 2.0)),
        ("Cap 65%→33% bet=1x s3c3", lambda: MambaCapTarget(base, 3.0, 65, 33, 3, 3, 1.0)),
        ("Dual 65/50 s3r2 bet=1x", lambda: DualTarget(base, 3.0, 65, 50, 3, 2, 1.0)),
        ("Dual 75/40 s3r2 bet=1x", lambda: DualTarget(base, 3.0, 75, 40, 3, 2, 1.0)),
        ("Ladder 65→55→45→35", lambda: ProgressiveTarget(base, 3.0, [65, 55, 45, 35])),
        ("Ladder 75→65→50→33", lambda: ProgressiveTarget(base, 3.0, [75, 65, 50, 33])),
        ("Ladder 80→65→50→33", lambda: ProgressiveTarget(base, 3.0, [80, 65, 50, 33])),
    ]

    for sp in [8, 10, 15, 20, 30]:
        print(f"\n  Stop={sp}%:")
        print(H); print(S)
        bl_r = sim(lambda: MambaBase(base, 3.0, 65), bank, num, seed=seed, stop_pct=sp)
        bl_val = bl_r['median']
        for tag, fn in best_ideas:
            r = sim(fn, bank, num, seed=seed, stop_pct=sp)
            pr(tag, r, bl_val)

    # ============================================================
    # SUMMARY
    # ============================================================
    print()
    print("=" * 125)
    print("  SUMMARY")
    print("=" * 125)
    print(f"\n  Baseline (65% pure IOL, stop=15%): median ${bl:+.2f}")

    # Collect all results at stop=15 for ranking
    all_r = []
    for tag, fn in best_ideas:
        r = sim(fn, bank, num, seed=seed, stop_pct=15)
        r['tag'] = tag
        all_r.append(r)

    all_r.sort(key=lambda x: x['median'], reverse=True)
    print(f"\n  Ranking at stop=15%:")
    for i, r in enumerate(all_r):
        delta = r['median'] - bl
        print(f"  {i+1}. {r['tag']:<45} ${r['median']:>+8.2f} ({'+' if delta >= 0 else ''}{delta:.2f} vs baseline) | bust {r['bust_pct']:.1f}%")
    print("=" * 125)
