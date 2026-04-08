#!/usr/bin/env python3
"""KRAIT dynamic chance test — increase win chance on consecutive losses.

DoubleDose's key mechanic: chance goes UP on loss, resets on win.
Test this within KRAIT's existing 2-regime (PROFIT + REST) architecture.

The trade-off: higher chance = more likely to end chain (good) but
lower payout per recovery (bad). Which effect dominates?
"""
import random, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking

SEED = 42
BANK = 100
MAX_HANDS = 15000
BET_CAP_PCT = 10
REST_CHANCE = 98


def payout(chance_pct):
    return 0.99 * 100.0 / chance_pct - 1.0


def _sim(args):
    (s, cfg) = args
    rng = random.Random(SEED * 100000 + s)
    bank = BANK

    base_chance = cfg['chance']
    p_div = cfg['p_div']
    r_div = cfg['r_div']
    delay = cfg['delay']
    mart_iol = cfg['mart_iol']
    dd_pct = cfg['dd_pct']
    rest_dur = cfg['rest_dur']
    sl = cfg.get('sl', 0)
    tp = cfg.get('tp', 0)

    # Dynamic chance params
    chance_bump = cfg.get('chance_bump', 0)       # additive increase per loss
    chance_mult = cfg.get('chance_mult', 1.0)     # multiplicative increase per loss
    chance_cap = cfg.get('chance_cap', 95)         # never exceed this

    p_base = max(bank / p_div, 0.00101)
    r_base = max(bank / r_div, 0.00101)
    sl_amt = bank * sl / 100 if sl > 0 else 1e18
    tp_amt = bank * tp / 100 if tp > 0 else 1e18
    r_pay = payout(REST_CHANCE)
    r_wp = REST_CHANCE / 100.0

    profit = 0.0
    peak = 0.0
    hands = 0
    wagered = 0.0
    switches = 0

    mult = 1.0
    in_mart = False
    consec = 0
    current_chance = base_chance

    mode = 'profit'
    rest_ctr = 0
    entry_profit = 0.0
    rest_hands = 0
    profit_hands = 0

    def reset_chain():
        nonlocal mult, in_mart, consec, current_chance
        mult = 1.0
        in_mart = False
        consec = 0
        current_chance = base_chance

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        if mode == 'rest':
            bet = r_base
            winp = r_wp
            pay = r_pay
            rest_hands += 1
        else:
            bet = p_base * mult
            winp = current_chance / 100.0
            pay = payout(current_chance)
            mx = bal * BET_CAP_PCT / 100
            if bet > mx:
                bet = mx
            if bet > bal * 0.95:
                reset_chain()
                bet = p_base
                winp = base_chance / 100.0
                pay = payout(base_chance)
            profit_hands += 1

        if bet > bal:
            bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        hands += 1
        wagered += bet

        if rng.random() < winp:
            profit += bet * pay
            if mode == 'profit':
                reset_chain()
        else:
            profit -= bet
            if mode == 'profit':
                consec += 1
                if consec <= delay:
                    mult = 1.0
                else:
                    if not in_mart:
                        in_mart = True
                        mult = 1.0
                    else:
                        mult *= mart_iol
                    if bal > 0 and p_base * mult > bal * 0.95:
                        reset_chain()

                # Dynamic chance: increase on loss
                if chance_bump > 0:
                    current_chance = min(current_chance + chance_bump, chance_cap)
                if chance_mult > 1.0:
                    current_chance = min(current_chance * chance_mult, chance_cap)

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)
        if profit > peak:
            peak = profit
        if profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)
        if profit >= tp_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)

        if mode == 'profit':
            dd = entry_profit - profit
            if dd >= bank * dd_pct / 100:
                mode = 'rest'
                rest_ctr = rest_dur
                reset_chain()
                switches += 1
        else:
            rest_ctr -= 1
            if rest_ctr <= 0:
                mode = 'profit'
                entry_profit = profit
                reset_chain()
                switches += 1

    return (profit, False, hands, wagered, rest_hands, profit_hands, switches)


