#!/usr/bin/env python3
"""
Row+Column Combo Test — 2 rows + 2 dozens roulette coverage
Bet: row1 + row2 + range13-24 + range25-36 (4 equal units)
Coverage: 32/37 (86.5%). Three-tier outcome: +50%, -25%, -100%.

Compares vs COBRA (23 numbers, binary +56.5% or -100%).
"""

import random
import sys
from itertools import product

# ============================================================
# ROULETTE MODELS
# ============================================================

# Row+Column combo: outcome per number
ROW1 = {1,4,7,10,13,16,19,22,25,28,31,34}
ROW2 = {2,5,8,11,14,17,20,23,26,29,32,35}
RANGE_13_24 = set(range(13, 25))
RANGE_25_36 = set(range(25, 37))

def combo_payout(n):
    """Net payout as fraction of total bet (4 units)."""
    wins = 0
    if n in ROW1: wins += 1
    if n in ROW2: wins += 1
    if n in RANGE_13_24: wins += 1
    if n in RANGE_25_36: wins += 1
    # Each winning bet pays 2:1 on its unit (1/4 of total)
    # Net = (wins * 2 - (4 - wins)) / 4 = (3*wins - 4) / 4
    return (3 * wins - 4) / 4.0

# Verify
print("=== COMBO PAYOUT VERIFICATION ===")
outcomes = {}
for n in range(37):
    p = combo_payout(n)
    cat = "MISS" if p == -1.0 else ("SMALL_LOSS" if p < 0 else "WIN")
    outcomes.setdefault(cat, []).append(n)

for cat in ["WIN", "SMALL_LOSS", "MISS"]:
    nums = outcomes.get(cat, [])
    p = combo_payout(nums[0]) if nums else 0
    print(f"  {cat}: {len(nums)} numbers ({len(nums)/37*100:.1f}%) payout={p:+.2f}x  {sorted(nums)}")

ev = sum(combo_payout(n) for n in range(37)) / 37
print(f"  EV per spin: {ev:.4f} ({ev*100:.2f}%)")

# COBRA: 23 numbers, +0.565x or -1.0x
COBRA_WIN_FRAC = 36.0 / 23 - 1
COBRA_COVERED = 23

print(f"\n  COBRA: {COBRA_COVERED}/37 win at +{COBRA_WIN_FRAC:.3f}x, miss -1.0x")
print(f"  COMBO: 16/37 win at +0.50x, 16/37 small loss at -0.25x, 5/37 miss at -1.0x")


# ============================================================
# IOL STRATEGIES
# ============================================================

