#!/usr/bin/env python3
"""PROVING GROUND — Honest Strategy Evaluation.

Evaluates strategies using MEAN-centered metrics instead of median:
- Mean (EV): actual expected outcome per session
- Edge efficiency: mean / total wagered (how much house edge you dodge)
- Profit velocity: mean / hands (profit per bet placed)
- Sharpe ratio: mean / stdev (risk-adjusted return)
- Bankroll half-life: sessions until 50% bankroll loss at this rate
- Win/loss asymmetry: avg_win × win% vs avg_loss × loss%
"""
import random, time, math, statistics
from multiprocessing import Pool, cpu_count

SEED = 42; BANK = 100; MAX_HANDS = 15000


# ============================================================
# Session functions — return (profit, busted, hands, wagered)
# ============================================================

def _mamba(args):
    """Current MAMBA: dice 65%, IOL 3.0x"""
    s, bank = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    act_t = bank * 10 / 100
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
        if rng.random() < 0.65:
            profit += bet * (99.0 / 65 - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank + profit > 0 and base * mult > (bank + profit) * 0.95: mult = 1.0
        if bank + profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


def _hybrid(args):
    """Hybrid: D'Alembert for first N losses, then Martingale."""
    s, bank, chance, dal_cap, mart_iol = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    units = 1; mult = 1.0; in_mart = False
    profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    consec = 0
    payout = 0.99 * 100.0 / chance - 1.0
    win_prob = chance / 100.0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)
        bet = base * mult if in_mart else base * units
        if bet > bal * 0.95:
            units = 1; mult = 1.0; in_mart = False; consec = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)
        if ta:
            floor = peak * 60 / 100; mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)
        hands += 1; wagered += bet
        if rng.random() < win_prob:
            profit += bet * payout
            units = 1; mult = 1.0; in_mart = False; consec = 0
        else:
            profit -= bet; consec += 1
            if in_mart:
                mult *= mart_iol
                if bank + profit > 0 and base * mult > (bank + profit) * 0.95:
                    mult = 1.0; units = 1; in_mart = False; consec = 0
            else:
                units += 1
                if consec >= dal_cap:
                    in_mart = True; mult = units
        if bank + profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


def _highchance(args):
    """High-chance: high win%, aggressive IOL."""
    s, bank, chance, iol = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    payout = 0.99 * 100.0 / chance - 1.0
    win_prob = chance / 100.0
    act_t = bank * 10 / 100
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
        if rng.random() < win_prob:
            profit += bet * payout; mult = 1.0
        else:
            profit -= bet; mult *= iol
            if bank + profit > 0 and base * mult > (bank + profit) * 0.95: mult = 1.0
        if bank + profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands, wagered)
    return (profit, False, hands, wagered)


# ============================================================
# Comprehensive stats
# ============================================================

