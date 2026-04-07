#!/usr/bin/env python3
"""PROVING GROUND — Snake Family scored by Growth Rate G.

Universal scorecard evaluation of all 6 strategies using the G metric
(session growth rate via Kelly/Shannon log-wealth compounding).

Replaces median-based ranking with honest compound-growth analysis.
"""
import random, time, sys, os
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.scorecard import scorecard, print_scorecard, print_ranking
from proving_ground.provably_fair import shuffle_float, load_seeds

SEED = 42; BANK = 100; MAX_HANDS = 15000

RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
DOZ2 = set(range(13,25)); DOZ3 = set(range(25,37))
COBRA_NUMS = RED | {2, 4, 6, 8, 10}


# ============================================================
# 1. MAMBA v3.0 — Dice 65% Hybrid D'Alembert→Martingale
# ============================================================

def _mamba(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    dal_units = 1; mult = 1.0; in_mart = False; consec = 0
    profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    act_t = bank * 10 / 100; dal_cap = 3; iol = 3.0
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        if bet > bal * 0.95:
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        if rng.random() < 0.65:
            profit += bet * (99.0/65 - 1)
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0
        else:
            profit -= bet; consec += 1
            if dal_cap > 0 and not in_mart and consec < dal_cap:
                dal_units += 1; mult = dal_units
            else:
                if not in_mart:
                    in_mart = True; mult = dal_units  # Stay at DAL level, Mart multiplies NEXT loss
                else:
                    mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95:
                    mult = 1.0; dal_units = 1; in_mart = False; consec = 0
        if bank+profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# 2. COBRA — Roulette 23-number IOL 3.0x
# ============================================================

def _cobra(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    act_t = bank * 10 / 100; net_win = 36.0/23 - 1
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        if rng.random() < 23.0/37:
            profit += bet * net_win; mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# 3. TAIPAN v2.0 — Roulette Adaptive + Delayed IOL + Bet Cap
# ============================================================

def _taipan_payout(n, ls):
    if ls >= 5:
        if n in DOZ2 or n in DOZ3: return 0.5
        return -1.0
    df, ef = 0.4, 0.6; net = 0.0
    if n in DOZ2: net += df * 2.0
    else: net -= df
    if n in RED: net += ef * 1.0
    else: net -= ef
    return net

def _taipan(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    consec = 0; ls = 0; act_t = bank * 10 / 100
    iol = 5.0; delay = 3; cap_pct = 15
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        if cap_pct > 0:
            max_a = bal * cap_pct / 100
            if bet > max_a: bet = max_a
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        n = rng.randint(0, 36)
        p = _taipan_payout(n, ls)
        if p > 0:
            profit += bet * p; mult = 1.0; ls = 0; consec = 0
        else:
            profit += bet * p; ls += 1; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        if bank+profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# 4. SIDEWINDER — HiLo Adaptive Chain IOL 3.0x
# ============================================================

def _sidewinder(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    act_t = bank * 10 / 100; skip = {6, 7, 8}
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
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
        if bank+profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# 5. BASILISK — Baccarat Delayed IOL 2.1x
# ============================================================

def _basilisk(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 1000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    consec = 0; act_t = bank * 10 / 100; iol = 2.1; delay = 3
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base; consec = 0
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        r = rng.random()
        if r < 0.4586:
            profit += bet * 0.95; mult = 1.0; consec = 0
        elif r < 0.4586 + 0.4462:
            profit -= bet; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        if bank+profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# 6. VIPER v4.0 — BJ PATIENCE + Martingale (calibrated -0.52%)
# ============================================================

def _viper(args):
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    unit = max(bank / 4000, 0.001)
    bet = unit; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    mode = 0; ls = 0; ws = 0; consec = 0; cap_count = 0; coil_deficit = 0.0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        if bet > bal * 0.95: bet = unit; mode = 0; ls = 0; consec = 0
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(unit, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        ht = rng.random(); r = rng.random()
        if ht < 0.0475: pnl = bet * 1.5
        elif ht < 0.0475 + 0.095:
            ab = bet * 2
            pnl = ab if r < 0.56 else (-ab if r < 0.92 else 0)
        elif ht < 0.0475 + 0.095 + 0.025:
            ab = bet * 2.1
            pnl = ab if r < 0.48 else (-ab if r < 0.92 else 0)
        else:
            pnl = bet if r < 0.387 else (-bet if r < 0.914 else 0)
        profit += pnl
        is_win = pnl > 0; is_loss = pnl < 0
        if is_win: ws += 1; ls = 0; consec = 0
        elif is_loss: ls += 1; ws = 0; consec += 1
        if profit > peak: peak = profit
        if mode == 0:
            if is_win:
                bet = unit
                if ws >= 2: mode = 2; cap_count = 0
            elif is_loss:
                if ls >= 12: coil_deficit = 0; mode = 1
                elif consec <= 1: pass
                else: bet = bet * 2
        elif mode == 1:
            coil_deficit += pnl
            if is_win and coil_deficit >= 0:
                mode = 0; bet = unit; consec = 0
                if ws >= 2: mode = 2; cap_count = 0
        elif mode == 2:
            cap_count += 1
            if is_loss or cap_count >= 3: mode = 0; bet = unit; ws = 0
            elif is_win: bet = bet * 2
        if bet < unit: bet = unit
        if bank+profit <= 0: return (profit, True, hands, wagered)
        if not ta and profit >= act_t: ta = True
        if ta and profit > peak: peak = profit
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 5000

    strategies = [
        ("MAMBA v3    dice 65% DAL3→Mart3x",    _mamba,      1.0),
        ("COBRA v5   roulette 23num IOL=3.0x",   _cobra,      2.7),
        ("TAIPAN v2  roulette adaptive d=3 c=15%", _taipan,   2.7),
        ("SIDEWINDER hilo skip={6-8} IOL=3.0x",  _sidewinder, 1.5),
        ("BASILISK   baccarat banker IOL=2.1x",   _basilisk,  1.06),
        ("VIPER v4   blackjack PAT=1 Mart2x",     _viper,    0.52),
    ]

    print()
    print("=" * 105)
    print("  SNAKE FAMILY — UNIVERSAL SCORECARD (Growth Rate G)")
    print("  {} sessions | ${} bank | trail=10/60 | no SL/stop".format(N, BANK))
    print("=" * 105)

    scorecards = []
    for label, func, edge in strategies:
        args = [(s, BANK) for s in range(N)]
        results = pool.map(func, args)
        s = scorecard(results, bank=BANK, house_edge_pct=edge, label=label)
        scorecards.append(s)

    # Top 3 detailed scorecards
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    for s in scorecards[:3]:
        print_scorecard(s, BANK)
        print()

    # Full ranking
    print("=" * 105)
    print("  FULL RANKING BY G (session growth rate)")
    print("=" * 105)
    print_ranking(scorecards, BANK)

    # PF validation for dice/roulette/hilo
    print()
    print("=" * 105)
    print("  PROVABLY FAIR VALIDATION (Shuffle HMAC-SHA256)")
    print("=" * 105)

    seeds = load_seeds()
    print("  {} seed pairs, {} total nonces".format(len(seeds), sum(s["nonces"] for s in seeds)))
    print()

    pf_strategies = [
        ("MAMBA v3 (PF)", _mamba, 1.0),
        ("COBRA v5 (PF)", _cobra, 2.7),
        ("TAIPAN v2 (PF)", _taipan, 2.7),
    ]
    # PF uses same session functions but with deterministic seeds
    # (the functions use SEED-based RNG, PF would need float injection)
    # For now, just note PF is available via rank_snakes.py
    print("  PF replay available for dice/roulette/hilo via rank_snakes.py")
    print("  Baccarat/blackjack: MC only (multi-card PF not implemented)")

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 105)
