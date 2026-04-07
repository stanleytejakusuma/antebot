#!/usr/bin/env python3
"""
TAIPAN Adaptive Test — Coverage switching on loss streaks
Tests: fixed coverage vs dozen rotation vs coverage expansion vs adaptive split.
"""

import random
import sys

RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK = set(range(1,37)) - RED
DOZ1, DOZ2, DOZ3 = set(range(1,13)), set(range(13,25)), set(range(25,37))
DOZENS = [DOZ1, DOZ2, DOZ3]
HIGH = set(range(19, 37))
LOW = set(range(1, 19))
ODD = {1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35}
EVEN = set(range(1,37)) - ODD
EVENS = [(RED, "red"), (BLACK, "black"), (HIGH, "high"), (LOW, "low"), (ODD, "odd"), (EVEN, "even")]

# Six-lines
SIXLINES = [set(range(i, i+6)) for i in range(1, 37, 6)]  # 6 six-lines


def payout(n, bets):
    """bets: list of (number_set, multiplier, fraction_of_total_bet)"""
    net = 0.0
    for nums, mult, frac in bets:
        if n in nums:
            net += frac * mult
        else:
            net -= frac
    return net


def sim(strategy_fn, bank=1000, num=2000, max_bets=5000, seed=42,
        stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60):
    pnls = []
    busts = 0
    total_bets = 0

    for s in range(num):
        random.seed(seed * 100000 + s)
        base = bank / 10000  # fixed divider
        mult = 1.0
        profit = 0.0
        peak = 0.0
        bets_count = 0
        ls = 0
        trail_active = False

        stop_thresh = bank * stop_pct / 100
        sl_thresh = bank * sl_pct / 100
        act_thresh = bank * trail_act / 100

        strat = strategy_fn()

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            total_bet = base * mult

            if trail_active:
                floor = peak * trail_lock / 100
                max_t = profit - floor
                if max_t > 0 and total_bet > max_t:
                    total_bet = max_t

            if total_bet > bal * 0.95:
                mult = 1.0
                total_bet = base
            if total_bet > bal:
                total_bet = bal
            if total_bet < 0.001:
                busts += 1
                break

            bets_count += 1

            # Get current bet structure from strategy
            bet_structure = strat.get_bets(ls, mult, trail_active)

            n = random.randint(0, 36)
            p = payout(n, bet_structure)
            profit += total_bet * p

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

            if p > 0:
                ls = 0
                mult = 1.0
                strat.on_win()
            else:
                ls += 1
                iol = strat.get_iol(ls, p)
                mult *= iol
                nb = base * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0

            # Trail
            if not trail_active and profit >= act_thresh:
                trail_active = True
            if trail_active:
                floor = peak * trail_lock / 100
                if profit <= floor:
                    break

            if profit >= stop_thresh and mult <= 1.01:
                break
            if profit <= -sl_thresh:
                break

        total_bets += bets_count
        pnls.append(profit)

    pnls.sort()
    nr = len(pnls)
    return {
        'median': pnls[nr // 2],
        'mean': sum(pnls) / nr,
        'bust_pct': busts / nr * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / nr * 100,
        'p10': pnls[nr // 10],
        'p90': pnls[9 * nr // 10],
        'avg_bets': total_bets / nr,
    }


# ============================================================
# STRATEGIES
# ============================================================

class FixedTaipan:
    """Fixed split: dozen_frac on DOZ2, rest on RED. Standard IOL."""
    def __init__(self, dozen_frac=0.4, iol=6.0):
        self.df = dozen_frac
        self.ef = 1.0 - dozen_frac
        self.iol = iol
    def get_bets(self, ls, mult, trail_active):
        return [(DOZ2, 2.0, self.df), (RED, 1.0, self.ef)]
    def get_iol(self, ls, p):
        return self.iol
    def on_win(self):
        pass


class RotatingDozen:
    """Rotate which dozen after X losses. Same split, different dozen."""
    def __init__(self, dozen_frac=0.4, iol=6.0, rotate_at=3):
        self.df = dozen_frac
        self.ef = 1.0 - dozen_frac
        self.iol = iol
        self.rotate_at = rotate_at
        self.dozen_idx = 1  # start on DOZ2
    def get_bets(self, ls, mult, trail_active):
        if self.rotate_at > 0 and ls > 0 and ls % self.rotate_at == 0:
            self.dozen_idx = (self.dozen_idx + 1) % 3
        doz = DOZENS[self.dozen_idx]
        return [(doz, 2.0, self.df), (RED, 1.0, self.ef)]
    def get_iol(self, ls, p):
        return self.iol
    def on_win(self):
        self.dozen_idx = 1  # reset to DOZ2


class CoverageExpanding:
    """Expand coverage on deep LS. Narrow (high payout) → Wide (safer)."""
    def __init__(self, iol=5.0):
        self.iol = iol
    def get_bets(self, ls, mult, trail_active):
        if ls <= 2:
            # Level 1: Single dozen (32.4% win, +2.0x)
            return [(DOZ2, 2.0, 1.0)]
        elif ls <= 4:
            # Level 2: Dozen + even-money 40/60 (64.9% effective win)
            return [(DOZ2, 2.0, 0.4), (RED, 1.0, 0.6)]
        elif ls <= 6:
            # Level 3: Two dozens (64.9% win, +0.5x)
            return [(DOZ2, 2.0, 0.5), (DOZ3, 2.0, 0.5)]
        else:
            # Level 4: Five six-lines (81.1% win, +0.2x)
            frac = 1.0 / 5
            return [(sl, 5.0, frac) for sl in SIXLINES[:5]]
    def get_iol(self, ls, p):
        return self.iol
    def on_win(self):
        pass


class AdaptiveSplit:
    """Change dozen/even-money split based on session state."""
    def __init__(self, cruise_split=0.4, strike_split=0.8, protect_split=0.3, iol=6.0):
        self.cruise = cruise_split
        self.strike = strike_split
        self.protect = protect_split
        self.iol = iol
    def get_bets(self, ls, mult, trail_active):
        if trail_active:
            df = self.protect  # maximum shield
        elif mult > 1.5:
            df = self.strike   # heavy dozen for recovery
        else:
            df = self.cruise   # wide coverage
        ef = 1.0 - df
        return [(DOZ2, 2.0, df), (RED, 1.0, ef)]
    def get_iol(self, ls, p):
        return self.iol
    def on_win(self):
        pass


class AdaptiveSplitV2:
    """Adaptive split with LS-based coverage expansion."""
    def __init__(self, iol=5.0, expand_at=5):
        self.iol = iol
        self.expand_at = expand_at
    def get_bets(self, ls, mult, trail_active):
        if trail_active:
            # PROTECT: wide coverage, low variance
            return [(DOZ2, 2.0, 0.3), (RED, 1.0, 0.7)]
        elif ls >= self.expand_at:
            # DEEP LS: expand to 2 dozens (higher win chance)
            return [(DOZ2, 2.0, 0.5), (DOZ3, 2.0, 0.5)]
        elif mult > 1.5:
            # RECOVERY: heavy dozen for max recovery
            return [(DOZ2, 2.0, 0.8), (RED, 1.0, 0.2)]
        else:
            # CRUISE: balanced
            return [(DOZ2, 2.0, 0.4), (RED, 1.0, 0.6)]
    def get_iol(self, ls, p):
        return self.iol
    def on_win(self):
        pass


class ProportionalIOL:
    """Variable IOL based on loss severity."""
    def __init__(self, dozen_frac=0.4, iol_miss=6.0, iol_shield=2.0):
        self.df = dozen_frac
        self.ef = 1.0 - dozen_frac
        self.iol_miss = iol_miss
        self.iol_shield = iol_shield
    def get_bets(self, ls, mult, trail_active):
        return [(DOZ2, 2.0, self.df), (RED, 1.0, self.ef)]
    def get_iol(self, ls, p):
        if p <= -0.5:
            return self.iol_miss  # full miss
        else:
            return self.iol_shield  # partial loss
    def on_win(self):
        pass


class FullAdaptive:
    """Everything combined: adaptive split + coverage expansion + proportional IOL."""
    def __init__(self, iol_miss=6.0, iol_shield=2.0, expand_at=6):
        self.iol_miss = iol_miss
        self.iol_shield = iol_shield
        self.expand_at = expand_at
    def get_bets(self, ls, mult, trail_active):
        if trail_active:
            return [(DOZ2, 2.0, 0.3), (RED, 1.0, 0.7)]
        elif ls >= self.expand_at:
            return [(DOZ2, 2.0, 0.5), (DOZ3, 2.0, 0.5)]
        elif mult > 1.5:
            return [(DOZ2, 2.0, 0.7), (RED, 1.0, 0.3)]
        else:
            return [(DOZ2, 2.0, 0.4), (RED, 1.0, 0.6)]
    def get_iol(self, ls, p):
        if p <= -0.5:
            return self.iol_miss
        else:
            return self.iol_shield
    def on_win(self):
        pass


def pr(tag, r, bl=None):
    m = " **" if bl and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 5 / 60
    print(f"  {tag:<58} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {t:>5.1f}m{m}")


if __name__ == "__main__":
    num = 2000
    bank = 1000
    seed = 42

    H = (f"  {'Config':<58} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Tm':>6}")
    S = (f"  {'─'*58} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*6}")

    print()
    print("=" * 125)
    print("  TAIPAN ADAPTIVE TEST — Coverage Switching on Loss Streaks")
    print(f"  {num:,} sessions | div=10000 | ${bank:,} | trail=8/60 SL=15% stop=15%")
    print("=" * 125)

    # === BASELINES ===
    print("\n  === BASELINES ===")
    print(H); print(S)

    r_fixed = sim(lambda: FixedTaipan(0.4, 6.0), bank, num)
    pr("Fixed TAIPAN 40/60 IOL=6.0x", r_fixed)
    bl = r_fixed['median']

    r_fixed2 = sim(lambda: FixedTaipan(0.6, 5.0), bank, num)
    pr("Fixed TAIPAN 60/40 IOL=5.0x", r_fixed2, bl)

    r_dozen = sim(lambda: FixedTaipan(1.0, 4.0), bank, num)
    pr("Pure Single Dozen IOL=4.0x", r_dozen, bl)

    # === DOZEN ROTATION (mathematically irrelevant?) ===
    print("\n  === DOZEN ROTATION ===")
    print(H); print(S)

    for rot in [2, 3, 4, 5, 0]:
        tag = f"Rotate dozen every {rot} LS" if rot > 0 else "No rotation (fixed)"
        r = sim(lambda r=rot: RotatingDozen(0.4, 6.0, r), bank, num)
        pr(tag, r, bl)

    # === COVERAGE EXPANSION ===
    print("\n  === COVERAGE EXPANSION (narrow→wide on deep LS) ===")
    print(H); print(S)

    for iol in [3.0, 4.0, 5.0, 6.0]:
        r = sim(lambda i=iol: CoverageExpanding(i), bank, num)
        pr(f"Expanding coverage IOL={iol}x", r, bl)

    # === ADAPTIVE SPLIT ===
    print("\n  === ADAPTIVE SPLIT (cruise/strike/protect) ===")
    print(H); print(S)

    configs = [
        (0.4, 0.8, 0.3, 6.0, "40→80→30 IOL=6x"),
        (0.4, 0.7, 0.3, 6.0, "40→70→30 IOL=6x"),
        (0.4, 0.9, 0.2, 6.0, "40→90→20 IOL=6x"),
        (0.5, 0.8, 0.3, 5.0, "50→80→30 IOL=5x"),
        (0.4, 0.8, 0.3, 5.0, "40→80→30 IOL=5x"),
        (0.3, 0.8, 0.2, 6.0, "30→80→20 IOL=6x"),
        (0.4, 1.0, 0.3, 5.0, "40→100→30 IOL=5x (pure dozen on recovery)"),
        (0.4, 1.0, 0.2, 6.0, "40→100→20 IOL=6x (pure dozen on recovery)"),
    ]
    for c, s, p, iol, label in configs:
        r = sim(lambda c=c, s=s, p=p, i=iol: AdaptiveSplit(c, s, p, i), bank, num)
        pr(f"Adaptive: {label}", r, bl)

    # === ADAPTIVE SPLIT V2 (with coverage expansion) ===
    print("\n  === ADAPTIVE V2 (split + expansion on deep LS) ===")
    print(H); print(S)

    for iol in [4.0, 5.0, 6.0]:
        for expand in [4, 5, 6, 7]:
            r = sim(lambda i=iol, e=expand: AdaptiveSplitV2(i, e), bank, num)
            pr(f"AdaptiveV2 IOL={iol}x expand@LS{expand}", r, bl)
        print()

    # === PROPORTIONAL IOL ===
    print("\n  === PROPORTIONAL IOL (different IOL per loss tier) ===")
    print(H); print(S)

    for im, ish in [(6.0, 1.5), (6.0, 2.0), (6.0, 3.0), (5.0, 1.5), (5.0, 2.0),
                     (4.0, 1.5), (4.0, 2.0), (8.0, 2.0), (8.0, 3.0)]:
        r = sim(lambda m=im, s=ish: ProportionalIOL(0.4, m, s), bank, num)
        pr(f"Proportional miss={im}x shield={ish}x (40/60)", r, bl)

    # === FULL ADAPTIVE (everything) ===
    print("\n  === FULL ADAPTIVE (split + expansion + proportional IOL) ===")
    print(H); print(S)

    for im, ish, exp in [
        (6.0, 2.0, 5), (6.0, 2.0, 6), (6.0, 2.0, 7),
        (5.0, 2.0, 5), (5.0, 2.0, 6),
        (6.0, 1.5, 5), (6.0, 1.5, 6),
        (8.0, 2.0, 5), (8.0, 2.0, 6),
        (6.0, 3.0, 5), (6.0, 3.0, 6),
    ]:
        r = sim(lambda m=im, s=ish, e=exp: FullAdaptive(m, s, e), bank, num)
        pr(f"Full: miss={im}x shield={ish}x expand@{exp}", r, bl)

    # === GRAND RANKING ===
    print()
    print("=" * 125)
    print("  GRAND RANKING")
    print("=" * 125)
    print(H); print(S)

    all_r = [
        ("Fixed 40/60 IOL=6x", r_fixed),
        ("Pure Dozen IOL=4x", r_dozen),
    ]

    # Collect best from each category
    best_configs = [
        ("Rotate@3", lambda: RotatingDozen(0.4, 6.0, 3)),
        ("Expand IOL=5x", lambda: CoverageExpanding(5.0)),
        ("Adaptive 40→80→30 IOL=6x", lambda: AdaptiveSplit(0.4, 0.8, 0.3, 6.0)),
        ("Adaptive 40→100→20 IOL=6x", lambda: AdaptiveSplit(0.4, 1.0, 0.2, 6.0)),
        ("AdaptiveV2 IOL=5x exp@5", lambda: AdaptiveSplitV2(5.0, 5)),
        ("AdaptiveV2 IOL=6x exp@5", lambda: AdaptiveSplitV2(6.0, 5)),
        ("Proportional 6x/2x", lambda: ProportionalIOL(0.4, 6.0, 2.0)),
        ("Proportional 8x/2x", lambda: ProportionalIOL(0.4, 8.0, 2.0)),
        ("Full 6x/2x exp@5", lambda: FullAdaptive(6.0, 2.0, 5)),
        ("Full 8x/2x exp@5", lambda: FullAdaptive(8.0, 2.0, 5)),
    ]

    for tag, fn in best_configs:
        r = sim(fn, bank, num)
        all_r.append((tag, r))

    all_r.sort(key=lambda x: x[1]['median'], reverse=True)
    for tag, r in all_r:
        pr(tag, r, bl)

    print()
    print(f"  #1: {all_r[0][0]} — ${all_r[0][1]['median']:+.2f}")
    print(f"  Fixed baseline: ${bl:+.2f}")
    print(f"  Delta: ${all_r[0][1]['median'] - bl:+.2f}")
    print("=" * 125)
