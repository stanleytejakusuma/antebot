#!/usr/bin/env python3
"""
D'Alembert Monte Carlo Simulator for Blackjack & Baccarat
Finds optimal parameters (divider, bet cap, vault target) before going live.

Usage:
  python3 dalembert-simulator.py                    # Run full parameter sweep
  python3 dalembert-simulator.py --quick             # Quick 1000-session test
  python3 dalembert-simulator.py --game baccarat     # Baccarat only
"""

import random
import sys
from collections import defaultdict

# ============================================================
# OUTCOME MODELS
# ============================================================

# Blackjack 8-deck, perfect basic strategy (~0.5% house edge)
# Payout multiplier = NET profit relative to base bet.
# +1 = win 1x bet, -1 = lose 1x bet, +2 = win 2x (doubled), etc.
# Probabilities derived from standard BJ sim data, then normal win/loss
# adjusted so total EV = -0.005 (0.5% house edge).
#
# Special outcomes (fixed from BJ statistics):
#   BJ:          4.75%  →  +1.5x  (3:2 natural)
#   Push:        8.48%  →  0x
#   Double win:  5.32%  →  +2x
#   Double loss: 4.18%  →  -2x
#   Split win:   0.48%  →  +2x (net across split hands)
#   Split loss:  0.56%  →  -2x
#   Split push:  0.05%  →  0x
#   Split+dbl W: 0.04%  →  +4x
#   Split+dbl L: 0.04%  →  -4x
# Total special: 23.90%, special EV: +0.09245
# Remaining: 76.10% for normal win + normal loss
# Need: w - l = -0.005 - 0.09245 = -0.09745, w + l = 0.761
# → normal_win = 0.33178, normal_loss = 0.42922
BJ_OUTCOMES = [
    (0.0475, +1.5, -1, "blackjack"),
    (0.3318, +1.0, -1, "win"),
    (0.4292, -1.0, +1, "loss"),
    (0.0848, 0.0,   0, "push"),
    (0.0532, +2.0, -2, "double_win"),
    (0.0418, -2.0, +2, "double_loss"),
    (0.0048, +2.0, -2, "split_win"),
    (0.0056, -2.0, +2, "split_loss"),
    (0.0005, 0.0,   0, "split_push"),
    (0.0004, +4.0, -4, "splitdbl_win"),
    (0.0004, -4.0, +4, "splitdbl_loss"),
]

# Baccarat banker bet
# 5% commission on banker wins → net payout 0.95x
BACC_OUTCOMES = [
    (0.4586, +0.95, -1, "banker_win"),
    (0.4462, -1.0,  +1, "player_win"),
    (0.0952, 0.0,    0, "tie"),
]

def verify_model(outcomes, name):
    """Verify probabilities sum to 1 and compute house edge."""
    total_prob = sum(o[0] for o in outcomes)
    expected_return = sum(o[0] * o[1] for o in outcomes)
    house_edge = -expected_return * 100
    print(f"  {name}: probs sum={total_prob:.4f}, house edge={house_edge:.3f}%")
    return house_edge


# ============================================================
# SIMULATOR
# ============================================================

def random_outcome(outcomes):
    """Pick a random outcome based on probability distribution."""
    r = random.random()
    cumulative = 0
    for prob, payout, units, label in outcomes:
        cumulative += prob
        if r < cumulative:
            return payout, units, label
    # Fallback (rounding)
    return outcomes[-1][1], outcomes[-1][2], outcomes[-1][3]


def simulate_session(outcomes, divider, max_mult, vault_target, stop_loss, max_hands):
    """Simulate one session of D'Alembert progression."""
    bankroll = 1000.0
    unit = bankroll / divider
    bet = unit
    profit = 0.0
    peak = 0.0
    max_drawdown = 0.0
    vaults = 0
    vault_total = 0.0
    hands = 0

    for _ in range(max_hands):
        hands += 1
        payout, unit_change, label = random_outcome(outcomes)

        # Apply payout (bet * payout_multiplier)
        hand_profit = bet * payout
        profit += hand_profit

        # Track peak and drawdown
        if profit > peak:
            peak = profit
        dd = peak - profit
        if dd > max_drawdown:
            max_drawdown = dd

        # Stop loss check
        if profit <= -stop_loss:
            return {
                'profit': profit, 'vaults': vaults, 'vault_total': vault_total,
                'bust': True, 'hands': hands, 'max_dd': max_drawdown
            }

        # D'Alembert progression
        if unit_change != 0:
            bet += unit * unit_change

        # Enforce bounds
        if bet < unit:
            bet = unit
        if bet > unit * max_mult:
            bet = unit * max_mult

        # Vault check (only when bet is at base = just recovered)
        if vault_target > 0 and profit >= vault_target and bet <= unit * 1.01:
            vault_total += profit
            vaults += 1
            profit = 0.0
            peak = 0.0
            bet = unit

    return {
        'profit': profit, 'vaults': vaults, 'vault_total': vault_total,
        'bust': False, 'hands': hands, 'max_dd': max_drawdown
    }


