#!/usr/bin/env python3
"""Dual-Regime STRIKER — NO TRAIL variant.

Trail at 3% was ending sessions at ~124 hands, preventing regime switching
from ever activating. This test removes trail entirely and uses:
  - Stop loss (hard floor)
  - Profit target (take profit)
  - Max hands
as session exits, letting regime switching BE the risk management.

Tests whether rest mode can substitute for trail as a circuit breaker.
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

SEED = 42; BANK = 100; MAX_HANDS = 15000; DIV = 2500
MART_IOL = 3.0; BET_CAP_PCT = 10


def _regime_session(args):
    (s, switch_mode, rest_chance,
     profit_rounds, rest_rounds,
     ls_trigger, rest_duration, dd_trigger_pct,
     cushion_high_pct, cushion_low_pct,
     sl_pct, tp_pct) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    base = max(bank / DIV, 0.00101)

    # Profit mode: 50% chance
    p_payout = 0.99 * 100.0 / 50 - 1.0  # 0.98
    p_winp = 0.50

    # Rest mode
    r_payout = 0.99 * 100.0 / rest_chance - 1.0
    r_winp = rest_chance / 100.0

    # Stop loss / take profit (dollar amounts)
    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else bank * 0.99  # near-total loss
    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else bank * 100   # effectively infinite

    # State
    profit = 0.0; peak = 0.0; hands = 0; wagered = 0.0
    rest_hands = 0; profit_hands = 0; switches = 0

    # IOL state
    mult = 1.0; in_mart = False; consec = 0

    # Mode
    mode = 'profit'
    mode_ctr = profit_rounds if switch_mode == 'fixed' else 0
    rest_ctr = 0
    entry_profit = 0.0

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
            mx = bal * BET_CAP_PCT / 100
            if bet > mx: bet = mx
            if bet > bal * 0.95:
                reset_chain(); bet = base

        if bet > bal: bet = bal
        if bet < 0.001:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)

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
                if not in_mart:
                    in_mart = True; mult = 1
                else:
                    mult *= MART_IOL
                if bal > 0 and base * mult > bal * 0.95:
                    reset_chain()

        if bank + profit <= 0:
            return (profit, True, hands, wagered, rest_hands, profit_hands, switches)
        if profit > peak:
            peak = profit

        # --- EXITS (no trail — use SL/TP) ---
        if profit <= -sl_amt:
            return (profit, False, hands, wagered, rest_hands, profit_hands, switches)
        if profit >= tp_amt:
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

        elif switch_mode == 'cushion_sl':
            # Cushion relative to SL floor
            cushion = profit + sl_amt  # distance from SL
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
    #  cushion_high_pct, cushion_low_pct,
    #  sl_pct, tp_pct)

    configs = [
        # === BASELINES (no regime switching) ===
        ("BASE: SL=5% TP=5%",
         'none', 95, 99999, 0, 99, 0, 99, 0, 0, 5, 5),
        ("BASE: SL=10% TP=5%",
         'none', 95, 99999, 0, 99, 0, 99, 0, 0, 10, 5),
        ("BASE: SL=10% TP=10%",
         'none', 95, 99999, 0, 99, 0, 99, 0, 0, 10, 10),
        ("BASE: SL=15% TP=5%",
         'none', 95, 99999, 0, 99, 0, 99, 0, 0, 15, 5),

        # === FIXED REGIME: SL=10% TP=5% ===
        ("FIX 50/50   SL10 TP5 @95%",
         'fixed', 95, 50, 50, 99, 0, 99, 0, 0, 10, 5),
        ("FIX 100/50  SL10 TP5 @95%",
         'fixed', 95, 100, 50, 99, 0, 99, 0, 0, 10, 5),
        ("FIX 100/100 SL10 TP5 @95%",
         'fixed', 95, 100, 100, 99, 0, 99, 0, 0, 10, 5),
        ("FIX 200/100 SL10 TP5 @95%",
         'fixed', 95, 200, 100, 99, 0, 99, 0, 0, 10, 5),
        ("FIX 50/50   SL10 TP5 @98%",
         'fixed', 98, 50, 50, 99, 0, 99, 0, 0, 10, 5),
        ("FIX 100/50  SL10 TP5 @98%",
         'fixed', 98, 100, 50, 99, 0, 99, 0, 0, 10, 5),

        # === FIXED REGIME: SL=10% TP=10% ===
        ("FIX 50/50   SL10 TP10 @95%",
         'fixed', 95, 50, 50, 99, 0, 99, 0, 0, 10, 10),
        ("FIX 100/50  SL10 TP10 @95%",
         'fixed', 95, 100, 50, 99, 0, 99, 0, 0, 10, 10),
        ("FIX 100/100 SL10 TP10 @95%",
         'fixed', 95, 100, 100, 99, 0, 99, 0, 0, 10, 10),
        ("FIX 200/100 SL10 TP10 @95%",
         'fixed', 95, 200, 100, 99, 0, 99, 0, 0, 10, 10),

        # === LS TRIGGER: SL=10% TP=5% ===
        ("LS>=3 r=30  SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 3, 30, 99, 0, 0, 10, 5),
        ("LS>=3 r=50  SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 3, 50, 99, 0, 0, 10, 5),
        ("LS>=4 r=30  SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 4, 30, 99, 0, 0, 10, 5),
        ("LS>=4 r=50  SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 4, 50, 99, 0, 0, 10, 5),
        ("LS>=4 r=100 SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 4, 100, 99, 0, 0, 10, 5),
        ("LS>=5 r=30  SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 5, 30, 99, 0, 0, 10, 5),
        ("LS>=5 r=50  SL10 TP5 @95%",
         'ls_trigger', 95, 0, 0, 5, 50, 99, 0, 0, 10, 5),

        # === LS TRIGGER: SL=10% TP=10% ===
        ("LS>=4 r=50  SL10 TP10 @95%",
         'ls_trigger', 95, 0, 0, 4, 50, 99, 0, 0, 10, 10),
        ("LS>=4 r=100 SL10 TP10 @95%",
         'ls_trigger', 95, 0, 0, 4, 100, 99, 0, 0, 10, 10),
        ("LS>=5 r=50  SL10 TP10 @95%",
         'ls_trigger', 95, 0, 0, 5, 50, 99, 0, 0, 10, 10),

        # === DD TRIGGER: SL=10% TP=5% ===
        ("DD>1% r=50  SL10 TP5 @95%",
         'dd_trigger', 95, 0, 0, 99, 50, 1, 0, 0, 10, 5),
        ("DD>2% r=50  SL10 TP5 @95%",
         'dd_trigger', 95, 0, 0, 99, 50, 2, 0, 0, 10, 5),
        ("DD>2% r=100 SL10 TP5 @95%",
         'dd_trigger', 95, 0, 0, 99, 100, 2, 0, 0, 10, 5),
        ("DD>3% r=50  SL10 TP5 @95%",
         'dd_trigger', 95, 0, 0, 99, 50, 3, 0, 0, 10, 5),

        # === CUSHION-BASED (relative to SL floor): SL=10% TP=5% ===
        ("CUSH >5/<3  SL10 TP5 @95%",
         'cushion_sl', 95, 0, 0, 99, 0, 99, 5, 3, 10, 5),
        ("CUSH >5/<2  SL10 TP5 @95%",
         'cushion_sl', 95, 0, 0, 99, 0, 99, 5, 2, 10, 5),
        ("CUSH >7/<3  SL10 TP5 @95%",
         'cushion_sl', 95, 0, 0, 99, 0, 99, 7, 3, 10, 5),
        ("CUSH >7/<5  SL10 TP5 @95%",
         'cushion_sl', 95, 0, 0, 99, 0, 99, 7, 5, 10, 5),

        # === CUSHION-BASED: SL=10% TP=10% ===
        ("CUSH >5/<3  SL10 TP10 @95%",
         'cushion_sl', 95, 0, 0, 99, 0, 99, 5, 3, 10, 10),
        ("CUSH >7/<3  SL10 TP10 @95%",
         'cushion_sl', 95, 0, 0, 99, 0, 99, 7, 3, 10, 10),

        # === TRAIL BASELINE for comparison ===
        ("BASE: TRAIL 3% (v3.0)",
         'none', 95, 99999, 0, 99, 0, 99, 0, 0, 0, 0),
    ]

    print()
    print("=" * 120)
    print("  DUAL-REGIME STRIKER — NO TRAIL (SL/TP exits)")
    print("  {} sessions | ${} bank | div={} | mart={}x | betcap={}%".format(
        N, BANK, DIV, MART_IOL, BET_CAP_PCT))
    print("  NO TRAIL. Exits: Stop Loss + Take Profit + Max Hands")
    print("  Rest mode = flat bets @95-98%, no IOL. Profit mode = dalCap=1 → Mart 3x")
    print("=" * 120)

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
    print("  {:<35} {:>7} {:>7} {:>7} {:>7} {:>7} {:>7}".format(
        'Strategy', 'Hands', 'Prof%', 'Rest%', 'Sw', 'Wag', 'Win%'))
    print("  " + "-" * 85)

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
        print("  {:<35} {:>6.0f} {:>6.1f}% {:>6.1f}% {:>6.1f} ${:>6.0f} {:>6.1f}%".format(
            label, avg_hands, ph_pct, rh_pct, avg_sw, avg_wag, sc['win_pct']))

    # === TOP 5 + BASELINES ===
    print()
    for sc in scorecards[:5]:
        print_scorecard(sc, BANK)
        print()

    baselines = [sc for sc in scorecards if "BASE:" in sc['tag']]
    for b in baselines:
        if b not in scorecards[:5]:
            print("  --- BASELINE: {} ---".format(b['tag']))
            print_scorecard(b, BANK)
            print()

    pool.close(); pool.join()
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 120)