def eval_cfg(label, cfg, N=5000):
    args = [(s, cfg) for s in range(N)]
    results = pool.map(_sim, args)
    sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
    avg_h = statistics.mean(r[2] for r in results)
    avg_w = statistics.mean(r[3] for r in results)
    avg_sw = statistics.mean(r[6] for r in results)
    return {
        'label': label,
        'G': sc['G_pct'],
        'median': sc['median'],
        'win_pct': sc['win_pct'],
        'hl': sc['half_life'],
        'hands': avg_h,
        'wagered': avg_w,
        'sw': avg_sw,
    }


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())

    base_cfg = {
        'chance': 48, 'p_div': 5000, 'r_div': 15000,
        'delay': 1, 'mart_iol': 3.0,
        'dd_pct': 3, 'rest_dur': 30,
    }

    tests = []

    # === BASELINE: no dynamic chance ===
    tests.append(('KRAIT baseline (no dyn)', {**base_cfg}))

    # === Additive bump per loss ===
    for bump in [1, 2, 3, 5, 8, 10]:
        for cap in [60, 70, 80, 90]:
            label = f'bump+{bump} cap={cap}'
            tests.append((label, {**base_cfg, 'chance_bump': bump, 'chance_cap': cap}))

    # === Multiplicative per loss (DoubleDose style) ===
    for m in [1.02, 1.05, 1.08, 1.10]:
        for cap in [70, 80, 90]:
            label = f'mult*{m} cap={cap}'
            tests.append((label, {**base_cfg, 'chance_mult': m, 'chance_cap': cap}))

    # === Different base chances with dynamic ===
    for bc in [40, 45, 48, 50, 55]:
        label = f'base={bc}% bump+3 cap=70'
        tests.append((label, {**base_cfg, 'chance': bc, 'chance_bump': 3, 'chance_cap': 70}))

    # === Higher profit divider with dynamic ===
    for pd in [5000, 10000, 20000]:
        label = f'div={pd} bump+3 cap=70'
        tests.append((label, {**base_cfg, 'p_div': pd, 'chance_bump': 3, 'chance_cap': 70}))

    # === With SL/TP ===
    for sl, tp in [(5, 5), (5, 8), (10, 10)]:
        label = f'SL{sl}/TP{tp} bump+3 cap=70'
        tests.append((label, {**base_cfg, 'chance_bump': 3, 'chance_cap': 70, 'sl': sl, 'tp': tp}))
        label = f'SL{sl}/TP{tp} baseline'
        tests.append((label, {**base_cfg, 'sl': sl, 'tp': tp}))

    print()
    print('=' * 110)
    print('  KRAIT DYNAMIC CHANCE TEST')
    print(f'  {5000} sessions | ${BANK} bank | base={base_cfg["chance"]}% | IOL {base_cfg["mart_iol"]}x | delay={base_cfg["delay"]}')
    print('=' * 110)

    rows = []
    for label, cfg in tests:
        r = eval_cfg(label, cfg)
        rows.append(r)

    rows.sort(key=lambda x: x['G'], reverse=True)

    print()
    hdr = f"  {'Strategy':<35} {'G':>7} {'Med':>7} {'Win%':>6} {'Hands':>6} {'Wag':>8} {'Sw':>5} {'HL':>5}"
    print(hdr)
    print('  ' + '-' * (len(hdr) - 2))
    for x in rows:
        hl = 'inf' if x['hl'] >= 99999 else f"{x['hl']:.0f}"
        print(f"  {x['label']:<35} {x['G']:>+6.2f}% ${x['median']:>+6.2f} {x['win_pct']:>5.1f}% {x['hands']:>5.0f} ${x['wagered']:>7.0f} {x['sw']:>5.1f} {hl:>5}")

    print()
    print('  --- TOP 5 ---')
    for x in rows[:5]:
        hl = 'inf' if x['hl'] >= 99999 else f"{x['hl']:.0f}"
        print(f"  {x['label']:<35} G={x['G']:>+6.2f}% median=${x['median']:>+6.2f} win={x['win_pct']:>5.1f}% HL={hl}")

    print()
    print('  --- BASELINES ---')
    for x in rows:
        if 'baseline' in x['label']:
            hl = 'inf' if x['hl'] >= 99999 else f"{x['hl']:.0f}"
            print(f"  {x['label']:<35} G={x['G']:>+6.2f}% median=${x['median']:>+6.2f} win={x['win_pct']:>5.1f}% HL={hl}")

    pool.close()
    pool.join()
    print(f'\n  Runtime: {time.time() - t0:.1f}s')
    print('=' * 110)
