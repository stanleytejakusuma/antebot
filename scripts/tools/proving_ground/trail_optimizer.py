#!/usr/bin/env python3
"""PROVING GROUND — Trail Parameter Optimizer.

Sweeps (trailActivatePct, trailLockPct) across all Snake Family strategies.
Trail-only mode (no SL, no profit stop) to isolate trail effect.
"""
import random, time, sys, os
from multiprocessing import Pool, cpu_count

NUM = 3000; SEED = 42; MAX_HANDS = 15000; BANK = 100

RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
DOZ2 = set(range(13,25)); DOZ3 = set(range(25,37))
COBRA_NUMS = RED | {2, 4, 6, 8, 10}


# ============================================================
# Session functions (trail-parametrized, no SL/stop)
# args = (s, bank, trail_act, trail_lock)
# ============================================================

def _mamba(args):
    s, bank, ta_pct, tl_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    act_t = bank * ta_pct / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < 0.65:
            profit += bet * (99.0/65 - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * tl_pct / 100: return (profit, False, hands)
    return (profit, False, hands)


def _cobra(args):
    s, bank, ta_pct, tl_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    act_t = bank * ta_pct / 100
    net_win = 36.0 / 23 - 1
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < 23.0/37:
            profit += bet * net_win; mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * tl_pct / 100: return (profit, False, hands)
    return (profit, False, hands)


def _taipan_payout(n, ls):
    if ls >= 5:
        if n in DOZ2 or n in DOZ3: return 0.5
        return -1.0
    df, ef = 0.4, 0.6
    net = 0.0
    if n in DOZ2: net += df * 2.0
    else: net -= df
    if n in RED: net += ef * 1.0
    else: net -= ef
    return net


def _taipan(args):
    s, bank, ta_pct, tl_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    consec = 0; ls = 0
    act_t = bank * ta_pct / 100
    iol = 5.0; delay = 3; cap_pct = 15
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if cap_pct > 0:
            max_a = bal * cap_pct / 100
            if bet > max_a: bet = max_a
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        n = rng.randint(0, 36)
        p = _taipan_payout(n, ls)
        if p > 0:
            profit += bet * p; mult = 1.0; ls = 0; consec = 0
        else:
            profit += bet * p; ls += 1; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * tl_pct / 100: return (profit, False, hands)
    return (profit, False, hands)


def _sidewinder(args):
    s, bank, ta_pct, tl_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    act_t = bank * ta_pct / 100
    skip = {6, 7, 8}
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if ta: co_target = 1.1
        elif profit < -bank * 5 / 100 or mult > 1.5: co_target = 2.5
        else: co_target = 1.5
        card = rng.randint(1, 13); acc = 1.0; won = False
        for _ in range(52):
            if card in skip: card = rng.randint(1, 13); continue
            bet_high = card <= 7
            winning = (13 - card) if bet_high else (card - 1)
            if winning <= 0: card = rng.randint(1, 13); continue
            gross = 0.99 * 13.0 / winning
            nxt = rng.randint(1, 13)
            correct = (nxt > card) if bet_high else (nxt < card)
            if not correct: break
            acc *= gross; card = nxt
            if acc >= co_target: won = True; break
        if won: profit += bet * (acc - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * tl_pct / 100: return (profit, False, hands)
    return (profit, False, hands)


def _basilisk(args):
    s, bank, ta_pct, tl_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 1000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    consec = 0
    act_t = bank * ta_pct / 100
    iol = 2.1; delay = 3
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base; consec = 0
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        r = rng.random()
        if r < 0.4586:
            profit += bet * 0.95; mult = 1.0; consec = 0
        elif r < 0.4586 + 0.4462:
            profit -= bet; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * tl_pct / 100: return (profit, False, hands)
    return (profit, False, hands)


def _viper(args):
    s, bank, ta_pct, tl_pct = args
    rng = random.Random(SEED * 100000 + s)
    unit = max(bank / 6000, 0.001)
    bet = unit; profit = 0.0; peak = 0.0; ta = False; hands = 0
    mode = 0; ls = 0; ws = 0; cap_count = 0
    coil_deficit = 0.0
    brake_at = 10; cap_streak = 2; cap_max = 2
    act_t = bank * ta_pct / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        if bet > bal * 0.95: bet = unit; mode = 0; ls = 0
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(unit, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        hand_type = rng.random(); r = rng.random()
        if hand_type < 0.0475:
            pnl = bet * 1.5
        elif hand_type < 0.0475 + 0.095:
            actual_bet = bet * 2
            if r < 0.56: pnl = actual_bet
            elif r < 0.56 + 0.36: pnl = -actual_bet
            else: pnl = 0
        elif hand_type < 0.0475 + 0.095 + 0.025:
            actual_bet = bet * 2.1
            if r < 0.48: pnl = actual_bet
            elif r < 0.48 + 0.44: pnl = -actual_bet
            else: pnl = 0
        else:
            if r < 0.387: pnl = bet
            elif r < 0.387 + 0.527: pnl = -bet
            else: pnl = 0
        profit += pnl
        is_win = pnl > 0; is_loss = pnl < 0
        if is_win: ws += 1; ls = 0
        elif is_loss: ls += 1; ws = 0
        if profit > peak: peak = profit
        if mode == 0:
            if is_win:
                bet = unit
                if ws >= cap_streak: mode = 2; cap_count = 0
            elif is_loss:
                if brake_at > 0 and ls >= brake_at:
                    coil_deficit = 0; mode = 1
                else:
                    bet = bet * 2
        elif mode == 1:
            coil_deficit += pnl
            if is_win and coil_deficit >= 0:
                mode = 0; bet = unit
                if ws >= cap_streak: mode = 2; cap_count = 0
        elif mode == 2:
            cap_count += 1
            if is_loss or cap_count >= cap_max:
                mode = 0; bet = unit; ws = 0
            elif is_win:
                bet = bet * 2
        if bet < unit: bet = unit
        if ta:
            floor = peak * tl_pct / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(unit, mt)
        if bank+profit <= 0: return (profit, True, hands)
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * tl_pct / 100: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# Stats
# ============================================================

def stats(results):
    pnls = sorted([r[0] for r in results])
    busts = sum(1 for r in results if r[1])
    n = len(pnls)
    if n == 0: return {'median': 0, 'mean': 0, 'bust_pct': 0, 'win_pct': 0, 'p10': 0}
    return {
        'median': pnls[n//2], 'mean': sum(pnls)/n, 'bust_pct': busts/n*100,
        'win_pct': sum(1 for p in pnls if p > 0)/n*100,
        'p10': pnls[n//10], 'p90': pnls[9*n//10],
    }


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    bank = BANK

    activates = [3, 5, 8, 10, 12, 15]
    locks = [40, 50, 60, 70, 80]

    strategies = [
        ("MAMBA", _mamba),
        ("COBRA", _cobra),
        ("TAIPAN", _taipan),
        ("SIDEWINDER", _sidewinder),
        ("BASILISK", _basilisk),
        ("VIPER", _viper),
    ]

    print()
    print("=" * 120)
    print("  TRAIL PARAMETER OPTIMIZER — Snake Family")
    print("  {} MC sessions | ${} bank | trail only (no SL/stop)".format(NUM, bank))
    print("  Grid: activate={} × lock={}".format(activates, locks))
    print("=" * 120)

    best_overall = {}

    for strat_name, strat_func in strategies:
        print()
        print("  === {} ===".format(strat_name))
        print("  {:>6} | ".format("act\\lock") + " | ".join("{:>18}".format("lock={}%".format(l)) for l in locks))
        print("  " + "-" * (8 + len(locks) * 21))

        best_med = -999; best_ra = -999; best_wr = -999
        best_med_params = (0, 0); best_ra_params = (0, 0); best_wr_params = (0, 0)
        grid = {}

        for act in activates:
            row = []
            for lock in locks:
                args = [(s, bank, act, lock) for s in range(NUM)]
                r = stats(pool.map(strat_func, args))
                ra = r['median'] / abs(r['p10']) if r['p10'] != 0 and r['median'] > 0 else -1
                grid[(act, lock)] = r

                cell = "${:>+5.2f} {:>4.1f}%b {:>4.1f}%w".format(r['median'], r['bust_pct'], r['win_pct'])
                row.append(cell)

                if r['median'] > best_med:
                    best_med = r['median']; best_med_params = (act, lock)
                if ra > best_ra:
                    best_ra = ra; best_ra_params = (act, lock)
                if r['win_pct'] > best_wr:
                    best_wr = r['win_pct']; best_wr_params = (act, lock)

            print("  {:>5}% | ".format(act) + " | ".join(row))

        # Current default
        cur = grid.get((8, 60), {})
        cur_med = cur.get('median', 0)
        cur_ra = cur['median'] / abs(cur['p10']) if cur.get('p10', 0) != 0 and cur.get('median', 0) > 0 else -1

        print()
        print("  Current (8/60):  median=${:>+.2f}  bust={:.1f}%  win={:.1f}%  RA={:.3f}".format(
            cur_med, cur.get('bust_pct', 0), cur.get('win_pct', 0), cur_ra))
        print("  Best median:     {}/{}  median=${:>+.2f}".format(best_med_params[0], best_med_params[1], best_med))

        bra = grid[best_ra_params]
        bra_ra = bra['median'] / abs(bra['p10']) if bra['p10'] != 0 and bra['median'] > 0 else -1
        print("  Best RA:         {}/{}  RA={:.3f}  median=${:>+.2f}".format(
            best_ra_params[0], best_ra_params[1], bra_ra, bra['median']))

        bwr = grid[best_wr_params]
        print("  Best win rate:   {}/{}  win={:.1f}%  median=${:>+.2f}".format(
            best_wr_params[0], best_wr_params[1], bwr['win_pct'], bwr['median']))

        best_overall[strat_name] = {
            'best_med': best_med_params, 'best_ra': best_ra_params,
            'best_wr': best_wr_params, 'grid': grid,
        }

    # ================================================================
    # Summary
    # ================================================================
    print()
    print("=" * 120)
    print("  SUMMARY — Optimal trail params per strategy")
    print("=" * 120)
    print("  {:<12} {:>12} {:>12} {:>12}".format('Strategy', 'Best Median', 'Best RA', 'Best WinRate'))
    print("  " + "-" * 48)
    for name in [s[0] for s in strategies]:
        b = best_overall[name]
        print("  {:<12} {:>5}/{:<5} {:>5}/{:<5} {:>5}/{:<5}".format(
            name,
            b['best_med'][0], b['best_med'][1],
            b['best_ra'][0], b['best_ra'][1],
            b['best_wr'][0], b['best_wr'][1]))

    # Check if there's a universal winner
    med_params = [best_overall[s[0]]['best_med'] for s in strategies]
    ra_params = [best_overall[s[0]]['best_ra'] for s in strategies]
    from collections import Counter
    med_counts = Counter(med_params)
    ra_counts = Counter(ra_params)
    print()
    print("  Most common best-median params: {}".format(med_counts.most_common(3)))
    print("  Most common best-RA params:     {}".format(ra_counts.most_common(3)))

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
