#!/usr/bin/env python3
"""KRAIT fine-grained chance sweep — find optimal profit mode chance.

Tests 35%-55% in 1% increments at the user's live config:
  profitDivider=75000, wagerDivider=30000, SL5/TP10, DD3 r30 @98%

Also sweeps divider ratios and SL/TP combos at the winning chance.
"""
import random, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000; BET_CAP_PCT = 10; REST_CHANCE = 98


def _krait(args):
    (s, chance, p_div, r_div, delay, mart_iol,
     dd_pct, rest_dur, sl_pct, tp_pct) = args

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
                    if not in_mart:
                        in_mart = True; mult = 1
                    else:
                        mult *= mart_iol
                    if bal > 0 and p_base * mult > bal * 0.95:
                        reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)
        if profit > peak: peak = profit

        if sl_pct > 0 and profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)
        if tp_pct > 0 and profit >= tp_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)

        # Regime switching
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

    # (label, chance, p_div, r_div, delay, mart_iol, dd_pct, rest_dur, sl_pct, tp_pct)
    configs = []

    # ================================================================
    # SWEEP 1: Chance 35%-55% at user's live config
    # ================================================================
    for ch in range(35, 56):
        label = "{}% pdiv=75k rdiv=30k".format(ch)
        configs.append((label, ch, 75000, 30000, 1, 3.0, 3, 30, 5, 10))

    # ================================================================
    # SWEEP 2: Divider ratio sweep at key chances (40%, 45%, 48%)
    # ================================================================
    for ch in [40, 45, 48]:
        for p_div, r_div in [
            (50000, 20000),
            (75000, 30000),    # current
            (100000, 40000),
            (150000, 60000),
            (75000, 75000),    # same divider both modes
            (75000, 150000),   # rest bets SMALLER than profit
        ]:
            label = "{}% p{}k/r{}k".format(ch, p_div // 1000, r_div // 1000)
            configs.append((label, ch, p_div, r_div, 1, 3.0, 3, 30, 5, 10))

    # ================================================================
    # SWEEP 3: SL/TP combos at best chances
    # ================================================================
    for ch in [40, 45, 48]:
        for sl, tp in [(3, 5), (5, 5), (5, 10), (5, 15), (7, 10), (10, 10), (10, 15)]:
            label = "{}% SL{}/TP{} p75k".format(ch, sl, tp)
            configs.append((label, ch, 75000, 30000, 1, 3.0, 3, 30, sl, tp))

    # ================================================================
    # SWEEP 4: IOL multiplier at key chances
    # ================================================================
    for ch in [40, 45, 48]:
        for iol in [2.0, 2.5, 3.0, 3.5, 4.0]:
            label = "{}% IOL={}x p75k".format(ch, iol)
            configs.append((label, ch, 75000, 30000, 1, iol, 3, 30, 5, 10))

    # ================================================================
    # SWEEP 5: Delay at key chances
    # ================================================================
    for ch in [40, 45, 48]:
        for d in [0, 1, 2, 3]:
            label = "{}% d={} p75k".format(ch, d)
            configs.append((label, ch, 75000, 30000, d, 3.0, 3, 30, 5, 10))

    print()
    print("=" * 120)
    print("  KRAIT CHANCE SWEEP — FINE-GRAINED OPTIMIZATION")
    print("  {} sessions | ${} bank | rest@{}% | betcap={}%".format(
        N, BANK, REST_CHANCE, BET_CAP_PCT))
    print("  Base config: delay=1, IOL=3x, DD3% r=30, SL5/TP10")
    print("=" * 120)

    all_results = {}
    scorecards_all = []

    for cfg in configs:
        label = cfg[0]
        args = [(s,) + cfg[1:] for s in range(N)]
        results = pool.map(_krait, args)
        all_results[label] = results
        sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        ah = statistics.mean([r[2] for r in results])
        aw = statistics.mean([r[3] for r in results])
        asw = statistics.mean([r[6] for r in results])
        sc['_h'] = ah; sc['_w'] = aw; sc['_sw'] = asw
        scorecards_all.append(sc)

    # ================================================================
    # RESULTS
    # ================================================================

    def show_group(title, prefix):
        grp = [s for s in scorecards_all if s['tag'].startswith(prefix) or prefix in s['tag']]
        if not grp: return
        grp.sort(key=lambda x: x['G'], reverse=True)
        print()
        print("  === {} ===".format(title))
        print("  {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>6} {:>5}".format(
            'Config', 'G(%)', 'Mean', 'Median', 'Win%', 'Hands', 'Sw', 'HL'))
        print("  " + "-" * 85)
        for s in grp:
            hl = '{:.0f}'.format(s['half_life']) if s['half_life'] < 99999 else 'inf'
            print("  {:<35} {:>+6.2f}% ${:>+5.2f} ${:>+5.2f} {:>5.1f}% {:>5.0f} {:>5.1f} {:>5}".format(
                s['tag'], s['G_pct'], s['mean'], s['median'],
                s['win_pct'], s['_h'], s['_sw'], hl))

    # Sweep 1: Chance
    show_group("CHANCE SWEEP 35%-55% (pdiv=75k, SL5/TP10)", "% pdiv=75k rdiv=30k")

    # Sweep 2: Divider ratios (show for best 3 chances from sweep 1)
    # First find top 3 chances
    chance_grp = [s for s in scorecards_all if "pdiv=75k rdiv=30k" in s['tag']]
    chance_grp.sort(key=lambda x: x['G'], reverse=True)
    print()
    print("  === TOP 5 CHANCES ===")
    for s in chance_grp[:5]:
        hl = '{:.0f}'.format(s['half_life']) if s['half_life'] < 99999 else 'inf'
        print("  {:<35} G={:>+6.2f}% median=${:>+5.2f} win={:>5.1f}% HL={}".format(
            s['tag'], s['G_pct'], s['median'], s['win_pct'], hl))

    for ch in [40, 45, 48]:
        show_group("DIVIDER RATIO ({}%)".format(ch), "{}% p".format(ch))

    for ch in [40, 45, 48]:
        show_group("SL/TP SWEEP ({}%)".format(ch), "{}% SL".format(ch))

    for ch in [40, 45, 48]:
        show_group("IOL SWEEP ({}%)".format(ch), "{}% IOL".format(ch))

    for ch in [40, 45, 48]:
        show_group("DELAY SWEEP ({}%)".format(ch), "{}% d=".format(ch))

    # Top 10 overall
    scorecards_all.sort(key=lambda x: x['G'], reverse=True)
    print()
    print("  === TOP 10 OVERALL ===")
    print("  {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>5}".format(
        'Config', 'G(%)', 'Mean', 'Median', 'Win%', 'Hands', 'HL'))
    print("  " + "-" * 80)
    for s in scorecards_all[:10]:
        hl = '{:.0f}'.format(s['half_life']) if s['half_life'] < 99999 else 'inf'
        print("  {:<35} {:>+6.2f}% ${:>+5.2f} ${:>+5.2f} {:>5.1f}% {:>5.0f} {:>5}".format(
            s['tag'], s['G_pct'], s['mean'], s['median'],
            s['win_pct'], s['_h'], hl))

    # Top 3 detailed
    print()
    for s in scorecards_all[:3]:
        print_scorecard(s, BANK)
        print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
