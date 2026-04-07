#!/usr/bin/env python3
"""
Roulette Coverage Archetype Sweep — Test all distinct coverage patterns from 50+ systems.
Distilled to 7 unique archetypes. Sweeps IOL × divider on each with trail+SL.

From JackAce catalog: 50 systems reduce to 7 payout structures.
"""

import random
import sys
from itertools import product

# ============================================================
# ROULETTE NUMBER SETS
# ============================================================

RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
ODD = {1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35}
EVEN = {2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36}
HIGH = set(range(19, 37))
LOW = set(range(1, 19))
ROW1 = {1,4,7,10,13,16,19,22,25,28,31,34}
ROW2 = {2,5,8,11,14,17,20,23,26,29,32,35}
ROW3 = {3,6,9,12,15,18,21,24,27,30,33,36}
DOZ1 = set(range(1, 13))
DOZ2 = set(range(13, 25))
DOZ3 = set(range(25, 37))

# Six-line bets (5 of 6, covering 30 numbers)
SIXLINE1 = set(range(1, 7))    # 1-6
SIXLINE2 = set(range(7, 13))   # 7-12
SIXLINE3 = set(range(13, 19))  # 13-18
SIXLINE4 = set(range(19, 25))  # 19-24
SIXLINE5 = set(range(25, 31))  # 25-30
SIXLINE6 = set(range(31, 37))  # 31-36

# ============================================================
# ARCHETYPE DEFINITIONS
# ============================================================

def build_payout_table(name, bets):
    """
    Build payout table for 0-36.
    bets: list of (set_of_numbers, payout_multiplier, bet_fraction)
    e.g., [(RED, 1.0, 0.5), (DOZ3, 2.0, 0.5)] means bet half on red (1:1) half on dozen3 (2:1)
    Returns: dict of {number: net_payout_fraction} where total bet = 1.0
    """
    table = {}
    for n in range(37):
        net = 0.0
        for numbers, mult, frac in bets:
            if n in numbers:
                net += frac * mult  # win: payout
            else:
                net -= frac  # lose: bet fraction
        table[n] = net
    return table


ARCHETYPES = {}

# 1. EVEN MONEY — Red (Martingale classic)
# 18/37 win +1.0x, 19/37 lose -1.0x
ARCHETYPES["Even Money (Red)"] = build_payout_table("red", [(RED, 1.0, 1.0)])

# 2. SINGLE DOZEN — 1 dozen at 2:1
# 12/37 win +2.0x, 25/37 lose -1.0x
ARCHETYPES["Single Dozen"] = build_payout_table("doz", [(DOZ2, 2.0, 1.0)])

# 3. TWO DOZENS — 2 dozens at 2:1 each
# 24/37 win +0.5x, 13/37 lose -1.0x
ARCHETYPES["Two Dozens"] = build_payout_table("2doz", [
    (DOZ2, 2.0, 0.5),
    (DOZ3, 2.0, 0.5),
])

# 4. FIVE SIX-LINES — 5 of 6 six-line bets (covers 30/37)
# 30/37 win +0.2x, 7/37 lose -1.0x
ARCHETYPES["Five Six-Lines"] = build_payout_table("5six", [
    (SIXLINE1, 5.0, 0.2),
    (SIXLINE2, 5.0, 0.2),
    (SIXLINE3, 5.0, 0.2),
    (SIXLINE4, 5.0, 0.2),
    (SIXLINE5, 5.0, 0.2),
])

# 5. ROW+COLUMN COMBO — 2 rows + 2 dozens (our proven winner)
# 16/37 +0.5x, 16/37 -0.25x, 5/37 -1.0x
ARCHETYPES["Row+Column Combo"] = build_payout_table("combo", [
    (ROW1, 2.0, 0.25),
    (ROW2, 2.0, 0.25),
    (DOZ2, 2.0, 0.25),
    (DOZ3, 2.0, 0.25),
])

# 6. THREE EVEN-MONEY — Red + Odd + High (Martingale Lover style)
# Multi-tier: some numbers hit 0/1/2/3 bets
ARCHETYPES["Three Even-Money"] = build_payout_table("3even", [
    (RED, 1.0, 1/3),
    (ODD, 1.0, 1/3),
    (HIGH, 1.0, 1/3),
])

# 7. 23 PURE NUMBERS (COBRA baseline)
COBRA_NUMS = set(list(RED) + [2,4,6,8,10])  # 18 red + 5 black = 23
ARCHETYPES["COBRA 23 Numbers"] = {}
for n in range(37):
    if n in COBRA_NUMS:
        ARCHETYPES["COBRA 23 Numbers"][n] = 36.0 / 23 - 1  # +0.565x
    else:
        ARCHETYPES["COBRA 23 Numbers"][n] = -1.0

# 8. TWO ROWS + ONE DOZEN (variant: 2 columns + 1 dozen)
# Covers 24+12-overlap = varies
ARCHETYPES["Two Rows + One Dozen"] = build_payout_table("2r1d", [
    (ROW1, 2.0, 1/3),
    (ROW2, 2.0, 1/3),
    (DOZ3, 2.0, 1/3),
])

