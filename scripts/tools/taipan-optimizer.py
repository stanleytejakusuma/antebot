#!/usr/bin/env python3
"""
TAIPAN Optimizer — Selective IOL on Dozen + Even-Money
Tests the core thesis: only escalate on full misses, absorb partial losses.

Sweeps: split ratio × IOL × divider
Compares: vs standard IOL on same coverage, vs single dozen, vs COBRA
"""

import random
import sys
from itertools import product

# ============================================================
# ROULETTE SETS
# ============================================================

RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
DOZ2 = set(range(13, 25))
COBRA_NUMS = set(list(RED) + [2,4,6,8,10])

# Precompute TAIPAN outcome tiers per number
# For any dozen + any even-money: 6 overlap, 6 dozen-only, 12 even-only, 13 miss
DOZ2_AND_RED = DOZ2 & RED      # {14,16,18,19,21,23} — 6 numbers
DOZ2_ONLY = DOZ2 - RED          # {13,15,17,20,22,24} — 6 numbers
RED_ONLY = RED - DOZ2            # 12 numbers
MISS = set(range(37)) - DOZ2 - RED  # 13 numbers (includes 0)

assert len(DOZ2_AND_RED) == 6
assert len(DOZ2_ONLY) == 6
assert len(RED_ONLY) == 12
assert len(MISS) == 13
assert len(DOZ2_AND_RED) + len(DOZ2_ONLY) + len(RED_ONLY) + len(MISS) == 37


def taipan_outcome(n, dozen_frac):
    """
    Returns (net_payout_fraction, tier) for number n.
    dozen_frac: fraction of total bet on dozen (e.g., 0.6)
    even_frac: 1 - dozen_frac
    """
    even_frac = 1.0 - dozen_frac
    if n in DOZ2_AND_RED:
        net = dozen_frac * 2.0 + even_frac * 1.0  # win both
        return net, "strike"
    elif n in DOZ2_ONLY:
        net = dozen_frac * 2.0 - even_frac  # win dozen, lose even
        return net, "bite"
    elif n in RED_ONLY:
        net = -dozen_frac + even_frac * 1.0  # lose dozen, win even
        return net, "shield"
    else:
        net = -dozen_frac - even_frac  # lose both = -1.0
        return net, "miss"


# ============================================================
# SIMULATORS
# ============================================================

def sim_taipan(dozen_frac, iol, divider, bank, num, max_bets, seed,
               stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60,
               selective=True):
    """
    selective=True: only escalate on 'miss'. Hold on 'shield'.
    selective=False: escalate on any net loss (standard IOL).
    """
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
            payout, tier = taipan_outcome(n, dozen_frac)
            profit += total_bet * payout

            if bank + profit <= 0:
                busts += 1
                break

            if profit > peak:
                peak = profit

            # SELECTIVE IOL
            if tier in ("strike", "bite"):
                mult = 1.0  # Win — reset
            elif tier == "shield":
                if selective:
                    pass  # Hold — don't escalate
                else:
                    mult *= iol  # Standard: escalate on any loss
                    nb = base * mult
                    if bank + profit > 0 and nb > (bank + profit) * 0.95:
                        mult = 1.0
            elif tier == "miss":
                mult *= iol  # Escalate on full miss
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


