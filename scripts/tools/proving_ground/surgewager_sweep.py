#!/usr/bin/env python3
"""SURGEWAGER — Stop Profit % sweep.

Custom simulation because SURGEWAGER has dual-phase bet sizing with
dynamic engine switching (98% wager → 45% recovery) that doesn't fit
the standard run_session() loop.

Sweep: stopProfitPct = [1, 1.5, 2, 3, 5]
Fixed: SL=30%, wagerDiv=100, recoverDiv=5000, IOL=88%, switchAt=2.5%
Bank: $100, 5K bets per session, 5K sessions per config.
"""
import random, statistics, sys, os, time
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard import scorecard, print_ranking, print_scorecard

# === Constants ===
SEED = 42
BANK = 100
MAX_BETS = 5000
NUM_SESSIONS = 5000

# Wager phase: 98% chance, 1.0102x target
WAGER_CHANCE = 0.99 * 100.0 / 1.0102 / 100.0  # ~0.98
WAGER_NET_PAYOUT = 1.0102 - 1.0                 # +0.0102 per win

# Recovery phase: ~45% chance, 2.2x target
RECOVER_CHANCE = 0.99 / 2.2                      # ~0.45
RECOVER_NET_PAYOUT = 2.2 - 1.0                   # +1.2 per win


def _surgewager(args):
    (session_idx, wager_div, recover_div, increase_win_pct, reset_streak,
     recover_iol_pct, switch_pct, tp_pct, sl_pct) = args

    rng = random.Random(SEED * 100000 + session_idx)
    bank = BANK

    wager_base = max(bank / wager_div, 0.00101)
    recover_base = max(bank / recover_div, 0.00101)

    bet = wager_base
    phase = 1  # 1=wager, 2=recovery
    profit = 0.0
    wagered = 0.0
    win_streak = 0
    recovery_chain = 0

    tp_amt = bank * tp_pct / 100 if tp_pct > 0 else None
    sl_amt = bank * sl_pct / 100 if sl_pct > 0 else None
    switch_thresh = bank * switch_pct / 100

    for _ in range(MAX_BETS):
        bal = bank + profit

        # Hard bust
        if bal <= 0.001:
            return (profit, True, _ + 1, wagered)

        # Stop loss
        if sl_amt is not None and -profit >= sl_amt:
            return (profit, False, _ + 1, wagered)

        # Stop profit
        if tp_amt is not None and profit >= tp_amt:
            return (profit, False, _ + 1, wagered)

        # Bet safety cap
        if bet > bal * 0.95:
            bet = bal * 0.95
        if bet < 0.00101:
            bet = 0.00101

        wagered += bet

        # Resolve based on current phase
        if phase == 1:
            won = rng.random() < WAGER_CHANCE
            net = WAGER_NET_PAYOUT
        else:
            won = rng.random() < RECOVER_CHANCE
            net = RECOVER_NET_PAYOUT

        # Update profit
        if won:
            profit += bet * net
        else:
            profit -= bet

        # --- Phase 1: WAGER logic ---
        if phase == 1:
            if won:
                win_streak += 1
                bet *= (1 + increase_win_pct / 100)
                if win_streak > 0 and win_streak % reset_streak == 0:
                    bet = wager_base
            else:
                win_streak = 0
                bet = wager_base
                # Check switch to recovery
                if profit <= -switch_thresh:
                    phase = 2
                    bet = recover_base
                    recovery_chain = 0

        # --- Phase 2: RECOVERY logic ---
        elif phase == 2:
            if won:
                win_streak += 1
                bet = recover_base
                recovery_chain = 0
                # Check: recovered?
                if profit >= 0:
                    phase = 1
                    bet = wager_base
                    win_streak = 0
            else:
                win_streak = 0
                recovery_chain += 1
                bet *= (1 + recover_iol_pct / 100)

    return (profit, False, MAX_BETS, wagered)


def run_sweep():
    tp_values = [1.0, 1.5, 2.0, 3.0, 5.0]
    cores = cpu_count()

    # Fixed params
    wager_div = 100
    recover_div = 5000
    increase_win_pct = 15
    reset_streak = 5
    recover_iol_pct = 88
    switch_pct = 2.5
    sl_pct = 30

    all_cards = []

    print("=" * 80)
    print("  SURGEWAGER — Stop Profit Sweep (Limbo)")
    print("  Bank: ${} | Sessions: {} | Max bets: {}".format(BANK, NUM_SESSIONS, MAX_BETS))
    print("  Wager: div={} ({}%) | +{}%/win, reset@{}-streak".format(
        wager_div, round(WAGER_CHANCE * 100, 1), increase_win_pct, reset_streak))
    print("  Recovery: div={} ({}%) | IOL {}% | trigger=-{}%".format(
        recover_div, round(RECOVER_CHANCE * 100, 1), recover_iol_pct, switch_pct))
    print("  Stop loss: {}%".format(sl_pct))
    print("=" * 80)

    for tp in tp_values:
        t0 = time.time()
        label = "TP={}%  SL={}%".format(tp, sl_pct)

        args_list = [
            (i, wager_div, recover_div, increase_win_pct, reset_streak,
             recover_iol_pct, switch_pct, tp, sl_pct)
            for i in range(NUM_SESSIONS)
        ]

        with Pool(processes=cores) as pool:
            results = pool.map(_surgewager, args_list)

        # Extract wager stats (scorecard needs profit, busted, hands, wagered)
        wagers = [r[3] for r in results]
        avg_wager = statistics.mean(wagers)
        wager_mult = avg_wager / BANK

        card = scorecard(results, bank=BANK, house_edge_pct=1.0, label=label)
        card['avg_wagered'] = avg_wager
        card['wager_mult'] = wager_mult
        all_cards.append(card)

        elapsed = time.time() - t0
        print("\n  {} — {:.1f}s".format(label, elapsed))
        print_scorecard(card, bank=BANK)

    # === Ranking ===
    print("\n" + "=" * 80)
    print("  RANKING BY G (Session Growth Rate)")
    print("=" * 80)
    print_ranking(all_cards, bank=BANK)

    # === Wager-specific table ===
    print("\n" + "=" * 80)
    print("  WAGER EFFICIENCY TABLE")
    print("=" * 80)
    print("  {:<16} {:>8} {:>8} {:>8} {:>8} {:>8} {:>10}".format(
        'Config', 'Median', 'Win%', 'Bust%', 'Wager', 'W/Loss', 'Cost/1kW'))
    print("  " + "-" * 72)

    for c in all_cards:
        # Cost per $1k wagered = expected loss per session / (wager/1000)
        exp_loss = -c['mean']  # mean is negative for -EV
        cost_per_1k = (exp_loss / c['avg_wagered'] * 1000) if c['avg_wagered'] > 0 else 0
        # Wager per dollar lost
        w_per_loss = c['avg_wagered'] / exp_loss if exp_loss > 0 else float('inf')

        print("  {:<16} ${:>+6.2f} {:>6.1f}% {:>6.1f}% {:>6.1f}x ${:>6.0f} ${:>8.2f}".format(
            c['tag'], c['median'], c['win_pct'], c['bust_pct'],
            c['wager_mult'], w_per_loss, cost_per_1k))


if __name__ == "__main__":
    run_sweep()