def run_sweep(game, outcomes, sessions, max_hands):
    """Run parameter sweep and print results."""
    dividers = [100, 200, 500, 1000, 2000, 5000]
    max_mults = [10, 15, 20]
    vault_targets = [0, 25, 50]
    stop_loss = 300

    print(f"\n{'='*90}")
    print(f"  {game.upper()} — {sessions:,} sessions × {max_hands:,} hands | Stop loss: ${stop_loss}")
    print(f"{'='*90}")
    print(f"{'Div':>5} | {'Cap':>3}x | {'Vault':>5} | {'Mean P':>8} | {'Med P':>8} | {'Bust%':>6} | {'Vaults':>6} | {'VaultTot':>8} | {'MaxDD':>7} | {'Net$':>8}")
    print(f"{'-'*5}-|-{'-'*4}-|-{'-'*5}-|-{'-'*8}-|-{'-'*8}-|-{'-'*6}-|-{'-'*6}-|-{'-'*8}-|-{'-'*7}-|-{'-'*8}")

    best_net = -999999
    best_config = None

    for div in dividers:
        for mult in max_mults:
            for vault_t in vault_targets:
                results = []
                for _ in range(sessions):
                    r = simulate_session(outcomes, div, mult, vault_t, stop_loss, max_hands)
                    results.append(r)

                profits = [r['profit'] for r in results]
                vault_totals = [r['vault_total'] for r in results]
                busts = sum(1 for r in results if r['bust'])
                avg_vaults = sum(r['vaults'] for r in results) / sessions
                avg_vault_total = sum(vault_totals) / sessions
                avg_dd = sum(r['max_dd'] for r in results) / sessions

                profits.sort()
                mean_p = sum(profits) / len(profits)
                median_p = profits[len(profits) // 2]
                bust_pct = busts / sessions * 100

                # Net = vault_total + remaining profit (what you'd walk away with)
                net_values = [r['vault_total'] + r['profit'] for r in results]
                avg_net = sum(net_values) / len(net_values)

                if avg_net > best_net:
                    best_net = avg_net
                    best_config = (div, mult, vault_t)

                # Print rows with reasonable bust rates
                if bust_pct < 80:
                    print(f"{div:>5} | {mult:>3}x | ${vault_t:>4} | ${mean_p:>7.2f} | ${median_p:>7.2f} | {bust_pct:>5.1f}% | {avg_vaults:>5.1f} | ${avg_vault_total:>7.2f} | ${avg_dd:>6.2f} | ${avg_net:>7.2f}")

    print(f"\n  BEST CONFIG: divider={best_config[0]}, cap={best_config[1]}x, vault=${best_config[2]} → net ${best_net:.2f}/session")
    return best_config


def run_detail(game, outcomes, config, sessions, max_hands):
    """Run detailed analysis on a specific config."""
    div, mult, vault_t = config
    stop_loss = 300

    results = []
    for _ in range(sessions):
        r = simulate_session(outcomes, div, mult, vault_t, stop_loss, max_hands)
        results.append(r)

    profits = sorted([r['profit'] for r in results])
    nets = sorted([r['vault_total'] + r['profit'] for r in results])
    busts = sum(1 for r in results if r['bust'])
    n = len(results)

    print(f"\n{'='*60}")
    print(f"  {game.upper()} DETAILED — div={div}, cap={mult}x, vault=${vault_t}")
    print(f"  {sessions:,} sessions × {max_hands:,} hands")
    print(f"{'='*60}")
    print(f"  Bust rate:     {busts/n*100:.2f}% ({busts}/{n})")
    print(f"  Mean profit:   ${sum(profits)/n:.2f}")
    print(f"  Median profit: ${profits[n//2]:.2f}")
    print(f"  P10:           ${profits[n//10]:.2f}")
    print(f"  P90:           ${profits[9*n//10]:.2f}")
    print(f"  Mean vaults:   {sum(r['vaults'] for r in results)/n:.1f}")
    print(f"  Mean vaulted:  ${sum(r['vault_total'] for r in results)/n:.2f}")
    print(f"  Mean net:      ${sum(nets)/n:.2f}")
    print(f"  Median net:    ${nets[n//2]:.2f}")
    print(f"  Mean max DD:   ${sum(r['max_dd'] for r in results)/n:.2f}")
    print(f"  Worst max DD:  ${max(r['max_dd'] for r in results):.2f}")
    print(f"  Mean hands:    {sum(r['hands'] for r in results)/n:.0f}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    game_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--game" and i + 1 < len(sys.argv):
            game_filter = sys.argv[i + 1].lower()

    sessions = 1000 if quick else 5000
    max_hands = 2000

    print("D'Alembert Monte Carlo Simulator v1.0")
    print(f"Sessions: {sessions:,} | Hands/session: {max_hands:,}")
    print(f"Bankroll: $1,000 | Stop loss: $300")
    print()

    # Verify models
    print("Model verification:")
    verify_model(BJ_OUTCOMES, "Blackjack")
    verify_model(BACC_OUTCOMES, "Baccarat")

    games = []
    if game_filter is None or game_filter == "blackjack" or game_filter == "bj":
        games.append(("Blackjack", BJ_OUTCOMES))
    if game_filter is None or game_filter == "baccarat" or game_filter == "bacc":
        games.append(("Baccarat", BACC_OUTCOMES))

    for name, outcomes in games:
        best = run_sweep(name, outcomes, sessions, max_hands)
        run_detail(name, outcomes, best, sessions * 2, max_hands)
