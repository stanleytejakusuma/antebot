#!/usr/bin/env python3
"""STRIKER vs MAMBA — Profit-first dice strategy comparison.

Tests STRIKER (50% chance, big bets, hard stops, fast sessions)
against MAMBA v3.1 (65% chance, hybrid, trail).
Also tests delayed IOL variants.

Scored by Growth Rate G + compound session simulation.
"""
import random, math, statistics, time
from multiprocessing import Pool, cpu_count

SEED = 42; BANK = 100; MAX_HANDS = 15000


def _session(args):
    """Universal dice session with all parameters.

    Returns (profit, busted, hands, wagered)
    """
    (s, bank, chance, div, dal_cap, mart_iol, bet_cap_pct,
     trail_act, trail_range_pct, stop_profit_pct, stop_loss_pct,
     delay) = args

    rng = random.Random(SEED * 100000 + s)
    base = max(bank / div, 0.00101)
    payout = 0.99 * 100.0 / chance - 1.0
    win_prob = chance / 100.0

    dal_units = 1; mult = 1.0; in_mart = False; consec = 0
    profit = 0.0; peak = 0.0; ta = False; hands = 0; wagered = 0.0
    act_t = bank * trail_act / 100 if trail_act > 0 else 0
    trail_rng = bank * trail_range_pct / 100 if trail_range_pct > 0 else 0
    stop_p = bank * stop_profit_pct / 100 if stop_profit_pct > 0 else 0
    stop_l = bank * stop_loss_pct / 100 if stop_loss_pct > 0 else 0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands, wagered)

        bet = base * mult

        # Bet cap
        if bet_cap_pct > 0:
            max_b = bal * bet_cap_pct / 100
            if bet > max_b: bet = max_b

        # Soft bust
        if bet > bal * 0.95:
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands, wagered)

        # Trail-aware cap
        if ta and trail_rng > 0:
            fl = peak - trail_rng
            mt = profit - fl
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands, wagered)

        hands += 1; wagered += bet

        if rng.random() < win_prob:
            profit += bet * payout
            mult = 1.0; dal_units = 1; in_mart = False; consec = 0
        else:
            profit -= bet; consec += 1
            # Delayed IOL: skip first `delay` losses entirely (no bet increase)
            if delay > 0 and consec <= delay:
                pass  # Stay at current bet
            elif dal_cap > 0 and not in_mart and consec < dal_cap + delay:
                dal_units += 1; mult = dal_units
            else:
                if not in_mart:
                    in_mart = True; mult = dal_units
                else:
                    mult *= mart_iol
                if bank + profit > 0 and base * mult > (bank + profit) * 0.95:
                    mult = 1.0; dal_units = 1; in_mart = False; consec = 0

        if bank + profit <= 0: return (profit, True, hands, wagered)
        if profit > peak: peak = profit

        # Trail
        if trail_act > 0:
            if not ta and profit >= act_t: ta = True
            if ta and trail_rng > 0 and profit <= peak - trail_rng:
                return (profit, False, hands, wagered)

        # Hard stops
        if stop_p > 0 and profit >= stop_p and mult <= 1.01:
            return (profit, False, hands, wagered)
        if stop_l > 0 and profit < -stop_l:
            return (profit, False, hands, wagered)

    return (profit, False, hands, wagered)


