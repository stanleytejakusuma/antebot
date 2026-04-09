#!/usr/bin/env python3
"""Dual-Regime STRIKER validation — Rest + Profit mode switching.

Hypothesis: limiting profit-mode exposure reduces P(catastrophic chain)
while rest-mode flat bets rebuild trail cushion at minimal ED cost.

Switching strategies:
  A) Fixed round counts (profit N / rest M)
  B) Loss-streak trigger (rest after LS>=K, rest for D rounds)
  B') Drawdown trigger (rest when profit drops >X% from entry)
  C) Cushion-based (profit when cushion > H%, rest when < L%)
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000; DIV = 2500
MART_IOL = 3.0; BET_CAP_PCT = 10; TRAIL_RANGE_PCT = 3


def _regime_session(args):
    (s, switch_mode, rest_chance,
     profit_rounds, rest_rounds,
     ls_trigger, rest_duration, dd_trigger_pct,
     cushion_high_pct, cushion_low_pct) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    base = max(bank / DIV, 0.00101)

    # Profit mode: 50% chance
    p_payout = 0.99 * 100.0 / 50 - 1.0  # 0.98
    p_winp = 0.50

    # Rest mode: high chance, flat bets
    r_payout = 0.99 * 100.0 / rest_chance - 1.0
    r_winp = rest_chance / 100.0

    # Trail (global, from start)
    trail_rng = bank * TRAIL_RANGE_PCT / 100

    # State
    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    rest_hands = 0; profit_hands = 0; switches = 0

    # IOL state (profit mode)
    mult = 1.0; in_mart = False; consec = 0

    # Mode
    mode = 'profit'
    mode_ctr = profit_rounds if switch_mode == 'fixed' else 0
    rest_ctr = 0
    entry_profit = 0.0  # profit at profit-mode entry (for DD trigger)

    def reset_chain():
        nonlocal mult, in_mart, consec
        mult = 1.0; in_mart = False; consec = 0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        # --- BET ---
        if mode == 'rest':
            bet = base
            winp = r_winp; payout = r_payout
        else:
            bet = base * mult
            winp = p_winp; payout = p_payout
            # Bet cap
            mx = bal * BET_CAP_PCT / 100
            if bet > mx: bet = mx
            # Soft bust
            if bet > bal * 0.95:
                reset_chain(); bet = base

        if bet > bal: bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

        # Trail-aware cap (global)
        fl = peak - trail_rng
        margin = profit - fl
        if margin > 0 and bet > margin:
            bet = max(base * 0.5, margin)
        if bet < 0.001:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)

        hands += 1; wagered += bet
        if mode == 'rest':
            rest_hands += 1
        else:
            profit_hands += 1

        # --- RESOLVE ---
        if rng.random() < winp:
            profit += bet * payout
            if mode == 'profit':
                reset_chain()
        else:
            profit -= bet
            if mode == 'profit':
                consec += 1
                # dalCap=1: first loss stays flat, then Mart 3x
                if not in_mart:
                    in_mart = True; mult = 1  # flat absorb
                else:
                    mult *= MART_IOL
                # Soft bust check
                if bal > 0 and base * mult > bal * 0.95:
                    reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)
        if profit > peak:
            peak = profit

        # Trail exit
        if profit <= peak - trail_rng:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)

        # --- MODE SWITCHING ---
        if switch_mode == 'fixed':
            mode_ctr -= 1
            if mode_ctr <= 0:
                old = mode
                if mode == 'profit':
                    mode = 'rest'; mode_ctr = rest_rounds; reset_chain()
                else:
                    mode = 'profit'; mode_ctr = profit_rounds; reset_chain()
                    entry_profit = profit
                if old != mode: switches += 1

        elif switch_mode == 'ls_trigger':
            if mode == 'profit' and consec >= ls_trigger:
                mode = 'rest'; rest_ctr = rest_duration; reset_chain(); switches += 1
            elif mode == 'rest':
                rest_ctr -= 1
                if rest_ctr <= 0:
                    mode = 'profit'; reset_chain(); entry_profit = profit; switches += 1

        elif switch_mode == 'dd_trigger':
            if mode == 'profit':
                dd = entry_profit - profit
                if dd > bank * dd_trigger_pct / 100:
                    mode = 'rest'; rest_ctr = rest_duration; reset_chain(); switches += 1
            elif mode == 'rest':
                rest_ctr -= 1
                if rest_ctr <= 0:
                    mode = 'profit'; reset_chain(); entry_profit = profit; switches += 1

        elif switch_mode == 'cushion':
            cushion = profit - (peak - trail_rng)
            cushion_pct = cushion / bank * 100
            if mode == 'profit' and cushion_pct < cushion_low_pct:
                mode = 'rest'; reset_chain(); switches += 1
            elif mode == 'rest' and cushion_pct > cushion_high_pct:
                mode = 'profit'; reset_chain(); entry_profit = profit; switches += 1

    return (profit, False, hands, wagered, rest_hands, profit_hands, switches)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    N = 5000

    # (label, switch_mode, rest_chance,
    #  profit_rounds, rest_rounds,
    #  ls_trigger, rest_duration, dd_trigger_pct,
    #  cushion_high_pct, cushion_low_pct)
    configs = [
        # === BASELINE ===
        ("BASELINE STRIKER v3.0",
         'none', 95, 99999, 0, 99, 0, 99, 0, 0),

        # === FIXED (A) — 9 configs ===
        ("FIXED 400/100 @95%", 'fixed', 95, 400, 100, 99, 0, 99, 0, 0),
        ("FIXED 450/50  @95%", 'fixed', 95, 450, 50,  99, 0, 99, 0, 0),
        ("FIXED 480/20  @95%", 'fixed', 95, 480, 20,  99, 0, 99, 0, 0),
        ("FIXED 400/100 @98%", 'fixed', 98, 400, 100, 99, 0, 99, 0, 0),
        ("FIXED 450/50  @98%", 'fixed', 98, 450, 50,  99, 0, 99, 0, 0),
        ("FIXED 480/20  @98%", 'fixed', 98, 480, 20,  99, 0, 99, 0, 0),
        ("FIXED 400/100 @99%", 'fixed', 99, 400, 100, 99, 0, 99, 0, 0),
        ("FIXED 450/50  @99%", 'fixed', 99, 450, 50,  99, 0, 99, 0, 0),
        ("FIXED 480/20  @99%", 'fixed', 99, 480, 20,  99, 0, 99, 0, 0),

        # === LS TRIGGER (B) — 6 configs ===
        ("LS>=4 rest=50  @95%",  'ls_trigger', 95, 0, 0, 4, 50,  99, 0, 0),
        ("LS>=4 rest=100 @95%",  'ls_trigger', 95, 0, 0, 4, 100, 99, 0, 0),
        ("LS>=4 rest=200 @95%",  'ls_trigger', 95, 0, 0, 4, 200, 99, 0, 0),
        ("LS>=4 rest=50  @98%",  'ls_trigger', 98, 0, 0, 4, 50,  99, 0, 0),
        ("LS>=4 rest=100 @98%",  'ls_trigger', 98, 0, 0, 4, 100, 99, 0, 0),
        ("LS>=4 rest=200 @98%",  'ls_trigger', 98, 0, 0, 4, 200, 99, 0, 0),

        # === DRAWDOWN TRIGGER (B') — 4 configs ===
        ("DD>1% rest=50  @95%",  'dd_trigger', 95, 0, 0, 99, 50,  1, 0, 0),
        ("DD>1% rest=100 @95%",  'dd_trigger', 95, 0, 0, 99, 100, 1, 0, 0),
        ("DD>2% rest=50  @95%",  'dd_trigger', 95, 0, 0, 99, 50,  2, 0, 0),
        ("DD>2% rest=100 @98%",  'dd_trigger', 98, 0, 0, 99, 100, 2, 0, 0),

        # === CUSHION-BASED (C) — 6 configs ===
        ("CUSH >2%/<1%   @95%",  'cushion', 95, 0, 0, 99, 0, 99, 2.0, 1.0),
        ("CUSH >2%/<0.5% @95%",  'cushion', 95, 0, 0, 99, 0, 99, 2.0, 0.5),
        ("CUSH >1.5/<0.5 @95%",  'cushion', 95, 0, 0, 99, 0, 99, 1.5, 0.5),
        ("CUSH >2%/<1%   @98%",  'cushion', 98, 0, 0, 99, 0, 99, 2.0, 1.0),
        ("CUSH >2%/<0.5% @98%",  'cushion', 98, 0, 0, 99, 0, 99, 2.0, 0.5),
        ("CUSH >1.5/<0.5 @98%",  'cushion', 98, 0, 0, 99, 0, 99, 1.5, 0.5),
    ]

    print()
    print("=" * 115)
    print("  DUAL-REGIME STRIKER — PROVING GROUND")
    print("  {} sessions | ${} bank | div={} | mart={}x | trail={}% | betcap={}%".format(
        N, BANK, DIV, MART_IOL, TRAIL_RANGE_PCT, BET_CAP_PCT))
    print("  Rest mode = flat bets, no IOL. Profit mode = STRIKER v3.0 (dalCap=1 → Mart 3x)")
    print("=" * 115)

    all_results = {}
    scorecards = []

    for cfg in configs:
        label = cfg[0]
        args = [(s,) + cfg[1:] for s in range(N)]
        results = pool.map(_regime_session, args)
        all_results[label] = results
        sc = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        scorecards.append(sc)

    # === RANKING ===
    print()
    print_ranking(scorecards, BANK)

    # === REGIME STATS ===
    print()
    print("  {:<35} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
        'Strategy', 'Hands', 'Profit%', 'Rest%', 'Switches', 'Wag/Ses'))
    print("  " + "-" * 80)

    scorecards.sort(key=lambda x: x['G'], reverse=True)
    for sc in scorecards:
        label = sc['tag']
        results = all_results[label]
        avg_hands = statistics.mean([r[2] for r in results])
        avg_ph = statistics.mean([r[5] for r in results])
        avg_rh = statistics.mean([r[4] for r in results])
        avg_sw = statistics.mean([r[6] for r in results])
        avg_wag = statistics.mean([r[3] for r in results])
        ph_pct = avg_ph / avg_hands * 100 if avg_hands > 0 else 0
        rh_pct = avg_rh / avg_hands * 100 if avg_hands > 0 else 0
        print("  {:<35} {:>7.0f} {:>7.1f}% {:>7.1f}% {:>7.1f} ${:>7.0f}".format(
            label, avg_hands, ph_pct, rh_pct, avg_sw, avg_wag))

    # === TOP 3 + BASELINE ===
    print()
    for sc in scorecards[:3]:
        print_scorecard(sc, BANK)
        print()

    baseline = [sc for sc in scorecards if "BASELINE" in sc['tag']]
    if baseline and baseline[0] not in scorecards[:3]:
        print("  --- BASELINE COMPARISON ---")
        print_scorecard(baseline[0], BANK)
        print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 115)