def sim_single_dozen(iol, divider, bank, num, max_bets, seed, **kwargs):
    """Single dozen baseline (standard IOL)."""
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

        stop_thresh = bank * kwargs.get('stop_pct', 15) / 100
        sl_thresh = bank * kwargs.get('sl_pct', 15) / 100
        act_thresh = bank * kwargs.get('trail_act', 8) / 100

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break
            total_bet = base * mult
            if trail_active:
                floor = peak * kwargs.get('trail_lock', 60) / 100
                max_t = profit - floor
                if max_t > 0 and total_bet > max_t:
                    total_bet = max_t
            if total_bet > bal * 0.95:
                mult = 1.0
                total_bet = base
            if total_bet > bal: total_bet = bal
            if total_bet < 0.001:
                busts += 1
                break

            bets += 1
            n = random.randint(0, 36)
            if n in DOZ2:
                profit += total_bet * 2.0
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
            if profit > peak: peak = profit

            if not trail_active and profit >= act_thresh:
                trail_active = True
            if trail_active:
                floor = peak * kwargs.get('trail_lock', 60) / 100
                if profit <= floor: break

            if profit >= stop_thresh and mult <= 1.01: break
            if profit <= -sl_thresh: break

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
    print(f"  {tag:<55} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
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

    H = (f"  {'Config':<55} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Tm':>6}")
    S = (f"  {'─'*55} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*6}")

    # Verify tiers
    print("=== TAIPAN TIER VERIFICATION (60/40 split) ===")
    for frac in [0.4, 0.5, 0.6, 0.7, 0.8]:
        print(f"\n  Split {int(frac*100)}/{int((1-frac)*100)}:")
        for tier_name in ["strike", "bite", "shield", "miss"]:
            # Find a representative number
            if tier_name == "strike": nums = DOZ2_AND_RED
            elif tier_name == "bite": nums = DOZ2_ONLY
            elif tier_name == "shield": nums = RED_ONLY
            else: nums = MISS
            rep = sorted(nums)[0]
            payout, _ = taipan_outcome(rep, frac)
            print(f"    {tier_name:>8}: {len(nums):>2}/37 ({len(nums)/37*100:>5.1f}%) payout={payout:>+.3f}x")

    print()
    print("=" * 120)
    print("  TAIPAN OPTIMIZER — Selective IOL on Dozen + Even-Money")
    print(f"  {num:,} sessions | ${bank:,} | trail=8/60 SL=15% stop=15%")
    print("=" * 120)

    # ============================================================
    # BASELINES
    # ============================================================
    print("\n  === BASELINES ===")
    print(H); print(S)

    r_dozen = sim_single_dozen(4.0, 10000, bank, num, max_bets, seed)
    pr("Single Dozen IOL=4.0x div=10k", r_dozen)
    bl = r_dozen['median']

    r_dozen2 = sim_single_dozen(4.0, 8000, bank, num, max_bets, seed)
    pr("Single Dozen IOL=4.0x div=8k", r_dozen2)

    # ============================================================
    # SELECTIVE vs STANDARD IOL (same coverage, different escalation)
    # ============================================================
    print("\n  === SELECTIVE vs STANDARD IOL (split=60/40) ===")
    print(H); print(S)

    for iol in [3.0, 4.0, 5.0, 6.0]:
        for div in [8000, 10000, 15000]:
            rs = sim_taipan(0.6, iol, div, bank, num, max_bets, seed, selective=True)
            pr(f"TAIPAN selective IOL={iol}x div={div}", rs, bl)
        print()

    print("\n  --- Standard IOL on same coverage (60/40) ---")
    print(H); print(S)
    for iol in [3.0, 4.0, 5.0, 6.0]:
        for div in [8000, 10000, 15000]:
            rs = sim_taipan(0.6, iol, div, bank, num, max_bets, seed, selective=False)
            pr(f"Standard IOL={iol}x div={div}", rs, bl)
        print()

    # ============================================================
    # SPLIT RATIO SWEEP
    # ============================================================
    print("\n  === SPLIT RATIO SWEEP (Selective IOL) ===")

    all_results = []

    for dozen_frac in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        print(f"\n  --- Split {int(dozen_frac*100)}/{int((1-dozen_frac)*100)} ---")
        print(H); print(S)

        for iol in [3.0, 4.0, 5.0, 6.0]:
            for div in [5000, 8000, 10000, 15000]:
                r = sim_taipan(dozen_frac, iol, div, bank, num, max_bets, seed, selective=True)
                r['dozen_frac'] = dozen_frac
                r['iol'] = iol
                r['div'] = div
                r['tag'] = f"TAIPAN {int(dozen_frac*100)}/{int((1-dozen_frac)*100)} IOL={iol}x d={div}"
                all_results.append(r)

        # Show top 3 for this split
        subset = [r for r in all_results if r['dozen_frac'] == dozen_frac]
        subset.sort(key=lambda r: r['median'], reverse=True)
        for r in subset[:3]:
            pr(r['tag'], r, bl)

    # ============================================================
    # GRAND RANKING
    # ============================================================
    print()
    print("=" * 120)
    print("  GRAND RANKING — All TAIPAN configs")
    print("=" * 120)

    all_results.sort(key=lambda r: r['median'], reverse=True)

    print(f"\n  TOP 15 BY MEDIAN:")
    print(H); print(S)
    for r in all_results[:15]:
        pr(r['tag'], r, bl)

    # Score: median × (1 - bust/100)
    for r in all_results:
        r['score'] = r['median'] * (1 - r['bust_pct'] / 100)

    by_score = sorted(all_results, key=lambda r: r['score'], reverse=True)
    print(f"\n  TOP 10 BY RISK-ADJUSTED SCORE:")
    print(H); print(S)
    for r in by_score[:10]:
        pr(r['tag'] + f" [s={r['score']:.0f}]", r, bl)

    safe = [r for r in all_results if r['bust_pct'] < 1]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 10 SAFE (<1% bust):")
    print(H); print(S)
    for r in safe[:10]:
        pr(r['tag'], r, bl)

    # ============================================================
    # HEAD-TO-HEAD: BEST TAIPAN vs SINGLE DOZEN vs COBRA
    # ============================================================
    print()
    print("=" * 120)
    print("  HEAD-TO-HEAD: TAIPAN vs SINGLE DOZEN vs COBRA")
    print("=" * 120)
    print(H); print(S)

    best_taipan = all_results[0]
    pr(f"TAIPAN BEST: {best_taipan['tag']}", best_taipan)
    pr("Single Dozen IOL=4.0x div=10k", r_dozen)
    pr("Single Dozen IOL=4.0x div=8k", r_dozen2)

    # COBRA for reference
    cobra_table = {}
    for n in range(37):
        cobra_table[n] = (36.0/23 - 1) if n in COBRA_NUMS else -1.0
    # Quick COBRA sim
    pnls_c = []
    busts_c = 0
    bets_c = 0
    for s in range(num):
        random.seed(seed * 100000 + s)
        base = bank / 10000; mult = 1.0; profit = 0.0; peak = 0.0
        trail_active = False; b = 0
        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0: busts_c += 1; break
            tb = base * mult
            if trail_active:
                fl = peak * 60 / 100
                mt = profit - fl
                if mt > 0 and tb > mt: tb = mt
            if tb > bal * 0.95: mult = 1.0; tb = base
            if tb > bal: tb = bal
            if tb < 0.001: busts_c += 1; break
            b += 1
            n = random.randint(0, 36)
            p = cobra_table[n]
            profit += tb * p
            if bank + profit <= 0: busts_c += 1; break
            if profit > peak: peak = profit
            if p > 0: mult = 1.0
            else:
                mult *= 3.0
                if bank + profit > 0 and base * mult > (bank + profit) * 0.95: mult = 1.0
            if not trail_active and profit >= bank * 8 / 100: trail_active = True
            if trail_active and profit <= peak * 60 / 100: break
            if profit >= bank * 15 / 100 and mult <= 1.01: break
            if profit <= -bank * 15 / 100: break
        bets_c += b
        pnls_c.append(profit)
    pnls_c.sort()
    nc = len(pnls_c)
    r_cobra = {
        'median': pnls_c[nc//2], 'mean': sum(pnls_c)/nc,
        'bust_pct': busts_c/nc*100, 'win_pct': sum(1 for p in pnls_c if p > 0)/nc*100,
        'p10': pnls_c[nc//10], 'p90': pnls_c[9*nc//10], 'avg_bets': bets_c/nc,
    }
    pr("COBRA 23num IOL=3.0x div=10k", r_cobra)

    # ============================================================
    # SUMMARY
    # ============================================================
    print()
    print("=" * 120)
    print("  SUMMARY")
    print("=" * 120)
    print(f"\n  TAIPAN best:     ${best_taipan['median']:+.2f} | bust {best_taipan['bust_pct']:.1f}% | {best_taipan['tag']}")
    print(f"  Single Dozen:    ${r_dozen['median']:+.2f} | bust {r_dozen['bust_pct']:.1f}%")
    print(f"  COBRA:           ${r_cobra['median']:+.2f} | bust {r_cobra['bust_pct']:.1f}%")

    if best_taipan['median'] > r_dozen['median']:
        print(f"\n  VERDICT: TAIPAN BEATS Single Dozen by ${best_taipan['median'] - r_dozen['median']:+.2f}")
    else:
        print(f"\n  VERDICT: Single Dozen still leads by ${r_dozen['median'] - best_taipan['median']:+.2f}")

    # Selective vs Standard delta
    best_standard = sim_taipan(best_taipan['dozen_frac'], best_taipan['iol'],
                               best_taipan['div'], bank, num, max_bets, seed, selective=False)
    print(f"\n  Selective IOL advantage: ${best_taipan['median'] - best_standard['median']:+.2f} vs standard IOL on same coverage")
    print("=" * 120)
