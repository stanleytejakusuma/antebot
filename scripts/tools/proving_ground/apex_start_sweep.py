#!/usr/bin/env python3
"""APEX — Starting target sweep. Does starting from high chance help?"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking

BANK = 100; MAX_BETS = 5000; NUM = 5000; SEED = 42; MIN_BET = 0.00101

def _apex(args):
    (s, start_target, target_step, target_cap, bet_iol, div, tp_pct, sl_pct) = args
    rng = random.Random(SEED * 100000 + s)
    bank = BANK; base = max(bank / div, MIN_BET)
    target = start_target; bet = base
    profit = 0.0; wagered = 0.0; hands = 0
    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else None
    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else None
    for _ in range(MAX_BETS):
        bal = bank + profit
        if bal <= MIN_BET: return (profit, True, hands, wagered)
        if sl_amt is not None and -profit >= sl_amt: return (profit, False, hands, wagered)
        if tp_amt is not None and profit >= tp_amt: return (profit, False, hands, wagered)
        if bet > bal * 0.95: bet = bal * 0.95
        if bet < MIN_BET: bet = MIN_BET
        wagered += bet; hands += 1
        win_prob = min(0.99 / target, 0.99)
        if rng.random() < win_prob:
            profit += bet * (target - 1); target = start_target; bet = base
        else:
            profit -= bet
            target *= target_step
            if target > target_cap: target = target_cap
            bet *= bet_iol
    return (profit, False, hands, wagered)

if __name__ == "__main__":
    cores = cpu_count()
    configs = [
        ("t=1.01 (98%) div=100k",  (0, 1.01, 1.3, 10.0, 1.3, 100000, 10, 30)),
        ("t=1.10 (90%) div=100k",  (0, 1.10, 1.3, 10.0, 1.3, 100000, 10, 30)),
        ("t=1.20 (83%) div=100k",  (0, 1.20, 1.3, 10.0, 1.3, 100000, 10, 30)),
        ("t=1.50 (66%) div=100k",  (0, 1.50, 1.3, 10.0, 1.3, 100000, 10, 30)),
        ("t=2.00 (50%) div=100k",  (0, 2.00, 1.3, 10.0, 1.3, 100000, 10, 30)),
        ("t=3.00 (33%) div=100k",  (0, 3.00, 1.3, 10.0, 1.3, 100000, 10, 30)),
        # Lower dividers for high-chance starts (need bigger bets to see action)
        ("t=1.01 (98%) div=100",   (0, 1.01, 1.3, 10.0, 1.3, 100, 10, 30)),
        ("t=1.01 (98%) div=1k",    (0, 1.01, 1.3, 10.0, 1.3, 1000, 10, 30)),
        ("t=1.10 (90%) div=1k",    (0, 1.10, 1.3, 10.0, 1.3, 1000, 10, 30)),
        ("t=1.50 (66%) div=1k",    (0, 1.50, 1.3, 10.0, 1.3, 1000, 10, 30)),
        ("t=1.50 (66%) div=10k",   (0, 1.50, 1.3, 10.0, 1.3, 10000, 10, 30)),
        ("t=2.00 (50%) div=10k",   (0, 2.00, 1.3, 10.0, 1.3, 10000, 10, 30)),
    ]

    print("=" * 95)
    print("  APEX — Starting Target Sweep (higher chance = lower target)")
    print("  Fixed: targetStep=1.3, betIOL=1.3, targetCap=10, TP=10%, SL=30%")
    print("=" * 95)
    fmt = "  {:<26} {:>7} {:>4} {:>8} {:>6} {:>8} {:>7} {:>5}"
    print(fmt.format("Config", "G(%)", "Grd", "Median", "Win%", "CVaR10", "Hands", "HL"))
    print("  " + "-" * 82)

    all_cards = []
    for name, cfg in configs:
        t0 = time.time()
        args_list = [tuple([i] + list(cfg)[1:]) for i in range(NUM)]
        with Pool(processes=cores) as pool:
            results = pool.map(_apex, args_list)
        card = scorecard(results, bank=BANK, house_edge_pct=1.0, label=name)
        elapsed = time.time() - t0
        grade = "A+" if card["G_pct"] > -0.5 else "A" if card["G_pct"] > -1 else "B" if card["G_pct"] > -2 else "C" if card["G_pct"] > -4 else "D" if card["G_pct"] > -8 else "F"
        hl = "{:.0f}".format(card["half_life"]) if card["half_life"] < 99999 else "inf"
        print("  {:<26} {:>+6.2f}% {:>4} ${:>+7.2f} {:>5.1f}% ${:>+7.2f} {:>6.0f} {:>5} ({:.1f}s)".format(
            name, card["G_pct"], grade, card["median"], card["win_pct"],
            card["CVaR10"], card["avg_hands"], hl, elapsed))
        all_cards.append(card)
