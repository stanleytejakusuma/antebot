#!/usr/bin/env python3
"""KRAIT adaptive IOL — vary Martingale multiplier based on SL proximity.

Concept stolen from Roberto's Multi IOL: graduated behavior.
But graduated on CUSHION TO SL (risk budget), not chain depth.

Aggressive IOL when flush, gentle IOL when near SL.
"""
import random, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000; BET_CAP_PCT = 10; REST_CHANCE = 98


def _krait(args):
    (s, chance, p_div, r_div, delay, base_iol,
     dd_pct, rest_dur, sl_pct, tp_pct,
     adaptive_mode, tiers) = args
    # adaptive_mode: 'fixed' (flat IOL) or 'cushion' (adaptive based on SL distance)
    # tiers: list of (cushion_threshold_pct, iol) sorted high→low
    #   e.g. [(7, 4.0), (4, 3.5), (2, 2.5), (0, 2.0)]

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    p_base = max(bank / p_div, 0.00101)
    r_base = max(bank / r_div, 0.00101)

    p_payout = 0.99 * 100.0 / chance - 1.0
    p_winp = chance / 100.0
    r_payout = 0.99 * 100.0 / REST_CHANCE - 1.0
    r_winp = REST_CHANCE / 100.0

    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else 1e18
    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else 1e18

    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    rest_hands = 0; profit_hands = 0; switches = 0

    mult = 1.0; in_mart = False; consec = 0
    mode = 'profit'; rest_ctr = 0; entry_profit = 0.0

    def reset_chain():
        nonlocal mult, in_mart, consec
        mult = 1.0; in_mart = False; consec = 0

    def get_iol():
        if adaptive_mode == 'fixed':
            return base_iol
        # Cushion = distance from SL
        cushion_pct = (profit + sl_amt) / bank * 100
        for threshold, iol in tiers:
            if cushion_pct >= threshold:
                return iol
        return tiers[-1][1]  # fallback to lowest

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        if mode == 'rest':
            bet = r_base; winp = r_winp; payout = r_payout
        else:
            bet = p_base * mult; winp = p_winp; payout = p_payout
            mx = bal * BET_CAP_PCT / 100
            if bet > mx: bet = mx
            if bet > bal * 0.95:
                reset_chain(); bet = p_base

        if bet > bal: bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        # SL-aware cap
        if sl_pct > 0:
            cushion = profit + sl_amt
            if cushion >= 0 and bet >= cushion:
                bet = max(0.001, cushion)

        hands += 1; wagered += bet
        if mode == 'rest': rest_hands += 1
        else: profit_hands += 1

        if rng.random() < winp:
            profit += bet * payout
            if mode == 'profit': reset_chain()
        else:
            profit -= bet
            if mode == 'profit':
                consec += 1
                if consec <= delay:
                    mult = 1
                else:
                    current_iol = get_iol()
                    if not in_mart:
                        in_mart = True; mult = 1
                    else:
                        mult *= current_iol
                    if bal > 0 and p_base * mult > bal * 0.95:
                        reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)
        if profit > peak: peak = profit

        if sl_pct > 0 and profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)
        if tp_pct > 0 and profit >= tp_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)

        if mode == 'profit':
            dd = entry_profit - profit
            if dd >= bank * dd_pct / 100:
                mode = 'rest'; rest_ctr = rest_dur; reset_chain(); switches += 1
        else:
            rest_ctr -= 1
            if rest_ctr <= 0:
                mode = 'profit'; entry_profit = profit; reset_chain(); switches += 1

    return (profit, False, hands, wagered, rest_hands, profit_hands, switches)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 10000

    BASE = (40, 75000, 30000, 1, 3.5, 3, 30, 5, 10)
    NO_TIERS = []

    configs = []

    # === BASELINE: flat 3.5x ===
    configs.append(("FLAT 3.5x (v2.0 baseline)",) + BASE + ('fixed', NO_TIERS))

    # === FLAT IOL controls ===
    for iol in [2.0, 2.5, 3.0, 4.0, 4.5, 5.0]:
        label = "FLAT {}x".format(iol)
        configs.append((label, 40, 75000, 30000, 1, iol, 3, 30, 5, 10, 'fixed', NO_TIERS))

    # === ADAPTIVE: aggressive when flush, gentle near SL ===
    # Tier format: [(cushion_pct, iol), ...] sorted high→low
    adaptive_configs = [
        # Gentle gradient
        ("ADAPT 4.0/3.5/2.5/2.0",
         [(7, 4.0), (4, 3.5), (2, 2.5), (0, 2.0)]),

        ("ADAPT 4.5/3.5/2.5/2.0",
         [(7, 4.5), (4, 3.5), (2, 2.5), (0, 2.0)]),

        ("ADAPT 5.0/3.5/2.5/2.0",
         [(7, 5.0), (4, 3.5), (2, 2.5), (0, 2.0)]),

        # More aggressive top tier
        ("ADAPT 5.0/4.0/3.0/2.0",
         [(7, 5.0), (4, 4.0), (2, 3.0), (0, 2.0)]),

        ("ADAPT 4.0/3.5/3.0/2.5",
         [(7, 4.0), (4, 3.5), (2, 3.0), (0, 2.5)]),

        # Two-tier (simple)
        ("ADAPT 4.0/2.5 split@4%",
         [(4, 4.0), (0, 2.5)]),

        ("ADAPT 4.5/2.5 split@4%",
         [(4, 4.5), (0, 2.5)]),

        ("ADAPT 5.0/2.0 split@4%",
         [(4, 5.0), (0, 2.0)]),

        ("ADAPT 4.0/3.0 split@3%",
         [(3, 4.0), (0, 3.0)]),

        ("ADAPT 4.0/2.5 split@3%",
         [(3, 4.0), (0, 2.5)]),

        ("ADAPT 5.0/2.5 split@3%",
         [(3, 5.0), (0, 2.5)]),

        # Three-tier
        ("ADAPT 5.0/3.5/2.0 @7/3",
         [(7, 5.0), (3, 3.5), (0, 2.0)]),

        ("ADAPT 4.5/3.0/2.0 @6/3",
         [(6, 4.5), (3, 3.0), (0, 2.0)]),

        # Aggressive top, survival bottom
        ("ADAPT 6.0/3.5/1.5 @7/2",
         [(7, 6.0), (2, 3.5), (0, 1.5)]),

        # Very gentle near SL
        ("ADAPT 4.0/3.5/2.0/1.5",
         [(7, 4.0), (4, 3.5), (2, 2.0), (0, 1.5)]),

        # Aggressive throughout, gentle only at death's door
        ("ADAPT 4.0/4.0/4.0/2.0",
         [(7, 4.0), (4, 4.0), (2, 4.0), (0, 2.0)]),

        ("ADAPT 3.5/3.5/3.5/2.0",
         [(3, 3.5), (0, 2.0)]),
    ]

    for label, tiers in adaptive_configs:
        configs.append((label,) + BASE + ('cushion', tiers))

    # === ADAPTIVE at different chances ===
    best_tier = [(7, 4.5), (4, 3.5), (2, 2.5), (0, 2.0)]
    for ch in [38, 40, 42, 45, 48]:
        label = "{}% ADAPT 4.5/3.5/2.5/2.0".format(ch)
        configs.append((label, ch, 75000, 30000, 1, 3.5, 3, 30, 5, 10, 'cushion', best_tier))

    print()
    print("=" * 120)
    print("  KRAIT ADAPTIVE IOL TEST")
    print("  {} sessions | ${} bank | 40% chance | pdiv=75k | SL5/TP10 | rest@98%".format(N, BANK))
    print("  IOL varies based on cushion to SL (distance from stop loss)")
    print("=" * 120)

    all_results = {}
    scorecards = []

    for cfg in configs:
        label = cfg[0]
        args = [(s,) + cfg[1:] for s in range(N)]
        results = pool.map(_krait, args)
        all_results[label] = results
        sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        ah = statistics.mean([r[2] for r in results])
        aw = statistics.mean([r[3] for r in results])
        sc['_h'] = ah; sc['_w'] = aw
        scorecards.append(sc)

    scorecards.sort(key=lambda x: x['G'], reverse=True)

    # === RANKING ===
    print()
    print("  {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>6} {:>5}".format(
        'Config', 'G(%)', 'Mean', 'Median', 'Win%', 'Hands', 'Wag', 'HL'))
    print("  " + "-" * 85)
    for s in scorecards:
        hl = '{:.0f}'.format(s['half_life']) if s['half_life'] < 99999 else 'inf'
        print("  {:<35} {:>+6.2f}% ${:>+5.2f} ${:>+5.2f} {:>5.1f}% {:>5.0f} ${:>5.0f} {:>5}".format(
            s['tag'], s['G_pct'], s['mean'], s['median'],
            s['win_pct'], s['_h'], s['_w'], hl))

    # === TOP 5 ===
    print()
    for s in scorecards[:5]:
        print_scorecard(s, BANK)
        print()

    # Baseline comparison
    baseline = next(s for s in scorecards if 'v2.0' in s['tag'])
    if baseline not in scorecards[:5]:
        print("  --- BASELINE ---")
        print_scorecard(baseline, BANK)
        print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
