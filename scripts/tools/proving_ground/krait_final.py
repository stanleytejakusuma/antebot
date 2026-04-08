#!/usr/bin/env python3
"""KRAIT final optimization — dual-regime dice strategy.

Architecture: SL/TP exits, no trail. Optional DD-triggered rest mode.
Best params from sweep: 50% chance, IOL 3x, DD3% r=30, delay=0 or 1.

This test fine-tunes the winning config and establishes the production spec.
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000
BET_CAP_PCT = 10; REST_CHANCE = 95


def _krait(args):
    (s, div, delay, mart_iol,
     dd_pct, rest_dur, sl_pct, tp_pct, use_switching) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    base = max(bank / div, 0.00101)

    p_payout = 0.99 * 100.0 / 50 - 1.0  # 0.98
    p_winp = 0.50
    r_payout = 0.99 * 100.0 / REST_CHANCE - 1.0
    r_winp = REST_CHANCE / 100.0

    sl_amt = bank * sl_pct / 100
    tp_amt = bank * tp_pct / 100

    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    rest_hands = 0; profit_hands = 0; switches = 0

    mult = 1.0; in_mart = False; consec = 0; chain_cost = 0.0
    mode = 'profit'; rest_ctr = 0; entry_profit = 0.0

    def reset_chain():
        nonlocal mult, in_mart, consec, chain_cost
        mult = 1.0; in_mart = False; consec = 0; chain_cost = 0.0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        if mode == 'rest':
            bet = base; winp = r_winp; payout = r_payout
        else:
            bet = base * mult; winp = p_winp; payout = p_payout
            mx = bal * BET_CAP_PCT / 100
            if bet > mx: bet = mx
            if bet > bal * 0.95:
                reset_chain(); bet = base

        if bet > bal: bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        hands += 1; wagered += bet
        if mode == 'rest': rest_hands += 1
        else: profit_hands += 1

        if rng.random() < winp:
            profit += bet * payout
            if mode == 'profit': reset_chain()
        else:
            profit -= bet
            if mode == 'profit':
                consec += 1; chain_cost += bet
                if consec <= delay:
                    mult = 1  # flat absorb
                else:
                    if not in_mart:
                        in_mart = True; mult = 1
                    else:
                        mult *= mart_iol
                    if bal > 0 and base * mult > bal * 0.95:
                        reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)
        if profit > peak: peak = profit

        if profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)
        if profit >= tp_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)

        # Regime switching
        if use_switching:
            if mode == 'profit':
                dd = entry_profit - profit
                if dd > bank * dd_pct / 100:
                    mode = 'rest'; rest_ctr = rest_dur
                    reset_chain(); switches += 1
            elif mode == 'rest':
                rest_ctr -= 1
                if rest_ctr <= 0:
                    mode = 'profit'; entry_profit = profit
                    reset_chain(); switches += 1

    return (profit, False, hands, wagered, rest_hands, profit_hands, switches)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 10000  # 10k for final validation

    configs = []

    # === TOP CANDIDATES FROM SWEEP ===

    # Best switching: DD3% r=30 delay=1
    configs.append(("DD3 r30 d1 SL10/TP5",
                     2500, 1, 3.0, 3, 30, 10, 5, True))
    # Untested combo: DD3% r=30 delay=0
    configs.append(("DD3 r30 d0 SL10/TP5",
                     2500, 0, 3.0, 3, 30, 10, 5, True))
    # No-switch baseline delay=1
    configs.append(("no-switch d1 SL10/TP5",
                     2500, 1, 3.0, 3, 30, 10, 5, False))
    # No-switch baseline delay=0
    configs.append(("no-switch d0 SL10/TP5",
                     2500, 0, 3.0, 3, 30, 10, 5, False))

    # === SL/TP RATIO SWEEP (with DD3 r30 d0, the predicted winner) ===
    for sl, tp in [(5, 3), (5, 5), (7, 5), (10, 3), (10, 5), (10, 7),
                   (10, 10), (15, 5), (15, 10)]:
        label = "DD3 r30 d0 SL{}/TP{}".format(sl, tp)
        configs.append((label, 2500, 0, 3.0, 3, 30, sl, tp, True))

    # === DIVIDER SWEEP (with DD3 r30 d0 SL10/TP5) ===
    for div in [1500, 2000, 2500, 3000, 4000]:
        label = "div={} DD3 r30 d0 SL10/TP5".format(div)
        configs.append((label, div, 0, 3.0, 3, 30, 10, 5, True))

    # === DD FINE-TUNE (with d0 SL10/TP5) ===
    for dd in [2.5, 3.0, 3.5, 4.0]:
        for rest in [20, 30, 50]:
            label = "DD{}% r{} d0 SL10/TP5".format(dd, rest)
            configs.append((label, 2500, 0, 3.0, dd, rest, 10, 5, True))

    # === REFERENCE: STRIKER v3.0 equivalent (trail proxy via tight SL) ===
    configs.append(("STRIKER-proxy SL3/TP3",
                     2500, 1, 3.0, 3, 30, 3, 3, False))

    print()
    print("=" * 120)
    print("  KRAIT — FINAL OPTIMIZATION")
    print("  {} sessions | ${} bank | 50% dice | rest@{}% | betcap={}%".format(
        N, BANK, REST_CHANCE, BET_CAP_PCT))
    print("  Architecture: SL/TP exits + DD-triggered rest mode")
    print("=" * 120)

    all_results = {}
    scorecards = []

    for cfg in configs:
        label = cfg[0]
        args = [(s,) + cfg[1:] for s in range(N)]
        results = pool.map(_krait, args)
        all_results[label] = results
        sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        scorecards.append(sc)

    print()
    print_ranking(scorecards, BANK)

    # Regime stats for top 10
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    print("  {:<35} {:>7} {:>7} {:>7} {:>7} {:>7} {:>7}".format(
        'Strategy', 'Hands', 'Prof%', 'Rest%', 'Sw', 'Wag', 'Win%'))
    print("  " + "-" * 85)
    for sc in scorecards[:15]:
        label = sc['tag']
        results = all_results[label]
        avg_h = statistics.mean([r[2] for r in results])
        avg_ph = statistics.mean([r[5] for r in results])
        avg_rh = statistics.mean([r[4] for r in results])
        avg_sw = statistics.mean([r[6] for r in results])
        avg_w = statistics.mean([r[3] for r in results])
        ph_pct = avg_ph / avg_h * 100 if avg_h > 0 else 0
        rh_pct = avg_rh / avg_h * 100 if avg_h > 0 else 0
        print("  {:<35} {:>6.0f} {:>6.1f}% {:>6.1f}% {:>6.1f} ${:>6.0f} {:>6.1f}%".format(
            label, avg_h, ph_pct, rh_pct, avg_sw, avg_w, sc['win_pct']))

    # Top 3 detailed
    print()
    for sc in scorecards[:3]:
        print_scorecard(sc, BANK)
        print()

    # Show no-switch and STRIKER proxy for comparison
    refs = ["no-switch d1 SL10/TP5", "no-switch d0 SL10/TP5", "STRIKER-proxy SL3/TP3"]
    for ref in refs:
        sc = next((s for s in scorecards if s['tag'] == ref), None)
        if sc and sc not in scorecards[:3]:
            print("  --- REF: {} ---".format(ref))
            print_scorecard(sc, BANK)
            print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