def sim_combo(iol, divider, bank, num, max_bets, seed,
              stop_pct=15, stop_loss_pct=15,
              trail_act=8, trail_lock=60,
              escalate_on="any_loss"):
    """
    escalate_on: 'any_loss' = IOL on net < 0, 'miss_only' = IOL only on -100% miss,
                 'proportional' = IOL multiplier scaled by loss fraction
    """
    pnls = []
    busts = 0
    total_bets = 0
    trail_exits = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base = bank / divider
        mult = 1.0
        profit = 0.0
        peak = 0.0
        bets = 0
        trail_active = False

        stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
        sl_thresh = bank * stop_loss_pct / 100 if stop_loss_pct > 0 else 0
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
                max_trail = profit - floor
                if max_trail > 0 and total_bet > max_trail:
                    total_bet = max_trail

            if total_bet > bal * 0.95:
                mult = 1.0
                total_bet = base
            if total_bet > bal:
                total_bet = bal
            if total_bet < 0.004:  # min for 4 sub-bets
                busts += 1
                break

            bets += 1
            n = random.randint(0, 36)
            payout_frac = combo_payout(n)
            profit += total_bet * payout_frac

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

            # IOL logic
            if payout_frac > 0:
                # Win — reset
                mult = 1.0
            elif escalate_on == "any_loss":
                # Any loss escalates
                mult *= iol
                nb = base * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0
            elif escalate_on == "miss_only":
                # Only escalate on full miss (-100%)
                if payout_frac <= -0.99:
                    mult *= iol
                    nb = base * mult
                    if bank + profit > 0 and nb > (bank + profit) * 0.95:
                        mult = 1.0
                # Small loss: don't escalate, stay at current mult
            elif escalate_on == "proportional":
                # Scale IOL by loss fraction
                loss_frac = abs(payout_frac)  # 0.25 or 1.0
                iol_adj = 1 + (iol - 1) * loss_frac  # e.g., 1.5x for -25%, 3.0x for -100%
                mult *= iol_adj
                nb = base * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0

            # Trailing stop
            if trail_act > 0:
                if not trail_active and profit >= act_thresh:
                    trail_active = True
                if trail_active:
                    floor = peak * trail_lock / 100
                    if profit <= floor:
                        trail_exits += 1
                        break

            # Fixed stop
            if stop_thresh > 0 and profit >= stop_thresh and mult <= 1.01:
                break

            # Stop loss
            if sl_thresh > 0 and profit <= -sl_thresh:
                break

        total_bets += bets
        pnls.append(profit)

    pnls.sort()
    n_r = len(pnls)
    return {
        'median': pnls[n_r // 2],
        'mean': sum(pnls) / n_r,
        'bust_pct': busts / n_r * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n_r * 100,
        'p10': pnls[n_r // 10],
        'p90': pnls[9 * n_r // 10],
        'avg_bets': total_bets / n_r,
    }


def sim_cobra(iol, divider, bank, num, max_bets, seed,
              stop_pct=15, stop_loss_pct=15,
              trail_act=8, trail_lock=60):
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
        sl_thresh = bank * stop_loss_pct / 100 if stop_loss_pct > 0 else 0
        act_thresh = bank * trail_act / 100 if trail_act > 0 else 0

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            total_bet = base * mult
            if trail_active:
                floor = peak * trail_lock / 100
                max_trail = profit - floor
                if max_trail > 0 and total_bet > max_trail:
                    total_bet = max_trail

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
            if n < COBRA_COVERED:
                profit += total_bet * COBRA_WIN_FRAC
                mult = 1.0
            else:
                profit -= total_bet
                mult *= iol
                nb = base * mult
                if bank + profit > 0 and nb > (bank + profit) * 0.95:
                    mult = 1.0

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

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
    n_r = len(pnls)
    return {
        'median': pnls[n_r // 2],
        'mean': sum(pnls) / n_r,
        'bust_pct': busts / n_r * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n_r * 100,
        'p10': pnls[n_r // 10],
        'p90': pnls[9 * n_r // 10],
        'avg_bets': total_bets / n_r,
    }


def pr(tag, r, bl=None):
    m = " **" if bl and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 5 / 60
    print(f"  {tag:<55} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {t:>5.1f}m{m}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    max_bets = 5000

    H = (f"  {'Config':<55} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Tm':>6}")
    S = (f"  {'─'*55} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*6}")

    print()
    print("=" * 120)
    print("  ROW+COLUMN COMBO vs COBRA — Roulette Coverage Comparison")
    print(f"  {num:,} sessions x {max_bets} spins | ${bank:,} | trail=8/60 SL=15%")
    print("=" * 120)

    # === COBRA BASELINE ===
    print("\n  --- COBRA BASELINE (23 numbers, trail 8/60 + SL 15%) ---")
    print(H); print(S)

    for div in [8000, 10000, 15000]:
        r = sim_cobra(3.0, div, bank, num, max_bets, seed)
        pr(f"COBRA div={div} IOL=3.0x", r)

    bl_r = sim_cobra(3.0, 10000, bank, num, max_bets, seed)
    bl = bl_r['median']

    # === COMBO: IOL ESCALATE ON ANY LOSS ===
    print(f"\n  --- COMBO: Escalate on ANY loss (net < 0) ---")
    print(H); print(S)

    for iol in [2.0, 2.5, 3.0, 3.5, 4.0]:
        for div in [5000, 8000, 10000, 15000]:
            r = sim_combo(iol, div, bank, num, max_bets, seed, escalate_on="any_loss")
            pr(f"COMBO any_loss IOL={iol}x div={div}", r, bl)
        print()

    # === COMBO: IOL ESCALATE ON MISS ONLY ===
    print(f"\n  --- COMBO: Escalate on MISS only (-100%) ---")
    print(H); print(S)

    for iol in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        for div in [5000, 8000, 10000, 15000]:
            r = sim_combo(iol, div, bank, num, max_bets, seed, escalate_on="miss_only")
            pr(f"COMBO miss_only IOL={iol}x div={div}", r, bl)
        print()

    # === COMBO: PROPORTIONAL IOL ===
    print(f"\n  --- COMBO: Proportional IOL (scale by loss fraction) ---")
    print(H); print(S)

    for iol in [2.0, 3.0, 4.0, 5.0]:
        for div in [5000, 8000, 10000, 15000]:
            r = sim_combo(iol, div, bank, num, max_bets, seed, escalate_on="proportional")
            pr(f"COMBO proportional IOL={iol}x div={div}", r, bl)
        print()

    # === SUMMARY ===
    print("=" * 120)
    print("  SUMMARY — Best combo config vs COBRA")
    print("=" * 120)

    # Find best combo across all modes
    all_combos = []
    for mode in ["any_loss", "miss_only", "proportional"]:
        for iol in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
            for div in [5000, 8000, 10000, 15000]:
                r = sim_combo(iol, div, bank, num, max_bets, seed, escalate_on=mode)
                r['tag'] = f"{mode} IOL={iol}x div={div}"
                all_combos.append(r)

    all_combos.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  COBRA baseline: ${bl:+.2f}")
    print(f"\n  Top 10 combo configs:")
    print(H); print(S)
    for r in all_combos[:10]:
        pr(r['tag'], r, bl)

    safe = [r for r in all_combos if r['bust_pct'] < 5]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  Top 5 safe (<5% bust):")
    print(H); print(S)
    for r in safe[:5]:
        pr(r['tag'], r, bl)

    best = all_combos[0]
    print(f"\n  VERDICT: Row+Column combo {'BEATS' if best['median'] > bl else 'does NOT beat'} COBRA")
    print(f"  Best combo: {best['tag']} → ${best['median']:+.2f} vs COBRA ${bl:+.2f}")
    print("=" * 120)
