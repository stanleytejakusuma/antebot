#!/usr/bin/env python3
"""KRAIT delay sweep — test delay=0/1/2/3 across SL/TP profiles."""
import random, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking

SEED = 42; BANK = 100; MAX_HANDS = 15000; BET_CAP_PCT = 10; REST_CHANCE = 95


def _k(args):
    (s, div, delay, iol, dd, rest, sl, tp, sw) = args
    rng = random.Random(SEED * 100000 + s); bank = BANK
    base = max(bank / div, 0.00101)
    pp = 0.99 * 100.0 / 50 - 1.0; pw = 0.50
    rp = 0.99 * 100.0 / REST_CHANCE - 1.0; rw = REST_CHANCE / 100.0
    sla = bank * sl / 100; tpa = bank * tp / 100
    profit = 0.0; peak = 0.0; h = 0; w = 0.0; rh = 0; ph = 0; swi = 0
    mult = 1.0; im = False; con = 0
    mode = 'profit'; rc = 0; ep = 0.0
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, h, w, rh, ph, swi)
        if mode == 'rest':
            bet = base; wp = rw; pay = rp
        else:
            bet = base * mult; wp = pw; pay = pp
            mx = bal * BET_CAP_PCT / 100
            if bet > mx: bet = mx
            if bet > bal * 0.95: mult = 1.0; im = False; con = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, h, w, rh, ph, swi)
        h += 1; w += bet
        if mode == 'rest': rh += 1
        else: ph += 1
        if rng.random() < wp:
            profit += bet * pay
            if mode == 'profit': mult = 1.0; im = False; con = 0
        else:
            profit -= bet
            if mode == 'profit':
                con += 1
                if con <= delay:
                    mult = 1
                else:
                    if not im: im = True; mult = 1
                    else: mult *= iol
                    if bal > 0 and base * mult > bal * 0.95:
                        mult = 1.0; im = False; con = 0
        if bank + profit <= 0: return (profit, True, h, w, rh, ph, swi)
        if profit > peak: peak = profit
        if profit <= -sla: return (profit, False, h, w, rh, ph, swi)
        if profit >= tpa: return (profit, False, h, w, rh, ph, swi)
        if sw:
            if mode == 'profit':
                dd_ = ep - profit
                if dd_ > bank * dd / 100:
                    mode = 'rest'; rc = rest; mult = 1.0; im = False; con = 0; swi += 1
            elif mode == 'rest':
                rc -= 1
                if rc <= 0:
                    mode = 'profit'; ep = profit; mult = 1.0; im = False; con = 0; swi += 1
    return (profit, False, h, w, rh, ph, swi)


if __name__ == "__main__":
    pool = Pool(cpu_count()); N = 10000
    cfgs = [
        ('SL5/TP5  DD3r30 d=0', 2500, 0, 3.0, 3, 30, 5, 5, True),
        ('SL5/TP5  DD3r30 d=1', 2500, 1, 3.0, 3, 30, 5, 5, True),
        ('SL5/TP5  DD3r30 d=2', 2500, 2, 3.0, 3, 30, 5, 5, True),
        ('SL5/TP5  DD3r30 d=3', 2500, 3, 3.0, 3, 30, 5, 5, True),
        ('SL5/TP5  noSw d=0', 2500, 0, 3.0, 3, 30, 5, 5, False),
        ('SL5/TP5  noSw d=1', 2500, 1, 3.0, 3, 30, 5, 5, False),
        ('SL5/TP5  noSw d=2', 2500, 2, 3.0, 3, 30, 5, 5, False),
        ('SL5/TP3  DD3r30 d=0', 2500, 0, 3.0, 3, 30, 5, 3, True),
        ('SL5/TP3  DD3r30 d=1', 2500, 1, 3.0, 3, 30, 5, 3, True),
        ('SL5/TP3  DD3r30 d=2', 2500, 2, 3.0, 3, 30, 5, 3, True),
        ('SL10/TP5 DD3r30 d=0', 2500, 0, 3.0, 3, 30, 10, 5, True),
        ('SL10/TP5 DD3r30 d=1', 2500, 1, 3.0, 3, 30, 10, 5, True),
        ('SL10/TP5 DD3r30 d=2', 2500, 2, 3.0, 3, 30, 10, 5, True),
        ('SL10/TP5 noSw d=0', 2500, 0, 3.0, 3, 30, 10, 5, False),
        ('SL10/TP5 noSw d=1', 2500, 1, 3.0, 3, 30, 10, 5, False),
    ]
    scs = []
    for cfg in cfgs:
        label = cfg[0]; args = [(s,) + cfg[1:] for s in range(N)]
        res = pool.map(_k, args); sc = scorecard(res, bank=BANK, house_edge_pct=1.0, label=label)
        ah = statistics.mean([r[2] for r in res]); aw = statistics.mean([r[3] for r in res])
        sc['_h'] = ah; sc['_w'] = aw; scs.append(sc)
    pool.close(); pool.join()

    print('\n  KRAIT DELAY SWEEP (10k sessions, 50% dice, IOL 3x, rest@95%)')
    scs.sort(key=lambda x: x['G'], reverse=True)

    # Group by SL/TP
    for group in ['SL5/TP5', 'SL5/TP3', 'SL10/TP5']:
        print('\n  === {} ==='.format(group))
        print('  {:<28} {:>7} {:>7} {:>7} {:>6} {:>6} {:>6} {:>5}'.format(
            'Config', 'G(%)', 'Mean', 'Median', 'Win%', 'Hands', 'Wag', 'HL'))
        print('  ' + '-' * 75)
        grp = sorted([s for s in scs if group in s['tag']], key=lambda x: x['G'], reverse=True)
        for s in grp:
            hl = '{:.0f}'.format(s['half_life']) if s['half_life'] < 99999 else 'inf'
            print('  {:<28} {:>+6.2f}% ${:>+5.2f} ${:>+5.2f} {:>5.1f}% {:>5.0f} ${:>5.0f} {:>5}'.format(
                s['tag'], s['G_pct'], s['mean'], s['median'], s['win_pct'], s['_h'], s['_w'], hl))
