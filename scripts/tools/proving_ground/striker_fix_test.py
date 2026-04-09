#!/usr/bin/env python3
"""STRIKER recovery fix validation — tests 3 fixes + combinations.

Problem 1: LS=2 chains structurally unrecoverable (DAL→MART transition at dalUnits
           instead of chain-cost-covering level)
Problem 2: Trail-aware bet cap creates death spiral on deep chains

Fix A: Cost-aware recovery (first Mart bet sized to cover chain cost)
Fix B: dalCap=1 (skip DAL phase, straight to Mart on 2nd loss)
Fix C: Disable trail cap during active recovery chains
"""
import random, math, statistics, sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000


def _striker(args):
    (s, bank, dal_cap, mart_iol, div, bet_cap_pct, trail_range_pct,
     cost_aware_recovery, trail_cap_in_chain) = args

    rng = random.Random(SEED * 100000 + s)
    base = max(bank / div, 0.00101)
    payout = 0.99 * 100.0 / 50 - 1.0  # 0.98
    win_prob = 0.50

    dal_units = 1; mult = 1.0; in_mart = False; consec = 0
    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    trail_rng = bank * trail_range_pct / 100
    chain_cost = 0.0  # Track cumulative chain cost

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered)

        bet = base * mult

        # Bet cap
        if bet_cap_pct > 0:
            max_b = bal * bet_cap_pct / 100
            if bet > max_b:
                bet = max_b

        # Soft bust
        if bet > bal * 0.95:
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0
            chain_cost = 0.0; bet = base

        if bet > bal:
            bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered)

        # Trail-aware cap — optionally disabled during active chains
        apply_trail_cap = True
        if not trail_cap_in_chain and consec > 0:
            apply_trail_cap = False  # Fix C: skip trail cap mid-chain

        if apply_trail_cap and trail_rng > 0:
            fl = peak - trail_rng
            mt = profit - fl
            if mt > 0 and bet > mt:
                bet = max(base, mt)
            if bet < 0.001:
                return (profit, False, hands, wagered)

        hands += 1; wagered += bet

        if rng.random() < win_prob:
            profit += bet * payout
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0
            chain_cost = 0.0
        else:
            profit -= bet; consec += 1
            chain_cost += bet

            if dal_cap > 0 and not in_mart and consec < dal_cap:
                dal_units += 1; mult = dal_units
            else:
                if not in_mart:
                    in_mart = True
                    if cost_aware_recovery:
                        # Fix A: Size first Mart bet to cover chain cost
                        # Need: bet * payout >= chain_cost + bet (cover cost + own bet)
                        # bet * (1 + payout) >= chain_cost + base  (chain_cost so far + next loss)
                        # Simpler: bet >= chain_cost / payout
                        needed = (chain_cost + base) / payout  # cover chain + base margin
                        mult = max(dal_units, needed / base)
                    else:
                        mult = dal_units  # Original: transition at dalUnits
                else:
                    mult *= mart_iol

                if bank + profit > 0 and base * mult > (bank + profit) * 0.95:
                    mult = 1.0; dal_units = 1; in_mart = False; consec = 0
                    chain_cost = 0.0

        if bank + profit <= 0:
            return (profit, True, hands, wagered)
        if profit > peak:
            peak = profit

        # Trail exit
        if profit <= peak - trail_rng:
            return (profit, False, hands, wagered)

    return (profit, False, hands, wagered)


if __name__ == "__main__":
    pool = Pool(cpu_count())
    N = 5000

    # Config format:
    # (label, dal_cap, mart_iol, div, bet_cap_pct, trail_range_pct,
    #  cost_aware_recovery, trail_cap_in_chain)
    configs = [
        # === BASELINE ===
        ("CURRENT v2.0.1 (dal=2, trail-cap always)",
         2, 3.0, 2500, 10, 5, False, True),

        # === FIX A: Cost-aware recovery ===
        ("Fix A: cost-aware recovery (dal=2)",
         2, 3.0, 2500, 10, 5, True, True),

        # === FIX B: dalCap=1 (skip DAL phase) ===
        ("Fix B: dalCap=1 (straight to Mart)",
         1, 3.0, 2500, 10, 5, False, True),

        # === FIX C: No trail cap in chains ===
        ("Fix C: no trail-cap mid-chain (dal=2)",
         2, 3.0, 2500, 10, 5, False, False),

        # === COMBINATIONS ===
        ("Fix A+C: cost-aware + no trail-cap in chain",
         2, 3.0, 2500, 10, 5, True, False),

        ("Fix B+C: dalCap=1 + no trail-cap in chain",
         1, 3.0, 2500, 10, 5, False, False),

        # === FIX B VARIANTS (dalCap=1 with different ranges) ===
        ("Fix B: dalCap=1, range=3%",
         1, 3.0, 2500, 10, 3, False, True),

        ("Fix B: dalCap=1, range=7%",
         1, 3.0, 2500, 10, 7, False, True),

        ("Fix B+C: dalCap=1 + no trail-cap, range=3%",
         1, 3.0, 2500, 10, 3, False, False),

        ("Fix B+C: dalCap=1 + no trail-cap, range=7%",
         1, 3.0, 2500, 10, 7, False, False),

        # === dalCap=0 (pure Mart from loss 1) ===
        ("dalCap=0 (pure Mart from loss 1)",
         0, 3.0, 2500, 10, 5, False, True),

        ("dalCap=0 + no trail-cap",
         0, 3.0, 2500, 10, 5, False, False),

        # === Cost-aware with dalCap=1 (belt + suspenders) ===
        ("Fix A+B: cost-aware + dalCap=1",
         1, 3.0, 2500, 10, 5, True, True),

        ("Fix A+B+C: cost-aware + dalCap=1 + no trail-cap",
         1, 3.0, 2500, 10, 5, True, False),
    ]

    print()
    print("=" * 110)
    print("  STRIKER RECOVERY FIX VALIDATION")
    print("  {} sessions | ${} bank | 50% chance | div=2500 | mart=3x | betcap=10%".format(N, BANK))
    print("  Fixes: A=cost-aware recovery, B=dalCap=1, C=no trail-cap mid-chain")
    print("=" * 110)

    scorecards = []
    for (label, dal, mart, div, cap, trail_rng,
         cost_aware, trail_in_chain) in configs:
        args = [(s, BANK, dal, mart, div, cap, trail_rng,
                 cost_aware, trail_in_chain) for s in range(N)]
        results = pool.map(_striker, args)
        s = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        scorecards.append(s)

    print()
    print_ranking(scorecards, BANK)

    # Top 3 detailed scorecards
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    for s in scorecards[:3]:
        print_scorecard(s, BANK)
        print()

    # Also show baseline for comparison
    baseline = [s for s in scorecards if "CURRENT" in s['tag']]
    if baseline and baseline[0] not in scorecards[:3]:
        print("  --- BASELINE COMPARISON ---")
        print_scorecard(baseline[0], BANK)
        print()

    pool.close(); pool.join()
    print("=" * 110)
