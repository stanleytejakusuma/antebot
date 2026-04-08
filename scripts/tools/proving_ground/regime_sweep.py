#!/usr/bin/env python3
"""Regime strategy parameter sweep — focused on the 3 design forks:
  1. Profit mode chance/multiplier (50%, 33%, 25%)
  2. Delayed IOL (delay 0, 1, 2, 3 losses before Mart)
  3. DD trigger % and rest duration

All configs use SL=10% TP=5% exits (no trail).
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000; DIV = 2500
BET_CAP_PCT = 10; SL_PCT = 10; TP_PCT = 5
REST_CHANCE = 95  # fixed at 95% for rest mode


def _regime_session(args):
    (s, profit_chance, mart_iol, delay,
     dd_trigger_pct, rest_duration, switch_mode) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    base = max(bank / DIV, 0.00101)

    # Profit mode
    p_payout = 0.99 * 100.0 / profit_chance - 1.0
    p_winp = profit_chance / 100.0

    # Rest mode (95% chance)
    r_payout = 0.99 * 100.0 / REST_CHANCE - 1.0
    r_winp = REST_CHANCE / 100.0

    # Exits
    sl_amt = bank * SL_PCT / 100
    tp_amt = bank * TP_PCT / 100

    # State
    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    rest_hands = 0; profit_hands = 0; switches = 0
    abandoned_chains = 0; chain_cost_abandoned = 0.0

    # IOL state
    mult = 1.0; in_mart = False; consec = 0; chain_cost = 0.0

    # Mode
    mode = 'profit'
    rest_ctr = 0
    entry_profit = 0.0

    def reset_chain():
        nonlocal mult, in_mart, consec, chain_cost, abandoned_chains, chain_cost_abandoned
        if chain_cost > base * 2:  # was mid-chain
            abandoned_chains += 1
            chain_cost_abandoned += chain_cost
        mult = 1.0; in_mart = False; consec = 0; chain_cost = 0.0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands,
                    switches, abandoned_chains, chain_cost_abandoned)

        # --- BET ---
        if mode == 'rest':
            bet = base
            winp = r_winp; payout = r_payout
        else:
            bet = base * mult
            winp = p_winp; payout = p_payout
            mx = bal * BET_CAP_PCT / 100
            if bet > mx: bet = mx
            if bet > bal * 0.95:
                reset_chain(); bet = base

        if bet > bal: bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered, rest_hands, profit_hands,
                    switches, abandoned_chains, chain_cost_abandoned)

        hands += 1; wagered += bet
        if mode == 'rest':
            rest_hands += 1
        else:
            profit_hands += 1

        # --- RESOLVE ---
        if rng.random() < winp:
            profit += bet * payout
            if mode == 'profit':
                reset_chain()
        else:
            profit -= bet
            if mode == 'profit':
                consec += 1
                chain_cost += bet

                # Delayed IOL: absorb first `delay` losses at flat
                if consec <= delay:
                    mult = 1  # stay flat
                else:
                    if not in_mart:
                        in_mart = True
                        mult = 1  # first Mart bet = flat (absorb), then escalate
                    else:
                        mult *= mart_iol
                    if bal > 0 and base * mult > bal * 0.95:
                        reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands,
                    switches, abandoned_chains, chain_cost_abandoned)
        if profit > peak:
            peak = profit

        # --- EXITS ---
        if profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands,
                    switches, abandoned_chains, chain_cost_abandoned)
        if profit >= tp_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands,
                    switches, abandoned_chains, chain_cost_abandoned)

        # --- MODE SWITCHING ---
        if switch_mode == 'dd_trigger':
            if mode == 'profit':
                dd = entry_profit - profit
                if dd > bank * dd_trigger_pct / 100:
                    mode = 'rest'; rest_ctr = rest_duration
                    reset_chain(); switches += 1
            elif mode == 'rest':
                rest_ctr -= 1
                if rest_ctr <= 0:
                    mode = 'profit'; entry_profit = profit
                    reset_chain(); switches += 1

        elif switch_mode == 'none':
            pass  # pure profit mode, no switching

    return (profit, False, hands, wagered, rest_hands, profit_hands,
            switches, abandoned_chains, chain_cost_abandoned)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 5000

    # (label, profit_chance, mart_iol, delay,
    #  dd_trigger_pct, rest_duration, switch_mode)
    configs = []

    # === FORK 1: PROFIT MODE CHANCE (with best DD trigger) ===
    for chance in [50, 33, 25]:
        iol = 3.0
        label = "{}% ({}x) delay=1 DD2 r100".format(chance, round(0.99*100/chance - 1, 2))
        configs.append((label, chance, iol, 1, 2, 100, 'dd_trigger'))

    # === FORK 1b: CHANCE without switching (baseline) ===
    for chance in [50, 33, 25]:
        iol = 3.0
        label = "{}% no-switch baseline".format(chance)
        configs.append((label, chance, iol, 1, 99, 0, 'none'))

    # === FORK 2: DELAYED IOL (at 50% with DD2 r100) ===
    for delay in [0, 1, 2, 3]:
        label = "50% delay={} DD2 r100".format(delay)
        configs.append((label, 50, 3.0, delay, 2, 100, 'dd_trigger'))

    # === FORK 2b: DELAYED IOL without switching ===
    for delay in [0, 1, 2, 3]:
        label = "50% delay={} no-switch".format(delay)
        configs.append((label, 50, 3.0, delay, 99, 0, 'none'))

    # === FORK 3: DD TRIGGER + REST DURATION (at 50%, delay=1) ===
    for dd in [1, 2, 3]:
        for rest in [30, 50, 100, 150, 200]:
            label = "DD{}% r={} (50%,d=1)".format(dd, rest)
            configs.append((label, 50, 3.0, 1, dd, rest, 'dd_trigger'))

    # === MART IOL SWEEP (at 50%, delay=1, DD2 r100) ===
    for iol in [2.0, 2.5, 3.0, 4.0, 5.0]:
        label = "IOL={}x DD2 r100 (50%,d=1)".format(iol)
        configs.append((label, 50, iol, 1, 2, 100, 'dd_trigger'))

    print()
    print("=" * 120)
    print("  REGIME STRATEGY PARAMETER SWEEP")
    print("  {} sessions | ${} bank | div={} | SL={}% TP={}% | rest@{}%".format(
        N, BANK, DIV, SL_PCT, TP_PCT, REST_CHANCE))
    print("  Sweeping: chance, delay, DD trigger, rest duration, IOL multiplier")
    print("=" * 120)

    all_results = {}
    scorecards = []

    for cfg in configs:
        label = cfg[0]
        args = [(s,) + cfg[1:] for s in range(N)]
        results = pool.map(_regime_session, args)
        all_results[label] = results
        sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        scorecards.append(sc)

    # === RANKING ===
    print()
    print_ranking(scorecards, BANK)

    # === FORK-BY-FORK ANALYSIS ===
    def fork_table(title, labels):
        print()
        print("  === {} ===".format(title))
        print("  {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>7} {:>7} {:>5}".format(
            'Config', 'G(%)', 'Mean', 'Median', 'Win%', 'Bust%', 'CVaR10', 'Hands', 'Aband'))
        print("  " + "-" * 100)
        for label in labels:
            sc = next(s for s in scorecards if s['tag'] == label)
            results = all_results[label]
            avg_hands = statistics.mean([r[2] for r in results])
            avg_aband = statistics.mean([r[7] for r in results])
            grade = "A+" if sc['G_pct'] > -0.5 else "A" if sc['G_pct'] > -1 else "B" if sc['G_pct'] > -2 else "C" if sc['G_pct'] > -4 else "D" if sc['G_pct'] > -8 else "F"
            print("  {:<35} {:>+6.2f}% ${:>+6.2f} ${:>+6.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} {:>6.0f} {:>5.1f}".format(
                label, sc['G_pct'], sc['mean'], sc['median'],
                sc['win_pct'], sc['bust_pct'], sc['CVaR10'], avg_hands, avg_aband))

    # Fork 1: Chance
    fork_table("FORK 1: PROFIT MODE CHANCE (with DD2 r100)", [
        c[0] for c in configs if "DD2 r100" in c[0] and "delay=1" in c[0]
    ])
    fork_table("FORK 1b: CHANCE BASELINES (no switching)", [
        c[0] for c in configs if "no-switch baseline" in c[0]
    ])

    # Fork 2: Delay
    fork_table("FORK 2: DELAYED IOL (50%, DD2 r100)", [
        c[0] for c in configs if "50% delay=" in c[0] and "DD2" in c[0]
    ])
    fork_table("FORK 2b: DELAYED IOL (50%, no switching)", [
        c[0] for c in configs if "50% delay=" in c[0] and "no-switch" in c[0]
    ])

    # Fork 3: DD + Rest
    fork_table("FORK 3: DD TRIGGER × REST DURATION", [
        c[0] for c in configs if "(50%,d=1)" in c[0] and "DD" in c[0] and "IOL" not in c[0]
    ])

    # IOL sweep
    fork_table("IOL MULTIPLIER SWEEP", [
        c[0] for c in configs if "IOL=" in c[0]
    ])

    # === TOP 5 DETAILED ===
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    for sc in scorecards[:5]:
        print_scorecard(sc, BANK)
        print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