# 9. EVEN MONEY + DOZEN (Red + Dozen3)
ARCHETYPES["Red + Dozen"] = build_payout_table("rd", [
    (RED, 1.0, 0.5),
    (DOZ3, 2.0, 0.5),
])

# 10. TWO COLUMNS + TWO DOZENS (swapped: row1+row3 + doz1+doz3)
ARCHETYPES["Alt Row+Dozen Combo"] = build_payout_table("altcombo", [
    (ROW1, 2.0, 0.25),
    (ROW3, 2.0, 0.25),
    (DOZ1, 2.0, 0.25),
    (DOZ3, 2.0, 0.25),
])


# ============================================================
# VERIFY ALL ARCHETYPES
# ============================================================

def analyze_archetype(name, table):
    tiers = {}
    for n in range(37):
        p = round(table[n], 4)
        tiers.setdefault(p, []).append(n)
    ev = sum(table[n] for n in range(37)) / 37
    return tiers, ev


print("=" * 100)
print("  ROULETTE ARCHETYPE PAYOUT VERIFICATION")
print("=" * 100)

for name, table in ARCHETYPES.items():
    tiers, ev = analyze_archetype(name, table)
    print(f"\n  {name}: EV={ev:.4f} ({ev*100:.2f}%)")
    for payout in sorted(tiers.keys(), reverse=True):
        nums = tiers[payout]
        print(f"    {payout:>+.4f}x: {len(nums)}/37 ({len(nums)/37*100:.1f}%) — {sorted(nums)[:8]}{'...' if len(nums)>8 else ''}")


# ============================================================
# SIMULATOR
# ============================================================

def sim(payout_table, iol, divider, bank, num, max_bets, seed,
        stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60):
    pnls = []
    busts = 0
    total_bets = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base = bank / divider
        mult = 1.0
        profit = 0.0
        peak = 0.0
        bets = 0
        trail_active = False

        stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
        sl_thresh = bank * sl_pct / 100 if sl_pct > 0 else 0
        act_thresh = bank * trail_act / 100 if trail_act > 0 else 0

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            total_bet = base * mult

            # Trail-aware bet cap
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

            bets += 1
            n = random.randint(0, 36)
            payout_frac = payout_table[n]
            profit += total_bet * payout_frac

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

            # IOL: escalate on any net loss
            if payout_frac > 0:
                mult = 1.0
            else:
                mult *= iol
                nb = base * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0

            # Trail
            if trail_act > 0:
                if not trail_active and profit >= act_thresh:
                    trail_active = True
                if trail_active:
                    floor = peak * trail_lock / 100
                    if profit <= floor:
                        break

            if stop_thresh > 0 and profit >= stop_thresh and mult <= 1.01:
                break
            if sl_thresh > 0 and profit <= -sl_thresh:
                break

        total_bets += bets
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


def pr(tag, r, bl=None):
    m = " **" if bl and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 5 / 60
    print(f"  {tag:<50} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {t:>5.1f}m{m}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    max_bets = 5000

    H = (f"  {'Config':<50} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Tm':>6}")
    S = (f"  {'─'*50} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*6}")

    print()
    print("=" * 100)
    print("  ROULETTE ARCHETYPE SWEEP — All Coverage Patterns")
    print(f"  {num:,} sessions | ${bank:,} | trail=8/60 SL=15% stop=15%")
    print("=" * 100)

    # Find best IOL/div per archetype
    all_results = []

    for name, table in ARCHETYPES.items():
        print(f"\n  === {name} ===")
        print(H); print(S)

        best = None
        best_med = -999999

        for iol in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
            for div in [5000, 8000, 10000, 15000]:
                r = sim(table, iol, div, bank, num, max_bets, seed)
                r['name'] = name
                r['iol'] = iol
                r['div'] = div
                tag = f"IOL={iol}x div={div}"

                if r['median'] > best_med:
                    best_med = r['median']
                    best = r
                    best['tag'] = tag

        # Print top 5 for this archetype
        configs = []
        for iol in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
            for div in [5000, 8000, 10000, 15000]:
                r = sim(table, iol, div, bank, num, max_bets, seed)
                r['iol'] = iol
                r['div'] = div
                configs.append(r)

        configs.sort(key=lambda r: r['median'], reverse=True)
        for r in configs[:5]:
            pr(f"IOL={r['iol']}x div={r['div']}", r)

        best['tag'] = f"IOL={best['iol']}x div={best['div']}"
        all_results.append(best)

    # ============================================================
    # GRAND RANKING
    # ============================================================
    print()
    print("=" * 100)
    print("  GRAND RANKING — Best config per archetype")
    print("=" * 100)
    print(H); print(S)

    all_results.sort(key=lambda r: r['median'], reverse=True)
    for i, r in enumerate(all_results):
        tag = f"#{i+1} {r['name']} ({r['tag']})"
        pr(tag, r)

    print()
    print("  TOP 3 FOR PROFIT:")
    for i, r in enumerate(all_results[:3]):
        print(f"    {i+1}. {r['name']}: ${r['median']:+.2f} (IOL={r['iol']}x div={r['div']}, bust={r['bust_pct']:.1f}%)")

    print("=" * 100)
