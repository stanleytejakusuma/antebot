#!/usr/bin/env python3
"""KRAIT hybrid exit test — SL/TP + trailing stop as profit lock.

Trail activates after reaching +X% profit, locks Y% below peak.
SL/TP still active as hard boundaries. Trail adds a third exit
that captures partial profits from sessions that peak but don't reach TP.

Tests at the v2.0 config: 40% chance, IOL 3.5x, pdiv=75k, SL5/TP10.
"""
import random, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000; BET_CAP_PCT = 10; REST_CHANCE = 98


def _krait(args):
    (s, chance, p_div, r_div, delay, mart_iol,
     dd_pct, rest_dur, sl_pct, tp_pct,
     trail_activate_pct, trail_range_pct) = args

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
    trail_activate_amt = bank * trail_activate_pct / 100 if trail_activate_pct > 0 else 1e18
    trail_range_amt = bank * trail_range_pct / 100 if trail_range_pct > 0 else 0

    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    rest_hands = 0; profit_hands = 0; switches = 0
    trail_active = False; exit_type = "MAX_HANDS"

    mult = 1.0; in_mart = False; consec = 0
    mode = 'profit'; rest_ctr = 0; entry_profit = 0.0

    def reset_chain():
        nonlocal mult, in_mart, consec
        mult = 1.0; in_mart = False; consec = 0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches, "BUST")

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
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches, "BUST")

        # SL-aware cap
        if sl_pct > 0:
            cushion = profit + sl_amt
            if cushion >= 0 and bet >= cushion:
                bet = max(0.001, cushion)

        # Trail-aware cap
        if trail_active and trail_range_amt > 0:
            trail_floor = peak - trail_range_amt
            margin = profit - trail_floor
            if margin > 0 and bet > margin:
                bet = max(0.001, margin)

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
                    if not in_mart:
                        in_mart = True; mult = 1
                    else:
                        mult *= mart_iol
                    if bal > 0 and p_base * mult > bal * 0.95:
                        reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches, "BUST")
        if profit > peak: peak = profit

        # === EXITS (priority: TP > Trail > SL) ===
        if tp_pct > 0 and profit >= tp_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches, "TP")
        if sl_pct > 0 and profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches, "SL")

        # Trail activation
        if not trail_active and trail_activate_pct > 0 and profit >= trail_activate_amt:
            trail_active = True
        # Trail fire
        if trail_active and trail_range_amt > 0:
            trail_floor = peak - trail_range_amt
            if profit <= trail_floor:
                return (profit, False, hands, wagered, rest_hands, profit_hands, switches, "TRAIL")

        # Regime switching
        if mode == 'profit':
            dd = entry_profit - profit
            if dd >= bank * dd_pct / 100:
                mode = 'rest'; rest_ctr = rest_dur; reset_chain(); switches += 1
        else:
            rest_ctr -= 1
            if rest_ctr <= 0:
                mode = 'profit'; entry_profit = profit; reset_chain(); switches += 1

    return (profit, False, hands, wagered, rest_hands, profit_hands, switches, exit_type)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 10000

    # Base config: KRAIT v2.0
    BASE = (40, 75000, 30000, 1, 3.5, 3, 30, 5, 10)

    # (label, ..., trail_activate_pct, trail_range_pct)
    configs = []

    # === BASELINE: no trail ===
    configs.append(("NO TRAIL (v2.0 baseline)",) + BASE + (0, 0))

    # === TRAIL ACTIVATION SWEEP (fixed range=2%) ===
    for act in [2, 3, 4, 5, 6, 7, 8]:
        label = "trail act={}% rng=2%".format(act)
        configs.append((label,) + BASE + (act, 2))

    # === TRAIL RANGE SWEEP (fixed activation=3%) ===
    for rng_pct in [1, 1.5, 2, 2.5, 3, 4, 5]:
        label = "trail act=3% rng={}%".format(rng_pct)
        configs.append((label,) + BASE + (3, rng_pct))

    # === TRAIL RANGE SWEEP (fixed activation=5%) ===
    for rng_pct in [1, 1.5, 2, 2.5, 3, 4, 5]:
        label = "trail act=5% rng={}%".format(rng_pct)
        configs.append((label,) + BASE + (5, rng_pct))

    # === COMBINED: tight trail (act=3%, rng=1-2%) at different SL/TP ===
    for sl, tp in [(5, 10), (5, 15), (3, 10), (7, 10)]:
        label = "SL{}/TP{} trail 3%/2%".format(sl, tp)
        configs.append((label, 40, 75000, 30000, 1, 3.5, 3, 30, sl, tp, 3, 2))
        label = "SL{}/TP{} no trail".format(sl, tp)
        configs.append((label, 40, 75000, 30000, 1, 3.5, 3, 30, sl, tp, 0, 0))

    # === TRAIL-ONLY (no TP, trail replaces it) ===
    for act in [3, 5]:
        for rng_pct in [2, 3]:
            label = "SL5/noTP trail {}%/{}%".format(act, rng_pct)
            configs.append((label, 40, 75000, 30000, 1, 3.5, 3, 30, 5, 0, act, rng_pct))

    print()
    print("=" * 120)
    print("  KRAIT HYBRID EXIT TEST — SL/TP + TRAILING STOP")
    print("  {} sessions | ${} bank | 40% chance | IOL 3.5x | pdiv=75k | rest@98%".format(N, BANK))
    print("  Trail = profit lock alongside hard SL/TP exits")
    print("=" * 120)

    all_results = {}
    scorecards = []

    for cfg in configs:
        label = cfg[0]
        args = [(s,) + cfg[1:] for s in range(N)]
        results = pool.map(_krait, args)
        all_results[label] = results
        sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)

        # Exit type breakdown
        exits = [r[7] for r in results]
        tp_count = exits.count("TP")
        sl_count = exits.count("SL")
        trail_count = exits.count("TRAIL")
        other = len(exits) - tp_count - sl_count - trail_count
        avg_h = statistics.mean([r[2] for r in results])
        avg_w = statistics.mean([r[3] for r in results])

        sc['_tp'] = tp_count / len(exits) * 100
        sc['_sl'] = sl_count / len(exits) * 100
        sc['_trail'] = trail_count / len(exits) * 100
        sc['_h'] = avg_h; sc['_w'] = avg_w
        scorecards.append(sc)

    # === RANKING ===
    print()
    print_ranking(scorecards, BANK)

    # === EXIT BREAKDOWN ===
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    print("  {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>6} {:>6} {:>5}".format(
        'Config', 'G(%)', 'Mean', 'Median', 'Win%', 'TP%', 'SL%', 'Trail%', 'HL'))
    print("  " + "-" * 95)
    for s in scorecards:
        hl = '{:.0f}'.format(s['half_life']) if s['half_life'] < 99999 else 'inf'
        print("  {:<35} {:>+6.2f}% ${:>+5.2f} ${:>+5.2f} {:>5.1f}% {:>5.1f}% {:>5.1f}% {:>5.1f}% {:>5}".format(
            s['tag'], s['G_pct'], s['mean'], s['median'],
            s['win_pct'], s['_tp'], s['_sl'], s['_trail'], hl))

    # === TOP 5 ===
    print()
    for s in scorecards[:5]:
        print_scorecard(s, BANK)
        print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