def stats(results):
    profits = [r[0] for r in results]
    n = len(profits); sp = sorted(profits)
    busts = sum(1 for r in results if r[1])
    eps = 0.001
    logs = [math.log(max(1 + p / BANK, eps / BANK)) for p in profits]
    G = math.exp(statistics.mean(logs)) - 1
    return {
        'median': sp[n // 2], 'mean': statistics.mean(profits),
        'G': G, 'G_pct': G * 100,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in profits if p > 0) / n * 100,
        'p10': sp[n // 10], 'p90': sp[9 * n // 10],
        'avg_hands': statistics.mean([r[2] for r in results]),
        'avg_wagered': statistics.mean([r[3] for r in results]),
    }


def pr(tag, r):
    print("  {:<50} G={:>+6.2f}% ${:>+6.2f} {:>5.1f}%b {:>5.1f}%w ${:>+6.2f} ${:>+6.2f} {:>5.0f}h".format(
        tag, r['G_pct'], r['median'], r['bust_pct'], r['win_pct'],
        r['p10'], r['p90'], r['avg_hands']))


def compound_sim(results, n_sessions=20, n_sims=1000):
    """Simulate compounding across n_sessions, return median bankroll multiplier."""
    profits = [r[0] for r in results]
    n = len(profits)
    rng = random.Random(42)
    final_banks = []
    for _ in range(n_sims):
        bank = BANK
        for _ in range(n_sessions):
            p = profits[rng.randint(0, n - 1)]
            # Scale profit proportionally to current bank
            bank *= (1 + p / BANK)
            if bank <= 0: bank = 0; break
        final_banks.append(bank)
    final_banks.sort()
    m = len(final_banks)
    return {
        'median': final_banks[m // 2] / BANK,
        'p10': final_banks[m // 10] / BANK,
        'p90': final_banks[9 * m // 10] / BANK,
        'bust': sum(1 for b in final_banks if b <= 0) / m * 100,
    }


H = "  {:<50} {:>7} {:>7} {:>6} {:>6} {:>7} {:>7} {:>6}".format(
    'Strategy', 'G(%)', 'Median', 'Bust%', 'Win%', 'P10', 'P90', 'Hands')
SEP = "  " + "-" * 100

if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 5000

    print()
    print("=" * 110)
    print("  STRIKER vs MAMBA — Profit Strategy Shootout")
    print("  {} sessions | ${} bank | Scored by G + compound simulation".format(N, BANK))
    print("=" * 110)

    configs = [
        # (label, chance, div, dal, mart, betcap, trail_act, trail_range, stop_p, stop_l, delay)

        # MAMBA v3.1 (current)
        ("MAMBA 65% dal=3 m=3x div=3000 trail=5/5%",
         65, 3000, 3, 3.0, 15, 5, 5, 0, 15, 0),

        # STRIKER variants — 50% chance, hard stops, no trail
        ("STRIKER 50% dal=2 m=3x div=1500 stop=10/10",
         50, 1500, 2, 3.0, 15, 0, 0, 10, 10, 0),
        ("STRIKER 50% dal=2 m=3x div=2000 stop=10/10",
         50, 2000, 2, 3.0, 15, 0, 0, 10, 10, 0),
        ("STRIKER 50% dal=3 m=3x div=1500 stop=10/10",
         50, 1500, 3, 3.0, 15, 0, 0, 10, 10, 0),
        ("STRIKER 50% dal=2 m=3x div=1500 stop=15/10",
         50, 1500, 2, 3.0, 15, 0, 0, 15, 10, 0),
        ("STRIKER 50% dal=2 m=3x div=1500 stop=10/15",
         50, 1500, 2, 3.0, 15, 0, 0, 10, 15, 0),
        ("STRIKER 50% dal=2 m=5x div=1500 stop=10/10",
         50, 1500, 2, 5.0, 15, 0, 0, 10, 10, 0),

        # Delayed IOL variants — absorb N losses at FLAT before any escalation
        ("DELAYED 65% delay=2 dal=3 m=3x div=3000 s=10/10",
         65, 3000, 3, 3.0, 15, 0, 0, 10, 10, 2),
        ("DELAYED 50% delay=2 dal=2 m=3x div=1500 s=10/10",
         50, 1500, 2, 3.0, 15, 0, 0, 10, 10, 2),
        ("DELAYED 50% delay=3 dal=2 m=3x div=1500 s=10/10",
         50, 1500, 2, 3.0, 15, 0, 0, 10, 10, 3),
        ("DELAYED 50% delay=2 dal=3 m=3x div=1500 s=10/10",
         50, 1500, 3, 3.0, 15, 0, 0, 10, 10, 2),
        ("DELAYED 50% delay=2 dal=2 m=3x div=2000 s=10/10",
         50, 2000, 2, 3.0, 15, 0, 0, 10, 10, 2),

        # Hybrid: STRIKER with trail instead of hard stops
        ("STRIKER+TRAIL 50% dal=2 div=1500 trail=5/5%",
         50, 1500, 2, 3.0, 15, 5, 5, 0, 15, 0),
        ("DELAYED+TRAIL 50% d=2 dal=2 div=1500 trail=5/5%",
         50, 1500, 2, 3.0, 15, 5, 5, 0, 15, 2),

        # Control: pure IOL at 50%
        ("PURE IOL 50% m=3x div=1500 stop=10/10",
         50, 1500, 0, 3.0, 15, 0, 0, 10, 10, 0),
    ]

    print()
    print(H)
    print(SEP)

    all_results = []
    for label, ch, div, dal, mart, cap, ta, tr, sp, sl, delay in configs:
        args = [(s, BANK, ch, div, dal, mart, cap, ta, tr, sp, sl, delay) for s in range(N)]
        results = pool.map(_session, args)
        r = stats(results)
        r['tag'] = label
        r['raw'] = results
        all_results.append(r)
        pr(label, r)

    # === GRAND RANKING by G ===
    print()
    print("=" * 110)
    print("  RANKING BY G (session growth rate)")
    print("=" * 110)
    print(H)
    print(SEP)
    all_results.sort(key=lambda x: x['G'], reverse=True)
    for i, r in enumerate(all_results):
        pr("#{:<2} {}".format(i + 1, r['tag']), r)

    # === COMPOUND SIMULATION ===
    print()
    print("=" * 110)
    print("  COMPOUND SIMULATION — 20 sessions, 1000 simulations")
    print("  Starting $100, each session uses current bankroll")
    print("=" * 110)
    print("  {:<50} {:>8} {:>8} {:>8} {:>7}".format(
        'Strategy', 'Med 20s', 'P10 20s', 'P90 20s', 'Bust%'))
    print("  " + "-" * 85)

    for r in all_results[:10]:  # Top 10 by G
        c = compound_sim(r['raw'])
        print("  {:<50} {:>7.2f}x {:>7.2f}x {:>7.2f}x {:>5.1f}%".format(
            r['tag'], c['median'], c['p10'], c['p90'], c['bust']))

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 110)
