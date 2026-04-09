#!/usr/bin/env python3
"""STRIKER trail-from-start — fine-grained range sweep to find optimal G."""
import random, math, statistics, sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.scorecard import scorecard, print_ranking

SEED = 42; BANK = 100; MAX_HANDS = 15000


def _striker(args):
    s, bank, trail_range_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 2500, 0.00101)
    payout = 0.99 * 100.0 / 50 - 1.0
    dal_units = 1; mult = 1.0; in_mart = False; consec = 0
    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    trail_rng = bank * trail_range_pct / 100
    ta = True  # Trail active from start

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        max_b = bal * 10 / 100
        if bet > max_b: bet = max_b
        if bet > bal * 0.95:
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        # Trail-aware cap
        fl = peak - trail_rng
        mt = profit - fl
        if mt > 0 and bet > mt: bet = max(base, mt)
        if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        if rng.random() < 0.50:
            profit += bet * payout
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0
        else:
            profit -= bet; consec += 1
            if consec < 2:
                dal_units += 1; mult = dal_units
            else:
                if not in_mart: in_mart = True; mult = dal_units
                else: mult *= 3.0
                if bank + profit > 0 and base * mult > (bank + profit) * 0.95:
                    mult = 1.0; dal_units = 1; in_mart = False; consec = 0
        if bank + profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if profit <= peak - trail_rng:
            return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


if __name__ == "__main__":
    pool = Pool(cpu_count())
    N = 5000

    ranges = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15]

    print()
    print("=" * 110)
    print("  STRIKER TRAIL-FROM-START — Range Sweep (G optimization)")
    print("  {} sessions | ${} bank | 50% chance | div=2500 | no SL".format(N, BANK))
    print("=" * 110)

    scorecards = []
    for rng_pct in ranges:
        label = "range={}%".format(rng_pct)
        args = [(s, BANK, rng_pct) for s in range(N)]
        results = pool.map(_striker, args)
        s = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        scorecards.append(s)

    print()
    print_ranking(scorecards, BANK)

    pool.close(); pool.join()
    print("=" * 110)
