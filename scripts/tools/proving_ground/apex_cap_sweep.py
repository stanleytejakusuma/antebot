#!/usr/bin/env python3
"""APEX — targetCap sweep for the 98% start config.

Tests whether a higher/lower cap improves G when starting from 1.01x.
Also sweeps divider alongside cap to find the optimal pairing.
"""
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

    # Sweep: targetCap x divider
    # Fixed: startTarget=1.01, targetStep=1.3, betIOL=1.3, TP=10%, SL=30%
    configs = []
    for cap in [3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 50.0, 100.0]:
        for div in [10000, 50000, 100000]:
            name = "cap={:<5} div={:<6}".format(cap, div)
            configs.append((name, (0, 1.01, 1.3, cap, 1.3, div, 10, 30)))

    print("=" * 95)
    print("  APEX 98%% Start — Target Cap Sweep")
    print("  Fixed: startTarget=1.01, targetStep=1.3, betIOL=1.3, TP=10%%, SL=30%%")
    print("=" * 95)
    fmt = "  {:<22} {:>7} {:>4} {:>8} {:>6} {:>8} {:>7} {:>5}"
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
        print("  {:<22} {:>+6.2f}% {:>4} ${:>+7.2f} {:>5.1f}% ${:>+7.2f} {:>6.0f} {:>5} ({:.1f}s)".format(
            name, card["G_pct"], grade, card["median"], card["win_pct"],
            card["CVaR10"], card["avg_hands"], hl, elapsed))
        all_cards.append(card)

    # Top 5
    all_cards.sort(key=lambda x: x["G"], reverse=True)
    print("\n  TOP 5:")
    for i, c in enumerate(all_cards[:5]):
        grade = "A+" if c["G_pct"] > -0.5 else "A" if c["G_pct"] > -1 else "B" if c["G_pct"] > -2 else "C" if c["G_pct"] > -4 else "D" if c["G_pct"] > -8 else "F"
        hl = "{:.0f}".format(c["half_life"]) if c["half_life"] < 99999 else "inf"
        print("    #{} {}  G={:>+.2f}% {} Med=${:>+.2f} Win={:.1f}% HL={}".format(
            i+1, c["tag"], c["G_pct"], grade, c["median"], c["win_pct"], hl))

    # Compare best APEX vs PULSE champion
    print("\n  " + "=" * 60)
    print("  vs PULSE champion (t=3.0 s=20 c=25): G=-0.24% A+ HL=294")
    best = all_cards[0]
    grade = "A+" if best["G_pct"] > -0.5 else "A" if best["G_pct"] > -1 else "B" if best["G_pct"] > -2 else "C" if best["G_pct"] > -4 else "D"
    print("  APEX best: {} G={:>+.2f}% {} HL={:.0f}".format(
        best["tag"], best["G_pct"], grade,
        best["half_life"] if best["half_life"] < 99999 else float("inf")))
