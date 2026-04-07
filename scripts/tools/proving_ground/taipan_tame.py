#!/usr/bin/env python3
"""Tame TAIPAN — apply delayed IOL + bet cap to fix tail risk."""
import random, time
from multiprocessing import Pool, cpu_count

NUM = 5000; SEED = 42
RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
DOZ2 = set(range(13,25)); DOZ3 = set(range(25,37))

def taipan_payout(n, ls, expand_at=5):
    if ls >= expand_at:
        if n in DOZ2 or n in DOZ3: return 0.5
        return -1.0
    df, ef = 0.4, 0.6
    net = 0.0
    if n in DOZ2: net += df * 2.0
    else: net -= df
    if n in RED: net += ef * 1.0
    else: net -= ef
    return net

def _session(args):
    (s, bank, iol, div, stop_pct, sl_pct, trail_act, trail_lock,
     expand_at, delay, bet_cap_pct) = args
    rng = random.Random(SEED * 100000 + s)
    raw_base = bank / div
    # minBet floor for 24 numbers
    pn = raw_base / 24
    if pn < 0.00101: pn = 0.00101
    base = pn * 24
    
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; ls = 0; hands = 0
    consec = 0; max_bet_seen = base
    stop_t = bank * stop_pct / 100; sl_t = bank * sl_pct / 100
    act_t = bank * trail_act / 100
    
    for _ in range(15000):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, max_bet_seen)
        
        bet = base * mult
        
        # BET CAP: hard limit as % of balance
        if bet_cap_pct > 0:
            max_allowed = bal * bet_cap_pct / 100
            if bet > max_allowed:
                bet = max_allowed
        
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, max_bet_seen)
        
        if ta:
            floor = peak * trail_lock / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = mt
            if bet < 0.001: return (profit, False, hands, max_bet_seen)
        
        if bet > max_bet_seen: max_bet_seen = bet
        hands += 1
        
        n = rng.randint(0, 36)
        p = taipan_payout(n, ls, expand_at)
        
        if p > 0:
            profit += bet * p; mult = 1.0; ls = 0; consec = 0
        else:
            profit += bet * p  # p is negative
            ls += 1; consec += 1
            # DELAYED IOL: only escalate after `delay` consecutive losses
            if consec >= delay:
                mult *= iol
                nb_pn = (raw_base * mult) / 24
                if nb_pn < 0.00101: nb_pn = 0.00101
                nb = nb_pn * 24
                if bank + profit > 0 and nb > (bank + profit) * 0.95: mult = 1.0; consec = 0
        
        if bank + profit <= 0: return (profit, True, hands, max_bet_seen)
        if profit > peak: peak = profit
        if trail_act > 0:
            if not ta and profit >= act_t: ta = True
            if ta and profit <= peak * trail_lock / 100:
                return (profit, False, hands, max_bet_seen)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01:
            return (profit, False, hands, max_bet_seen)
        if sl_t > 0 and profit <= -sl_t:
            return (profit, False, hands, max_bet_seen)
    return (profit, False, hands, max_bet_seen)

