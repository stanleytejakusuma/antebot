#!/usr/bin/env python3
"""KRAIT GRIND architecture test — 3-regime: GRIND (85%) + RECOVER (48%) + REST (98%).

Thesis: Spend most time at high-chance flat grind (upward drift),
switch to low-chance Mart only when drawdown needs real recovery,
REST as cooldown circuit breaker.

Compare against:
- Current KRAIT (48% profit + 98% rest)
- Pure 85% grind with Mart (DoubleDose-like)
- Pure 48% Mart (KRAIT without rest)
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking

SEED = 42
BANK = 100
MAX_HANDS = 15000
BET_CAP_PCT = 10


def payout_for_chance(chance_pct):
    return 0.99 * 100.0 / chance_pct - 1.0


def _sim(args):
    (s, cfg) = args
    rng = random.Random(SEED * 100000 + s)
    bank = BANK

    grind_chance = cfg.get('grind_chance', 85)
    recover_chance = cfg.get('recover_chance', 48)
    rest_chance = cfg.get('rest_chance', 98)
    grind_div = cfg.get('grind_div', 5000)
    recover_div = cfg.get('recover_div', 5000)
    rest_div = cfg.get('rest_div', 15000)
    delay = cfg.get('delay', 1)
    mart_iol = cfg.get('mart_iol', 3.0)
    dd_trigger_pct = cfg.get('dd_trigger_pct', 3)
    rest_dur = cfg.get('rest_dur', 30)
    sl_pct = cfg.get('sl_pct', 0)
    tp_pct = cfg.get('tp_pct', 0)
    recover_target = cfg.get('recover_target', 'entry')  # 'entry' or 'zero'
    use_grind = cfg.get('use_grind', True)
    use_recover = cfg.get('use_recover', True)
    use_rest = cfg.get('use_rest', True)

    grind_base = max(bank / grind_div, 0.00101)
    recover_base = max(bank / recover_div, 0.00101)
    rest_base = max(bank / rest_div, 0.00101)

    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else 1e18
    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else 1e18

    g_pay = payout_for_chance(grind_chance)
    g_wp = grind_chance / 100.0
    r_pay = payout_for_chance(recover_chance)
    r_wp = recover_chance / 100.0
    rest_pay = payout_for_chance(rest_chance)
    rest_wp = rest_chance / 100.0

    profit = 0.0
    peak = 0.0
    hands = 0
    wagered = 0.0
    switches = 0

    mult = 1.0
    in_mart = False
    consec = 0

    if use_grind:
        mode = 'grind'
    elif use_recover:
        mode = 'recover'
    else:
        mode = 'rest'

    rest_ctr = 0
    entry_profit = 0.0
    recover_entry = 0.0

    grind_hands = 0
    recover_hands = 0
    rest_hands = 0

    grind_entries = 1 if mode == 'grind' else 0
    recover_entries = 0
    rest_entries = 0

    def reset_chain():
        nonlocal mult, in_mart, consec
        mult = 1.0
        in_mart = False
        consec = 0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered,
                    grind_hands, recover_hands, rest_hands,
                    switches, grind_entries, recover_entries, rest_entries)

        if mode == 'grind':
            bet = grind_base
            winp = g_wp
            pay = g_pay
            grind_hands += 1
        elif mode == 'recover':
            bet = recover_base * mult
            winp = r_wp
            pay = r_pay
            mx = bal * BET_CAP_PCT / 100
            if bet > mx:
                bet = mx
            if bet > bal * 0.95:
                reset_chain()
                bet = recover_base
            recover_hands += 1
        else:  # rest
            bet = rest_base
            winp = rest_wp
            pay = rest_pay
            rest_hands += 1

        if bet > bal:
            bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered,
                    grind_hands, recover_hands, rest_hands,
                    switches, grind_entries, recover_entries, rest_entries)

        hands += 1
        wagered += bet

        if rng.random() < winp:
            profit += bet * pay
            if mode == 'recover':
                reset_chain()
        else:
            profit -= bet
            if mode == 'recover':
                consec += 1
                if consec <= delay:
                    mult = 1.0
                else:
                    if not in_mart:
                        in_mart = True
                        mult = 1.0
                    else:
                        mult *= mart_iol
                    if bal > 0 and recover_base * mult > bal * 0.95:
                        reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered,
                    grind_hands, recover_hands, rest_hands,
                    switches, grind_entries, recover_entries, rest_entries)

        if profit > peak:
            peak = profit

        if profit <= -sl_amt:
            return (profit, False, hands, wagered,
                    grind_hands, recover_hands, rest_hands,
                    switches, grind_entries, recover_entries, rest_entries)
        if profit >= tp_amt:
            return (profit, False, hands, wagered,
                    grind_hands, recover_hands, rest_hands,
                    switches, grind_entries, recover_entries, rest_entries)

        # === REGIME SWITCHING ===
        if mode == 'grind':
            dd = entry_profit - profit
            if dd >= bank * dd_trigger_pct / 100:
                if use_recover:
                    mode = 'recover'
                    recover_entry = profit
                    recover_entries += 1
                elif use_rest:
                    mode = 'rest'
                    rest_ctr = rest_dur
                    rest_entries += 1
                switches += 1
                reset_chain()
        elif mode == 'recover':
            if profit >= recover_entry:
                if use_grind:
                    mode = 'grind'
                    entry_profit = profit
                    grind_entries += 1
                switches += 1
                reset_chain()
            else:
                rec_dd = recover_entry - profit
                if rec_dd >= bank * dd_trigger_pct / 100:
                    if use_rest:
                        mode = 'rest'
                        rest_ctr = rest_dur
                        rest_entries += 1
                    elif use_grind:
                        mode = 'grind'
                        entry_profit = profit
                        grind_entries += 1
                    switches += 1
                    reset_chain()
        elif mode == 'rest':
            rest_ctr -= 1
            if rest_ctr <= 0:
                if use_grind:
                    mode = 'grind'
                    entry_profit = profit
                    grind_entries += 1
                elif use_recover:
                    mode = 'recover'
                    recover_entry = profit
                    recover_entries += 1
                switches += 1
                reset_chain()

    return (profit, False, hands, wagered,
            grind_hands, recover_hands, rest_hands,
            switches, grind_entries, recover_entries, rest_entries)


def eval_cfg(label, cfg, N=5000):
    args = [(s, cfg) for s in range(N)]
    results = pool.map(_sim, args)
    sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
    avg_h = statistics.mean(r[2] for r in results)
    avg_w = statistics.mean(r[3] for r in results)
    avg_gh = statistics.mean(r[4] for r in results)
    avg_rech = statistics.mean(r[5] for r in results)
    avg_rsth = statistics.mean(r[6] for r in results)
    avg_sw = statistics.mean(r[7] for r in results)
    return {
        'label': label,
        'G': sc['G_pct'],
        'median': sc['median'],
        'mean': sc['mean'],
        'win_pct': sc['win_pct'],
        'hl': sc['half_life'],
        'hands': avg_h,
        'wagered': avg_w,
        'grind_pct': avg_gh / avg_h * 100 if avg_h else 0,
        'recover_pct': avg_rech / avg_h * 100 if avg_h else 0,
        'rest_pct': avg_rsth / avg_h * 100 if avg_h else 0,
        'sw': avg_sw,
    }


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())

    tests = []

    # === BASELINE: Current KRAIT (48% profit + 98% rest) ===
    tests.append(('KRAIT-current (48+98)', {
        'use_grind': False, 'use_recover': True, 'use_rest': True,
        'recover_chance': 48, 'rest_chance': 98,
        'recover_div': 5000, 'rest_div': 15000,
        'delay': 1, 'mart_iol': 3.0,
        'dd_trigger_pct': 3, 'rest_dur': 30,
    }))

    # === BASELINE: Pure 48% Mart, no rest ===
    tests.append(('pure-48-mart', {
        'use_grind': False, 'use_recover': True, 'use_rest': False,
        'recover_chance': 48, 'recover_div': 5000,
        'delay': 1, 'mart_iol': 3.0,
        'dd_trigger_pct': 3,
    }))

    # === BASELINE: Pure 85% grind, no Mart (just flat) ===
    tests.append(('pure-85-flat', {
        'use_grind': True, 'use_recover': False, 'use_rest': False,
        'grind_chance': 85, 'grind_div': 5000,
        'dd_trigger_pct': 99,
    }))

    # === NEW: GRIND 85% + RECOVER 48% + REST 98% ===
    for g_div in [5000, 10000, 20000]:
        for r_div in [5000, 10000]:
            label = f'G85+R48+REST gd={g_div} rd={r_div}'
            tests.append((label, {
                'use_grind': True, 'use_recover': True, 'use_rest': True,
                'grind_chance': 85, 'recover_chance': 48, 'rest_chance': 98,
                'grind_div': g_div, 'recover_div': r_div, 'rest_div': 15000,
                'delay': 1, 'mart_iol': 3.0,
                'dd_trigger_pct': 2, 'rest_dur': 30,
            }))

    # === Sweep grind chance: 75%, 80%, 85%, 90% ===
    for gc in [75, 80, 85, 90]:
        label = f'G{gc}+R48+REST gd=10k rd=5k'
        tests.append((label, {
            'use_grind': True, 'use_recover': True, 'use_rest': True,
            'grind_chance': gc, 'recover_chance': 48, 'rest_chance': 98,
            'grind_div': 10000, 'recover_div': 5000, 'rest_div': 15000,
            'delay': 1, 'mart_iol': 3.0,
            'dd_trigger_pct': 2, 'rest_dur': 30,
        }))

    # === DD trigger sweep with best grind config ===
    for dd in [1, 2, 3, 5]:
        label = f'G85+R48+REST dd={dd}% gd=10k rd=5k'
        tests.append((label, {
            'use_grind': True, 'use_recover': True, 'use_rest': True,
            'grind_chance': 85, 'recover_chance': 48, 'rest_chance': 98,
            'grind_div': 10000, 'recover_div': 5000, 'rest_div': 15000,
            'delay': 1, 'mart_iol': 3.0,
            'dd_trigger_pct': dd, 'rest_dur': 30,
        }))

    # === GRIND only (no recover, just grind + rest) ===
    tests.append(('G85+REST-only gd=10k', {
        'use_grind': True, 'use_recover': False, 'use_rest': True,
        'grind_chance': 85, 'rest_chance': 98,
        'grind_div': 10000, 'rest_div': 15000,
        'dd_trigger_pct': 2, 'rest_dur': 30,
    }))

    # === Two-mode: GRIND + RECOVER, no REST ===
    tests.append(('G85+R48 no-rest gd=10k rd=5k', {
        'use_grind': True, 'use_recover': True, 'use_rest': False,
        'grind_chance': 85, 'recover_chance': 48,
        'grind_div': 10000, 'recover_div': 5000,
        'delay': 1, 'mart_iol': 3.0,
        'dd_trigger_pct': 2,
    }))

    # === With SL/TP exits ===
    for sl, tp in [(5, 5), (5, 8), (5, 10), (10, 10)]:
        label = f'G85+R48+REST SL{sl}/TP{tp} gd=10k rd=5k'
        tests.append((label, {
            'use_grind': True, 'use_recover': True, 'use_rest': True,
            'grind_chance': 85, 'recover_chance': 48, 'rest_chance': 98,
            'grind_div': 10000, 'recover_div': 5000, 'rest_div': 15000,
            'delay': 1, 'mart_iol': 3.0,
            'dd_trigger_pct': 2, 'rest_dur': 30,
            'sl_pct': sl, 'tp_pct': tp,
        }))

    print()
    print('=' * 130)
    print('  KRAIT GRIND ARCHITECTURE TEST — 3-regime: GRIND (high%) + RECOVER (48% Mart) + REST (98%)')
    print(f'  {5000} sessions | ${BANK} bank | max {MAX_HANDS} hands | betcap {BET_CAP_PCT}%')
    print('=' * 130)

    rows = []
    for label, cfg in tests:
        r = eval_cfg(label, cfg)
        rows.append(r)

    rows.sort(key=lambda x: x['G'], reverse=True)

    print()
    hdr = f"  {'Strategy':<40} {'G':>7} {'Med':>7} {'Win%':>6} {'Hands':>6} {'Wag':>8} {'Grind%':>7} {'Recov%':>7} {'Rest%':>6} {'Sw':>5} {'HL':>5}"
    print(hdr)
    print('  ' + '-' * (len(hdr) - 2))
    for x in rows:
        hl = 'inf' if x['hl'] >= 99999 else f"{x['hl']:.0f}"
        print(f"  {x['label']:<40} {x['G']:>+6.2f}% ${x['median']:>+6.2f} {x['win_pct']:>5.1f}% {x['hands']:>5.0f} ${x['wagered']:>7.0f} {x['grind_pct']:>6.1f}% {x['recover_pct']:>6.1f}% {x['rest_pct']:>5.1f}% {x['sw']:>5.1f} {hl:>5}")

    pool.close()
    pool.join()
    print(f'\n  Runtime: {time.time() - t0:.1f}s')
    print('=' * 130)
