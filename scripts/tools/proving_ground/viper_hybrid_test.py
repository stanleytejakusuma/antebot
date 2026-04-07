#!/usr/bin/env python3
"""VIPER Hybrid Upgrade — D'Alembert → Martingale for BJ, scored by G."""
import random, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.scorecard import scorecard, print_scorecard, print_ranking

SEED = 42; BANK = 100; MAX_HANDS = 15000


def _viper_current(args):
    """Current VIPER v4.0: PATIENCE=1, Mart 2x, div=4000, brake=12."""
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
        if bank + profit <= 0: return (profit, True, hands, wagered)
        if not ta and profit >= act_t: ta = True
        if ta and profit > peak: peak = profit
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


def _viper_hybrid(args):
    """Hybrid VIPER: D'Alembert first dal_cap losses, then Martingale."""
    s, bank, div, dal_cap, mart_iol, brake_at, cap_streak, cap_max = args
    rng = random.Random(SEED * 100000 + s)
    unit = max(bank / div, 0.001)
    dal_units = 1; mult = 1.0; in_mart = False; consec = 0
    bet = unit; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    mode = 0; ls = 0; ws = 0; cap_count = 0; coil_deficit = 0.0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        if bet > bal * 0.95:
            bet = unit; mode = 0; ls = 0; consec = 0
            dal_units = 1; mult = 1.0; in_mart = False
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

        if mode == 0:  # STRIKE (hybrid)
            if is_win:
                bet = unit; dal_units = 1; mult = 1.0; in_mart = False
                if ws >= cap_streak: mode = 2; cap_count = 0
            elif is_loss:
                if brake_at > 0 and ls >= brake_at:
                    coil_deficit = 0; mode = 1
                elif in_mart:
                    mult *= mart_iol; bet = unit * mult
                    if bal > 0 and bet > bal * 0.95:
                        bet = unit; dal_units = 1; mult = 1.0; in_mart = False; consec = 0
                else:
                    dal_units += 1; bet = unit * dal_units
                    if consec >= dal_cap:
                        in_mart = True; mult = dal_units * mart_iol; bet = unit * mult
        elif mode == 1:  # COIL
            coil_deficit += pnl
            if is_win and coil_deficit >= 0:
                mode = 0; bet = unit; consec = 0
                dal_units = 1; mult = 1.0; in_mart = False
                if ws >= cap_streak: mode = 2; cap_count = 0
        elif mode == 2:  # CAPITALIZE
            cap_count += 1
            if is_loss or cap_count >= cap_max:
                mode = 0; bet = unit; ws = 0
                dal_units = 1; mult = 1.0; in_mart = False
            elif is_win:
                bet = bet * 2

        if bet < unit: bet = unit
        if bank + profit <= 0: return (profit, True, hands, wagered)
        if not ta and profit >= act_t: ta = True
        if ta and profit > peak: peak = profit
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 5000

    configs = [
        ("VIPER v4.0 (current)",             _viper_current, lambda s: (s, BANK)),
        # Hybrid: vary div, dal_cap, mart_iol
        ("HYB d=4000 dal=3 m=2x b=12",      _viper_hybrid, lambda s: (s, BANK, 4000, 3, 2.0, 12, 2, 3)),
        ("HYB d=4000 dal=3 m=3x b=12",      _viper_hybrid, lambda s: (s, BANK, 4000, 3, 3.0, 12, 2, 3)),
        ("HYB d=4000 dal=5 m=2x b=12",      _viper_hybrid, lambda s: (s, BANK, 4000, 5, 2.0, 12, 2, 3)),
        ("HYB d=4000 dal=5 m=3x b=12",      _viper_hybrid, lambda s: (s, BANK, 4000, 5, 3.0, 12, 2, 3)),
        ("HYB d=5000 dal=3 m=2x b=12",      _viper_hybrid, lambda s: (s, BANK, 5000, 3, 2.0, 12, 2, 3)),
        ("HYB d=5000 dal=3 m=3x b=12",      _viper_hybrid, lambda s: (s, BANK, 5000, 3, 3.0, 12, 2, 3)),
        ("HYB d=5000 dal=5 m=2x b=12",      _viper_hybrid, lambda s: (s, BANK, 5000, 5, 2.0, 12, 2, 3)),
        ("HYB d=5000 dal=5 m=3x b=12",      _viper_hybrid, lambda s: (s, BANK, 5000, 5, 3.0, 12, 2, 3)),
        ("HYB d=6000 dal=3 m=2x b=10",      _viper_hybrid, lambda s: (s, BANK, 6000, 3, 2.0, 10, 2, 3)),
        ("HYB d=6000 dal=3 m=3x b=10",      _viper_hybrid, lambda s: (s, BANK, 6000, 3, 3.0, 10, 2, 3)),
        ("HYB d=6000 dal=5 m=2x b=10",      _viper_hybrid, lambda s: (s, BANK, 6000, 5, 2.0, 10, 2, 3)),
        ("HYB d=6000 dal=5 m=3x b=10",      _viper_hybrid, lambda s: (s, BANK, 6000, 5, 3.0, 10, 2, 3)),
        ("HYB d=8000 dal=3 m=2x b=12",      _viper_hybrid, lambda s: (s, BANK, 8000, 3, 2.0, 12, 2, 3)),
        ("HYB d=8000 dal=5 m=2x b=12",      _viper_hybrid, lambda s: (s, BANK, 8000, 5, 2.0, 12, 2, 3)),
    ]

    print()
    print("=" * 105)
    print("  VIPER HYBRID UPGRADE — Scored by G (session growth rate)")
    print("  BJ model (-0.52%) | {} sessions | ${} bank | trail 10/60".format(N, BANK))
    print("=" * 105)

    scorecards = []
    for label, func, arg_fn in configs:
        args = [arg_fn(s) for s in range(N)]
        r = scorecard(pool.map(func, args), bank=BANK, house_edge_pct=0.52, label=label)
        scorecards.append(r)

    # Top 3 detailed
    scorecards.sort(key=lambda x: x['G'], reverse=True)
    print()
    for s in scorecards[:3]:
        print_scorecard(s, BANK)
        print()

    # Full ranking
    print("=" * 105)
    print("  FULL RANKING BY G")
    print("=" * 105)
    print_ranking(scorecards, BANK)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 105)
