#!/usr/bin/env python3
"""STRIKER trail-from-start vs current config comparison."""
import random, math, statistics, sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.scorecard import scorecard, print_scorecard, print_ranking

SEED = 42; BANK = 100; MAX_HANDS = 15000


def _striker(args):
    s, bank, trail_act_pct, trail_range_pct, sl_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 2500, 0.00101)
    payout = 0.99 * 100.0 / 50 - 1.0
    dal_units = 1; mult = 1.0; in_mart = False; consec = 0
    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    act_t = bank * trail_act_pct / 100 if trail_act_pct > 0 else 0
    trail_rng = bank * trail_range_pct / 100
    sl = bank * sl_pct / 100 if sl_pct > 0 else 0
    ta = True if trail_act_pct == 0 else False

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        max_b = bal * 10 / 100
        if bet > max_b: bet = max_b
        if sl > 0:
            room = sl + profit
            if room > 0 and bet > room: bet = room
            elif room <= 0: bet = 0.00101
        if bet > bal * 0.95:
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
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
        if not ta and act_t > 0 and profit >= act_t: ta = True
        if ta and profit <= peak - trail_rng:
            return (profit, False, hands, wagered)
        if sl > 0 and profit <= -sl:
            return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


if __name__ == "__main__":
    pool = Pool(cpu_count())
    N = 5000

    configs = [
        ("CURRENT: trail=5% range=5% SL=10%",      5, 5, 10),
        ("TRAIL-START: range=5% no SL",             0, 5, 0),
        ("TRAIL-START: range=7% no SL",             0, 7, 0),
        ("TRAIL-START: range=10% no SL",            0, 10, 0),
        ("TRAIL-START: range=5% SL=10%",            0, 5, 10),
        ("TRAIL-START: range=7% SL=10%",            0, 7, 10),
        ("trail=3% range=5% SL=10%",                3, 5, 10),
        ("trail=3% range=5% no SL",                 3, 5, 0),
        ("trail=3% range=7% no SL",                 3, 7, 0),
        ("SL=10% only (no trail)",                  99, 5, 10),
    ]

    print()
    print("=" * 110)
    print("  STRIKER TRAIL-FROM-START COMPARISON")
    print("  {} sessions | ${} bank | 50% chance | div=2500".format(N, BANK))
    print("=" * 110)

    scorecards = []
    for label, ta, tr, sl in configs:
        args = [(s, BANK, ta, tr, sl) for s in range(N)]
        results = pool.map(_striker, args)
        s = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        scorecards.append(s)

    print()
    print_ranking(scorecards, BANK)

    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    for s in scorecards[:3]:
        print_scorecard(s, BANK)
        print()

    pool.close(); pool.join()
    print("=" * 110)