def full_stats(results):
    profits = [r[0] for r in results]
    busted = [r[1] for r in results]
    hands_list = [r[2] for r in results]
    wagered_list = [r[3] for r in results]
    n = len(profits)

    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]

    sorted_p = sorted(profits)
    mean = statistics.mean(profits)
    stdev = statistics.stdev(profits) if n > 1 else 0
    avg_hands = statistics.mean(hands_list)
    avg_wagered = statistics.mean(wagered_list)

    return {
        'median': sorted_p[n // 2],
        'mean': mean,
        'stdev': stdev,
        'bust_pct': sum(1 for b in busted if b) / n * 100,
        'win_pct': len(wins) / n * 100,
        'avg_win': statistics.mean(wins) if wins else 0,
        'avg_loss': statistics.mean(losses) if losses else 0,
        'p10': sorted_p[n // 10],
        'p90': sorted_p[9 * n // 10],
        'avg_hands': avg_hands,
        'avg_wagered': avg_wagered,
        # Derived
        'edge_eff': mean / avg_wagered * 100 if avg_wagered > 0 else 0,  # %
        'velocity': mean / avg_hands * 1000 if avg_hands > 0 else 0,  # per 1000 hands
        'sharpe': mean / stdev if stdev > 0 else 0,
        'half_life': abs(BANK / 2 / mean) if mean != 0 else float('inf'),  # sessions
    }


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 5000

    configs = [
        ("MAMBA 65% IOL=3.0x (current)",
         _mamba, lambda s: (s, BANK)),
        ("HYB 50% dal=3 mart=3.0x",
         _hybrid, lambda s: (s, BANK, 50, 3, 3.0)),
        ("HYB 50% dal=5 mart=3.0x",
         _hybrid, lambda s: (s, BANK, 50, 5, 3.0)),
        ("HYB 50% dal=5 mart=2.0x",
         _hybrid, lambda s: (s, BANK, 50, 5, 2.0)),
        ("HYB 50% dal=7 mart=3.0x",
         _hybrid, lambda s: (s, BANK, 50, 7, 3.0)),
        ("HYB 65% dal=3 mart=3.0x",
         _hybrid, lambda s: (s, BANK, 65, 3, 3.0)),
        ("HICH 75% IOL=5.0x",
         _highchance, lambda s: (s, BANK, 75, 5.0)),
        ("HICH 80% IOL=5.0x",
         _highchance, lambda s: (s, BANK, 80, 5.0)),
        ("HICH 80% IOL=7.0x",
         _highchance, lambda s: (s, BANK, 80, 7.0)),
        ("HICH 85% IOL=7.0x",
         _highchance, lambda s: (s, BANK, 85, 7.0)),
    ]

    print()
    print("=" * 140)
    print("  HONEST STRATEGY EVALUATION — Mean-Centered Metrics")
    print("  {} sessions | ${} bank | trail=10/60 | no SL/stop".format(N, BANK))
    print("=" * 140)

    all_stats = []

    for label, func, arg_fn in configs:
        args = [arg_fn(s) for s in range(N)]
        r = full_stats(pool.map(func, args))
        r['tag'] = label
        all_stats.append(r)

    # === TABLE 1: The Honest View ===
    print()
    print("  {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>8} {:>8} {:>8}".format(
        'Strategy', 'MEAN', 'Median', 'Stdev', 'Win%', 'Bust%', 'AvgWin', 'AvgLoss', 'Wagered'))
    print("  " + "-" * 105)
    for r in all_stats:
        print("  {:<35} ${:>+6.2f} ${:>+6.2f} ${:>6.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} ${:>7.0f}".format(
            r['tag'], r['mean'], r['median'], r['stdev'],
            r['win_pct'], r['bust_pct'], r['avg_win'], r['avg_loss'], r['avg_wagered']))

    # === TABLE 2: Efficiency Metrics ===
    print()
    print("  {:<35} {:>8} {:>9} {:>8} {:>9} {:>7}".format(
        'Strategy', 'EdgeEff', 'Velocity', 'Sharpe', 'HalfLife', 'Hands'))
    print("  {:>35} {:>8} {:>9} {:>8} {:>9} {:>7}".format(
        '', '(%)', '($/1kh)', '(M/SD)', '(sess)', '(avg)'))
    print("  " + "-" * 82)
    for r in all_stats:
        hl = "{:.0f}".format(r['half_life']) if r['half_life'] < 99999 else "inf"
        print("  {:<35} {:>+7.3f}% {:>+8.3f} {:>+7.4f} {:>8} {:>7.0f}".format(
            r['tag'], r['edge_eff'], r['velocity'], r['sharpe'], hl, r['avg_hands']))

    # === TABLE 3: Asymmetry Breakdown ===
    print()
    print("  {:<35} {:>7} {:>9} {:>7} {:>9} {:>9} {:>8}".format(
        'Strategy', 'Win%', 'Win×Avg', 'Loss%', 'Loss×Avg', 'Net EV', 'Asymm'))
    print("  " + "-" * 90)
    for r in all_stats:
        win_ev = r['win_pct'] / 100 * r['avg_win']
        loss_ev = (100 - r['win_pct']) / 100 * r['avg_loss']
        net = win_ev + loss_ev
        asymm = abs(win_ev / loss_ev) if loss_ev != 0 else 0
        print("  {:<35} {:>5.1f}% ${:>+8.2f} {:>5.1f}% ${:>+8.2f} ${:>+8.2f} {:>7.3f}".format(
            r['tag'], r['win_pct'], win_ev, 100 - r['win_pct'], loss_ev, net, asymm))

    # === RANKING by mean ===
    print()
    print("=" * 140)
    print("  RANKING BY MEAN (actual expected value per session)")
    print("=" * 140)
    all_stats.sort(key=lambda x: x['mean'], reverse=True)
    print("  {:<4} {:<35} {:>7} {:>7} {:>8} {:>8} {:>6}".format(
        '#', 'Strategy', 'MEAN', 'Median', 'EdgeEff', 'Sharpe', 'Bust%'))
    print("  " + "-" * 80)
    for i, r in enumerate(all_stats):
        print("  {:<4} {:<35} ${:>+6.2f} ${:>+6.2f} {:>+7.3f}% {:>+7.4f} {:>5.1f}%".format(
            i + 1, r['tag'], r['mean'], r['median'], r['edge_eff'], r['sharpe'], r['bust_pct']))

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 140)
