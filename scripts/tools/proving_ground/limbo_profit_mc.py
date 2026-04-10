#!/usr/bin/env python3
"""PROVING GROUND — Limbo Profit Strategies Monte Carlo.

Three novel strategies, 5000 sessions each, full scorecard comparison.
Custom simulation loops because each strategy has unique mechanics
that don't fit the standard run_session() framework.

Strategies:
  APEX     — Escalating target + bet IOL (dual escalation)
  CASCADE  — Chain-level IOL (3-win combo, IOL on chain fail)
  PULSE    — Windowed stint IOL (preroll + capped stint)
"""
import random, math, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

# === Constants ===
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

        # Bet safety
        if bet > bal * 0.95:
            bet = bal * 0.95
        if bet < MIN_BET:
            bet = MIN_BET

        wagered += bet
        hands += 1

        # Resolve: win prob = 0.99 / target
        win_prob = min(0.99 / target, 0.99)
        won = rng.random() < win_prob

        if won:
            profit += bet * (target - 1)
            # Reset both
            target = start_target
            bet = base
        else:
            profit -= bet
            # Escalate both
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

    chain_bet = base       # current chain's initial bet
    chain_step = 0         # 0 = start of chain
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

        # Determine bet for this roll
        if chain_step == 0:
            bet = chain_bet
        else:
            # Mid-chain: bet the accumulated winnings (let it ride)
            bet = chain_bet * (chain_target ** chain_step)

        # Bet safety
        if bet > bal * 0.95:
            # Soft bust — reset chain IOL
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
                # Chain complete! Reset.
                chain_step = 0
                chain_bet = base
        else:
            # Chain failed at any step — lose the original chain bet only
            # (mid-chain bets used winnings, so net cost = chain_bet)
            if chain_step > 0:
                # We already counted the profit from earlier steps via
                # the bet * (target-1) additions. On loss mid-chain,
                # we lose the current bet which was funded by prior wins.
                # The net effect: we lost the original chain_bet.
                # But the sim already handles this correctly via
                # profit -= bet (which subtracts the compounded amount)
                # and profit += for earlier wins. The accounting is exact.
                pass
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

    # Auto-calculate IOL and divider (matching the JS script)
    iol = 1.0 / (target - 1) + 1
    div_calc = 0.0
    for i in range(covered):
        div_calc += iol ** i
    div_val = int(math.ceil(div_calc)) + 1

    base = max(bank / div_val, MIN_BET)

    phase = 'preroll'  # 'preroll' or 'stint'
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
                preroll_count = 0  # reset on win
            else:
                profit -= bet
                preroll_count += 1

            # Transition to stint?
            if preroll_count >= preroll_len:
                phase = 'stint'
                stint_count = 0
                stint_bet = base

        elif phase == 'stint':
            bet = stint_bet

            # Bet safety
            if bet > bal * 0.95:
                # Soft bust — retreat
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
                # Win! Retreat to preroll.
                phase = 'preroll'
                preroll_count = 0
                stint_bet = base
            else:
                profit -= bet
                stint_count += 1
                if stint_count >= stint_len:
                    # Stint expired — retreat
                    phase = 'preroll'
                    preroll_count = 0
                    stint_bet = base
                else:
                    stint_bet *= iol

    return (profit, False, hands, wagered)


# =====================================================================
# Runner
# =====================================================================

def run_strategy(name, worker_fn, args_template, num=NUM_SESSIONS):
    """Run a strategy through MC and return scorecard."""
    cores = cpu_count()
    t0 = time.time()

    args_list = []
    for i in range(num):
        a = list(args_template)
        a[0] = i  # session index
        args_list.append(tuple(a))

    with Pool(processes=cores) as pool:
        results = pool.map(worker_fn, args_list)

    elapsed = time.time() - t0
    card = scorecard(results, bank=BANK, house_edge_pct=1.0, label=name)

    # Extra stats
    profits = [r[0] for r in results]
    wagers = [r[3] for r in results]
    card['avg_wagered'] = statistics.mean(wagers)
    card['wager_mult'] = card['avg_wagered'] / BANK

    print("\n  {} — {:.1f}s ({} sessions)".format(name, elapsed, num))
    print_scorecard(card, bank=BANK)
    return card


def main():
    print("=" * 80)
    print("  LIMBO PROFIT STRATEGIES — Monte Carlo Comparison")
    print("  Bank: ${} | Sessions: {} | Max bets: {}".format(
        BANK, NUM_SESSIONS, MAX_BETS))
    print("=" * 80)

    all_cards = []

    # --- APEX ---
    # args: (s, start_target, target_step, target_cap, bet_iol, div, tp_pct, sl_pct)
    apex_args = (0, 2.0, 1.15, 10.0, 1.5, 10000, 10, 30)
    card_apex = run_strategy("APEX", _apex, apex_args)
    all_cards.append(card_apex)

    # --- CASCADE ---
    # args: (s, chain_target, chain_len, chain_iol, div, tp_pct, sl_pct)
    cascade_args = (0, 2.0, 3, 1.25, 10000, 10, 30)
    card_cascade = run_strategy("CASCADE", _cascade, cascade_args)
    all_cards.append(card_cascade)

    # --- PULSE ---
    # args: (s, target, preroll_len, stint_len, covered, tp_pct, sl_pct)
    pulse_args = (0, 5.0, 5, 15, 25, 10, 30)
    card_pulse = run_strategy("PULSE", _pulse, pulse_args)
    all_cards.append(card_pulse)

    # === Ranking ===
    print("\n" + "=" * 80)
    print("  RANKING BY G (Session Growth Rate)")
    print("=" * 80)
    print_ranking(all_cards, bank=BANK)

    # === Head-to-head table ===
    print("\n" + "=" * 80)
    print("  HEAD-TO-HEAD COMPARISON")
    print("=" * 80)
    print("  {:<12} {:>8} {:>8} {:>7} {:>7} {:>8} {:>8} {:>8} {:>6}".format(
        'Strategy', 'Median', 'Mean', 'Win%', 'Bust%', 'CVaR10', 'Wager', 'G(%)', 'HL'))
    print("  " + "-" * 80)

    for c in all_cards:
        hl = "{:.0f}".format(c['half_life']) if c['half_life'] < 99999 else "inf"
        print("  {:<12} ${:>+6.2f} ${:>+6.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} {:>5.1f}x {:>+6.2f}% {:>5}".format(
            c['tag'], c['median'], c['mean'], c['win_pct'], c['bust_pct'],
            c['CVaR10'], c['wager_mult'], c['G_pct'], hl))

    # === Distribution tails ===
    print("\n" + "=" * 80)
    print("  DISTRIBUTION TAILS (percentiles)")
    print("=" * 80)
    print("  {:<12} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
        'Strategy', 'P5', 'P10', 'P25', 'Median', 'P75', 'P90', 'P95'))
    print("  " + "-" * 72)

    for c in all_cards:
        print("  {:<12} ${:>+6.2f} ${:>+6.2f} ${:>+6.2f} ${:>+6.2f} ${:>+6.2f} ${:>+6.2f} ${:>+6.2f}".format(
            c['tag'],
            c.get('p5', 0), c.get('p10', 0), c.get('p25', 0),
            c['median'],
            c.get('p75', 0), c.get('p90', 0), c.get('p95', 0)))


if __name__ == "__main__":
    main()