def stats(results):
    pnls = sorted([r[0] for r in results])
    busts = sum(1 for r in results if r[1])
    avg_h = sum(r[2] for r in results) / len(results)
    avg_mb = sum(r[3] for r in results) / len(results)
    max_mb = max(r[3] for r in results)
    n = len(pnls)
    return {
        'median': pnls[n//2], 'mean': sum(pnls)/n, 'bust_pct': busts/n*100,
        'win_pct': sum(1 for p in pnls if p > 0)/n*100,
        'p10': pnls[n//10], 'p90': pnls[9*n//10],
        'avg_hands': avg_h, 'avg_maxbet': avg_mb, 'worst_maxbet': max_mb,
    }

def pr(tag, r, bank):
    ra = r['median'] / abs(r['p10']) if r['p10'] != 0 and r['median'] > 0 else -1
    mb_pct = r['worst_maxbet'] / bank * 100
    print("  {:<50} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} mb={:>5.1f}% ra={:.3f}".format(
        tag, r['median'], r['bust_pct'], r['win_pct'], r['p10'], r['p90'], mb_pct, ra))

H = "  {:<50} {:>8} {:>6} {:>6} {:>8} {:>8} {:>7} {:>8}".format(
    'Strategy', 'Median', 'Bust%', 'Win%', 'P10', 'P90', 'MaxBet%', 'RA')
S = "  {} {} {} {} {} {} {} {}".format('-'*50, '-'*8, '-'*6, '-'*6, '-'*8, '-'*8, '-'*7, '-'*8)

def _mamba(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False
    for _ in range(15000):
        bal = bank + profit
        if bal <= 0: return (profit, True, 0, 0)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, 0, 0)
        if rng.random() < 0.65:
            profit += bet*(99/65-1); mult=1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult=1.0
        if bank+profit <= 0: return (profit, True, 0, 0)
        if profit > peak: peak = profit
        if not ta and profit >= bank*0.08: ta = True
        if ta and profit <= peak*0.60: return (profit, False, 0, 0)
        if profit >= bank*0.15 and mult <= 1.01: return (profit, False, 0, 0)
        if profit <= -bank*0.15: return (profit, False, 0, 0)
    return (profit, False, 0, 0)

if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    bank = 100

    print()
    print("=" * 120)
    print("  TAMING TAIPAN — Delayed IOL + Bet Cap")
    print("  {} sessions | ${} bank | trail=8/60 SL=15% stop=15%".format(NUM, bank))
    print("=" * 120)

    # CURRENT TAIPAN (untamed)
    print("\n  === CURRENT (untamed) ===")
    print(H); print(S)
    for iol, div in [(4.0, 8000), (6.0, 10000)]:
        args = [(s, bank, iol, div, 15, 15, 8, 60, 5, 1, 0) for s in range(NUM)]
        r = stats(pool.map(_session, args))
        pr("TAIPAN IOL={}x div={} (current)".format(iol, div), r, bank)

    # FIX 1: BET CAP only
    print("\n  === FIX 1: BET CAP (max bet as % of balance) ===")
    print(H); print(S)
    for iol in [4.0, 6.0]:
        for cap in [5, 10, 15, 20]:
            args = [(s, bank, iol, 10000, 15, 15, 8, 60, 5, 1, cap) for s in range(NUM)]
            r = stats(pool.map(_session, args))
            pr("IOL={}x cap={}%".format(iol, cap), r, bank)

    # FIX 2: DELAYED IOL only
    print("\n  === FIX 2: DELAYED IOL (PATIENCE from BASILISK) ===")
    print(H); print(S)
    for iol in [4.0, 6.0]:
        for delay in [1, 2, 3]:
            args = [(s, bank, iol, 10000, 15, 15, 8, 60, 5, delay, 0) for s in range(NUM)]
            r = stats(pool.map(_session, args))
            pr("IOL={}x delay={}".format(iol, delay), r, bank)

    # FIX 3: BOTH — delayed IOL + bet cap
    print("\n  === FIX 3: BOTH (delayed IOL + bet cap) ===")
    print(H); print(S)
    for iol in [4.0, 5.0, 6.0]:
        for delay in [2, 3]:
            for cap in [10, 15]:
                args = [(s, bank, iol, 10000, 15, 15, 8, 60, 5, delay, cap) for s in range(NUM)]
                r = stats(pool.map(_session, args))
                pr("IOL={}x delay={} cap={}%".format(iol, delay, cap), r, bank)

    # GRAND RANKING — best tamed configs vs MAMBA baseline
    print()
    print("=" * 120)
    print("  GRAND RANKING — Tamed TAIPAN vs baselines")
    print("=" * 120)
    print(H); print(S)

    r_mamba = stats(pool.map(_mamba, [(s, bank) for s in range(NUM)]))
    pr("MAMBA dice 65% IOL=3.0x (baseline)", r_mamba, bank)

    # Best tamed configs
    best = [
        ("TAIPAN IOL=6.0x (untamed)", 6.0, 10000, 1, 0),
        ("TAIPAN IOL=4.0x cap=10%", 4.0, 10000, 1, 10),
        ("TAIPAN IOL=6.0x cap=10%", 6.0, 10000, 1, 10),
        ("TAIPAN IOL=4.0x delay=2 cap=10%", 4.0, 10000, 2, 10),
        ("TAIPAN IOL=6.0x delay=2 cap=10%", 6.0, 10000, 2, 10),
        ("TAIPAN IOL=5.0x delay=2 cap=15%", 5.0, 10000, 2, 15),
        ("TAIPAN IOL=6.0x delay=2 cap=15%", 6.0, 10000, 2, 15),
        ("TAIPAN IOL=6.0x delay=3 cap=10%", 6.0, 10000, 3, 10),
    ]
    for label, iol, div, delay, cap in best:
        args = [(s, bank, iol, div, 15, 15, 8, 60, 5, delay, cap) for s in range(NUM)]
        r = stats(pool.map(_session, args))
        pr(label, r, bank)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
