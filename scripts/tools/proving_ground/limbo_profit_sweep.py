#!/usr/bin/env python3
"""PROVING GROUND — Limbo Profit Strategy Parameter Sweep.

Sweeps key parameters for APEX, CASCADE, and PULSE to find optimal G.
Each config runs 5000 sessions. Results ranked by G.

Sweep dimensions:
  APEX:    divider × targetStep × betIOL
  CASCADE: divider × chainLen × chainIOL
  PULSE:   target × stintLength × coveredStreak
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking

BANK = 100
MAX_BETS = 5000
NUM_SESSIONS = 5000
SEED = 42
MIN_BET = 0.00101


# =====================================================================
# APEX — Escalating Target IOL
# =====================================================================

def _apex(args):
    (s, start_target, target_step, target_cap, bet_iol,
     div, tp_pct, sl_pct) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    base = max(bank / div, MIN_BET)

    target = start_target
    bet = base
    profit = 0.0
    wagered = 0.0
    hands = 0

    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else None
    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else None

    for _ in range(MAX_BETS):
        bal = bank + profit
        if bal <= MIN_BET:
            return (profit, True, hands, wagered)
        if sl_amt is not None and -profit >= sl_amt:
            return (profit, False, hands, wagered)
        if tp_amt is not None and profit >= tp_amt:
            return (profit, False, hands, wagered)

        if bet > bal * 0.95:
            bet = bal * 0.95
        if bet < MIN_BET:
            bet = MIN_BET

        wagered += bet
        hands += 1

        win_prob = min(0.99 / target, 0.99)
        won = rng.random() < win_prob

        if won:
            profit += bet * (target - 1)
            target = start_target
            bet = base
        else:
            profit -= bet
            target *= target_step
            if target > target_cap:
                target = target_cap
            bet *= bet_iol

    return (profit, False, hands, wagered)


# =====================================================================
# CASCADE — Chain-Level IOL
# =====================================================================

def _cascade(args):
    (s, chain_target, chain_len, chain_iol, div, tp_pct, sl_pct) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK
    base = max(bank / div, MIN_BET)

    chain_bet = base
    chain_step = 0
    profit = 0.0
    wagered = 0.0
    hands = 0

    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else None
    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else None
    win_prob = min(0.99 / chain_target, 0.99)

    for _ in range(MAX_BETS):
        bal = bank + profit
        if bal <= MIN_BET:
            return (profit, True, hands, wagered)
        if sl_amt is not None and -profit >= sl_amt:
            return (profit, False, hands, wagered)
        if tp_amt is not None and profit >= tp_amt:
            return (profit, False, hands, wagered)

        if chain_step == 0:
            bet = chain_bet
        else:
            bet = chain_bet * (chain_target ** chain_step)

        if bet > bal * 0.95:
            chain_bet = base
            chain_step = 0
            bet = base
        if bet < MIN_BET:
            bet = MIN_BET

        wagered += bet
        hands += 1
        won = rng.random() < win_prob

        if won:
            profit += bet * (chain_target - 1)
            chain_step += 1
            if chain_step >= chain_len:
                chain_step = 0
                chain_bet = base
        else:
            profit -= bet
            chain_step = 0
            chain_bet *= chain_iol

    return (profit, False, hands, wagered)


# =====================================================================
# PULSE — Windowed Stint IOL
# =====================================================================

def _pulse(args):
    (s, target, preroll_len, stint_len, covered, tp_pct, sl_pct) = args

    rng = random.Random(SEED * 100000 + s)
    bank = BANK

    iol = 1.0 / (target - 1) + 1
    div_calc = 0.0
    for i in range(covered):
        div_calc += iol ** i
    div_val = int(math.ceil(div_calc)) + 1
    base = max(bank / div_val, MIN_BET)

    phase = 'preroll'
    preroll_count = 0
    stint_count = 0
    stint_bet = base
    profit = 0.0
    wagered = 0.0
    hands = 0

    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else None
    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else None
    win_prob = min(0.99 / target, 0.99)

    for _ in range(MAX_BETS):
        bal = bank + profit
        if bal <= MIN_BET:
            return (profit, True, hands, wagered)
        if sl_amt is not None and -profit >= sl_amt:
            return (profit, False, hands, wagered)
        if tp_amt is not None and profit >= tp_amt:
            return (profit, False, hands, wagered)

        if phase == 'preroll':
            bet = MIN_BET
            wagered += bet
            hands += 1
            won = rng.random() < win_prob
            if won:
                profit += bet * (target - 1)
                preroll_count = 0
            else:
                profit -= bet
                preroll_count += 1
            if preroll_count >= preroll_len:
                phase = 'stint'
                stint_count = 0
                stint_bet = base
        elif phase == 'stint':
            bet = stint_bet
            if bet > bal * 0.95:
                phase = 'preroll'
                preroll_count = 0
                stint_bet = base
                continue
            if bet < MIN_BET:
                bet = MIN_BET
            wagered += bet
            hands += 1
            won = rng.random() < win_prob
            if won:
                profit += bet * (target - 1)
                phase = 'preroll'
                preroll_count = 0
                stint_bet = base
            else:
                profit -= bet
                stint_count += 1
                if stint_count >= stint_len:
                    phase = 'preroll'
                    preroll_count = 0
                    stint_bet = base
                else:
                    stint_bet *= iol

    return (profit, False, hands, wagered)


# =====================================================================
# Sweep runner
# =====================================================================

def run_batch(worker_fn, configs, label_fn):
    """Run multiple configs for one strategy, return sorted scorecards."""
    cores = cpu_count()
    cards = []

    for cfg in configs:
        name = label_fn(cfg)
        t0 = time.time()

        args_list = []
        for i in range(NUM_SESSIONS):
            a = list(cfg)
            a[0] = i
            args_list.append(tuple(a))

        with Pool(processes=cores) as pool:
            results = pool.map(worker_fn, args_list)

        elapsed = time.time() - t0
        card = scorecard(results, bank=BANK, house_edge_pct=1.0, label=name)
        wagers = [r[3] for r in results]
        card['avg_wagered'] = statistics.mean(wagers)
        card['wager_mult'] = card['avg_wagered'] / BANK
        cards.append(card)

        grade = "A+" if card['G_pct'] > -0.5 else "A" if card['G_pct'] > -1 else "B" if card['G_pct'] > -2 else "C" if card['G_pct'] > -4 else "D" if card['G_pct'] > -8 else "F"
        print("    {:<40} G={:>+6.2f}% {:>2} Med=${:>+6.2f} Win={:>5.1f}% HL={:<4} ({:.1f}s)".format(
            name, card['G_pct'], grade, card['median'], card['win_pct'],
            "{:.0f}".format(card['half_life']) if card['half_life'] < 99999 else "inf",
            elapsed))

    cards.sort(key=lambda x: x['G'], reverse=True)
    return cards


def main():
    print("=" * 90)
    print("  LIMBO PROFIT STRATEGIES — Full Parameter Sweep")
    print("  Bank: ${} | Sessions/config: {} | Max bets: {}".format(
        BANK, NUM_SESSIONS, MAX_BETS))
    print("=" * 90)

    all_best = []

    # =================================================================
    # APEX SWEEP
    # =================================================================
    print("\n  APEX — Sweeping divider x targetStep x betIOL")
    print("  Fixed: startTarget=2.0, targetCap=10.0, TP=10%, SL=30%")
    print("  " + "-" * 85)

    apex_configs = []
    # (s, start_target, target_step, target_cap, bet_iol, div, tp_pct, sl_pct)
    for div in [10000, 50000, 100000, 500000, 1000000]:
        for tstep in [1.10, 1.15, 1.20, 1.30]:
            for biol in [1.3, 1.5, 1.8, 2.0]:
                apex_configs.append((0, 2.0, tstep, 10.0, biol, div, 10, 30))

    apex_cards = run_batch(
        _apex, apex_configs,
        lambda c: "div={} ts={} bi={}".format(c[5], c[2], c[4])
    )

    print("\n  APEX TOP 5:")
    for i, c in enumerate(apex_cards[:5]):
        print("    #{} {}  G={:>+.2f}% Med=${:>+.2f} Win={:.1f}% CVaR=${:.2f} HL={}".format(
            i+1, c['tag'], c['G_pct'], c['median'], c['win_pct'], c['CVaR10'],
            "{:.0f}".format(c['half_life']) if c['half_life'] < 99999 else "inf"))
    all_best.append(apex_cards[0])

    # =================================================================
    # CASCADE SWEEP
    # =================================================================
    print("\n  CASCADE — Sweeping divider x chainLen x chainIOL")
    print("  Fixed: chainTarget=2.0, TP=10%, SL=30%")
    print("  " + "-" * 85)

    cascade_configs = []
    # (s, chain_target, chain_len, chain_iol, div, tp_pct, sl_pct)
    for div in [10000, 50000, 100000, 500000, 1000000]:
        for clen in [2, 3, 4]:
            for ciol in [1.10, 1.15, 1.20, 1.25, 1.30]:
                cascade_configs.append((0, 2.0, clen, ciol, div, 10, 30))

    cascade_cards = run_batch(
        _cascade, cascade_configs,
        lambda c: "div={} len={} iol={}".format(c[4], c[2], c[3])
    )

    print("\n  CASCADE TOP 5:")
    for i, c in enumerate(cascade_cards[:5]):
        print("    #{} {}  G={:>+.2f}% Med=${:>+.2f} Win={:.1f}% CVaR=${:.2f} HL={}".format(
            i+1, c['tag'], c['G_pct'], c['median'], c['win_pct'], c['CVaR10'],
            "{:.0f}".format(c['half_life']) if c['half_life'] < 99999 else "inf"))
    all_best.append(cascade_cards[0])

    # =================================================================
    # PULSE SWEEP
    # =================================================================
    print("\n  PULSE — Sweeping target x stintLength x coveredStreak")
    print("  Fixed: preroll=5, TP=10%, SL=30%")
    print("  " + "-" * 85)

    pulse_configs = []
    # (s, target, preroll_len, stint_len, covered, tp_pct, sl_pct)
    for tgt in [2.0, 3.0, 5.0, 10.0]:
        for stint in [8, 12, 15, 20, 30]:
            for cov in [20, 25, 30, 40, 50]:
                if cov >= stint:  # covered must >= stint for safety
                    pulse_configs.append((0, tgt, 5, stint, cov, 10, 30))

    pulse_cards = run_batch(
        _pulse, pulse_configs,
        lambda c: "t={} s={} c={}".format(c[1], c[3], c[4])
    )

    print("\n  PULSE TOP 5:")
    for i, c in enumerate(pulse_cards[:5]):
        print("    #{} {}  G={:>+.2f}% Med=${:>+.2f} Win={:.1f}% CVaR=${:.2f} HL={}".format(
            i+1, c['tag'], c['G_pct'], c['median'], c['win_pct'], c['CVaR10'],
            "{:.0f}".format(c['half_life']) if c['half_life'] < 99999 else "inf"))
    all_best.append(pulse_cards[0])

    # =================================================================
    # FINAL COMPARISON — Best of each
    # =================================================================
    print("\n" + "=" * 90)
    print("  CHAMPIONS — Best config per strategy")
    print("=" * 90)
    print_ranking(all_best, bank=BANK)

    # Also show total configs tested
    total = len(apex_configs) + len(cascade_configs) + len(pulse_configs)
    print("\n  Total configs tested: {} ({} sessions total)".format(
        total, total * NUM_SESSIONS))


if __name__ == "__main__":
    main()
