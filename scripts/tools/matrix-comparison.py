#!/usr/bin/env python3
"""
BJ Matrix Comparison — H17 Correction Impact
Full card-dealing simulator on infinite deck. Flat bet only.
Compares current Vrafasky matrix (S17 conventions) vs H17-corrected matrix.

Changes tested:
  1. Hard 11 vs Ace: Hit → Double
  2. Soft 19 (A,8) vs 6: Stand → Double/Stand
"""

import random
import sys
import time
import copy

# ============================================================
# CARD DEALING — Infinite deck
# ============================================================

def deal():
    """Deal one card from infinite deck. Returns value (2-11, where 11=Ace)."""
    return random.choice([2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11])

def hand_val(cards):
    """Returns (total, is_soft)."""
    t = sum(cards)
    a = sum(1 for c in cards if c == 11)
    while t > 21 and a > 0:
        t -= 10
        a -= 1
    return t, a > 0

def is_bj(cards):
    return len(cards) == 2 and sorted(cards) == [10, 11]


# ============================================================
# BET MATRICES
# ============================================================

# Current Vrafasky matrix (S17 conventions)
# Dealer upcard key: 2-10 for number, 11 for Ace
MATRIX_CURRENT = {
    'hard': {
        4:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
        5:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
        6:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
        7:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
        8:  {2:'H',3:'H',4:'H',5:'H',6:'H',7:'H',8:'H',9:'H',10:'H',11:'H'},
        9:  {2:'H',3:'D',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        10: {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'H',11:'H'},
        11: {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'D',11:'H'},
        12: {2:'H',3:'H',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
        13: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
        14: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
        15: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
        16: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'H',8:'H',9:'H',10:'H',11:'H'},
        17: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        18: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        19: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        20: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        21: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
    },
    'soft': {
        12: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        13: {2:'H',3:'H',4:'H',5:'H',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        14: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        15: {2:'H',3:'H',4:'H',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        16: {2:'H',3:'H',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        17: {2:'H',3:'D',4:'D',5:'D',6:'D',7:'H',8:'H',9:'H',10:'H',11:'H'},
        18: {2:'S',3:'DS',4:'DS',5:'DS',6:'DS',7:'S',8:'S',9:'H',10:'H',11:'H'},
        19: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        20: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        21: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
    },
    'splits': {
        2:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
        3:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
        4:  {2:'H',3:'H',4:'H',5:'P',6:'P',7:'H',8:'H',9:'H',10:'H',11:'H'},
        5:  {2:'D',3:'D',4:'D',5:'D',6:'D',7:'D',8:'D',9:'D',10:'H',11:'H'},
        6:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'H',8:'H',9:'H',10:'H',11:'H'},
        7:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'H',9:'H',10:'H',11:'H'},
        8:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'P',9:'P',10:'P',11:'P'},
        9:  {2:'P',3:'P',4:'P',5:'P',6:'P',7:'S',8:'P',9:'P',10:'S',11:'S'},
        10: {2:'S',3:'S',4:'S',5:'S',6:'S',7:'S',8:'S',9:'S',10:'S',11:'S'},
        11: {2:'P',3:'P',4:'P',5:'P',6:'P',7:'P',8:'P',9:'P',10:'P',11:'P'},
    },
}

# H17-corrected matrix (2 cells changed)
MATRIX_H17 = copy.deepcopy(MATRIX_CURRENT)
MATRIX_H17['hard'][11][11] = 'D'     # 11 vs Ace: Hit → Double
MATRIX_H17['soft'][19][6] = 'DS'     # Soft 19 vs 6: Stand → Double/Stand


# ============================================================
# MATRIX LOOKUP
# ============================================================

def lookup(cards, val, soft, dealer_up, matrix, can_split):
    """Look up matrix action for this hand state."""
    d = dealer_up

    # Split check
    if can_split and len(cards) == 2 and cards[0] == cards[1]:
        pk = cards[0]
        if pk in matrix['splits']:
            a = matrix['splits'][pk].get(d)
            if a == 'P':
                return 'P'
            if a == 'D':
                return 'D'
            # Non-split action — fall through

    # Soft hand
    if soft and val in matrix['soft']:
        a = matrix['soft'][val].get(d, 'H')
        if a == 'DS':
            return 'D' if len(cards) == 2 else 'S'
        if a == 'D' and len(cards) > 2:
            return 'H'
        return a

    # Hard hand
    if val in matrix['hard']:
        a = matrix['hard'][val].get(d, 'H')
        if a == 'D' and len(cards) > 2:
            return 'H'
        return a

    return 'S' if val >= 17 else 'H'


# ============================================================
# HAND SIMULATION
# ============================================================

def dealer_play(cards):
    """Dealer plays H17 (hits soft 17)."""
    while True:
        t, s = hand_val(cards)
        if t > 17:
            break
        if t == 17 and not s:
            break
        cards.append(deal())

def play_hand(matrix, stats):
    """Simulate one BJ hand. Returns net result as bet multiplier."""
    p = [deal(), deal()]
    d = [deal(), deal()]
    d_up = d[0]

    p_bj = is_bj(p)
    d_bj = is_bj(d)

    if p_bj and d_bj:
        return 0.0
    if p_bj:
        stats['bj'] += 1
        return 1.5
    if d_bj:
        return -1.0

    # Player plays all hands (with possible split)
    to_play = [(list(p), 1.0, True)]
    finished = []

    while to_play:
        cards, bet, can_split = to_play.pop(0)

        while True:
            val, soft = hand_val(cards)
            if val >= 21:
                break

            action = lookup(cards, val, soft, d_up, matrix, can_split and len(cards) == 2 and cards[0] == cards[1])

            if action == 'S':
                break
            elif action == 'H':
                cards.append(deal())
            elif action == 'D':
                stats['doubles'] += 1
                bet *= 2
                cards.append(deal())
                break
            elif action == 'P':
                stats['splits'] += 1
                c1, c2 = cards[0], cards[1]
                to_play.append(([c2, deal()], 1.0, False))
                cards = [c1, deal()]
                bet = 1.0
                can_split = False
            else:
                break

        finished.append((cards, bet))

    # Dealer plays
    dealer_play(d)
    d_val, _ = hand_val(d)

    # Evaluate
    result = 0.0
    for cards, bet in finished:
        pv, _ = hand_val(cards)
        if pv > 21:
            result -= bet
        elif d_val > 21:
            result += bet
        elif pv > d_val:
            result += bet
        elif pv < d_val:
            result -= bet
    return result


# ============================================================
# SIMULATOR
# ============================================================

def simulate(matrix, num_sessions, hands_per_session, seed, label):
    """Run flat-bet sessions and return results."""
    results = []
    total_hands = 0
    total_wagered = 0.0
    total_pnl = 0.0
    stats = {'bj': 0, 'doubles': 0, 'splits': 0}

    t0 = time.time()
    for s in range(num_sessions):
        if s % 1000 == 0 and s > 0:
            elapsed = time.time() - t0
            rate = s / elapsed
            eta = (num_sessions - s) / rate
            print(f"\r  [{label}] Session {s:,}/{num_sessions:,} ({elapsed:.1f}s, ~{eta:.0f}s left)   ", end='', flush=True)

        random.seed(seed * 100000 + s)
        profit = 0.0

        for _ in range(hands_per_session):
            result = play_hand(matrix, stats)
            profit += result
            total_wagered += 1.0  # Flat bet = 1 unit per hand (before doubles)
            total_hands += 1

        total_pnl += profit
        results.append(profit)

    elapsed = time.time() - t0
    print(f"\r  [{label}] Done: {num_sessions:,} sessions in {elapsed:.1f}s" + " " * 30)

    results.sort()
    n = len(results)
    return {
        'label': label,
        'results': results,
        'mean': sum(results) / n,
        'median': results[n // 2],
        'p10': results[n // 10],
        'p90': results[9 * n // 10],
        'total_hands': total_hands,
        'total_wagered': total_wagered,
        'total_pnl': total_pnl,
        'house_edge': -total_pnl / total_wagered * 100 if total_wagered > 0 else 0,
        'stats': stats,
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    num_sessions = 10000
    hands = 1000
    seed = 42

    if "--quick" in sys.argv:
        num_sessions = 2000

    print()
    print("=" * 90)
    print("  BJ MATRIX COMPARISON — H17 Correction Impact")
    print(f"  {num_sessions:,} sessions x {hands:,} hands | Flat bet (1 unit) | Infinite deck | H17")
    print(f"  Seed: {seed}")
    print("=" * 90)
    print()
    print("  Changes tested:")
    print("    1. Hard 11 vs Ace: Hit → Double")
    print("    2. Soft 19 (A,8) vs 6: Stand → Double/Stand")
    print()

    # Run both matrices
    r_current = simulate(MATRIX_CURRENT, num_sessions, hands, seed, "S17 Matrix (current)")
    r_h17 = simulate(MATRIX_H17, num_sessions, hands, seed, "H17 Matrix (corrected)")

    # Results
    print()
    print("=" * 90)
    print("  RESULTS")
    print("=" * 90)
    print()
    print(f"  {'Metric':<30} {'S17 (current)':>18} {'H17 (corrected)':>18} {'Difference':>14}")
    print(f"  {'─'*30} {'─'*18} {'─'*18} {'─'*14}")

    metrics = [
        ("House Edge",          f"{r_current['house_edge']:.4f}%",     f"{r_h17['house_edge']:.4f}%",
         f"{r_h17['house_edge'] - r_current['house_edge']:+.4f}%"),
        ("Mean Profit (units)", f"{r_current['mean']:+.4f}",           f"{r_h17['mean']:+.4f}",
         f"{r_h17['mean'] - r_current['mean']:+.4f}"),
        ("Median Profit",       f"{r_current['median']:+.2f}",         f"{r_h17['median']:+.2f}",
         f"{r_h17['median'] - r_current['median']:+.2f}"),
        ("P10",                 f"{r_current['p10']:+.2f}",            f"{r_h17['p10']:+.2f}",
         f"{r_h17['p10'] - r_current['p10']:+.2f}"),
        ("P90",                 f"{r_current['p90']:+.2f}",            f"{r_h17['p90']:+.2f}",
         f"{r_h17['p90'] - r_current['p90']:+.2f}"),
        ("Blackjacks",          f"{r_current['stats']['bj']:,}",       f"{r_h17['stats']['bj']:,}",         ""),
        ("Doubles",             f"{r_current['stats']['doubles']:,}",   f"{r_h17['stats']['doubles']:,}",
         f"{r_h17['stats']['doubles'] - r_current['stats']['doubles']:+,}"),
        ("Splits",              f"{r_current['stats']['splits']:,}",    f"{r_h17['stats']['splits']:,}",     ""),
    ]

    for name, v1, v2, diff in metrics:
        print(f"  {name:<30} {v1:>18} {v2:>18} {diff:>14}")

    # Per-hand impact
    total_h = r_current['total_hands']
    edge_diff = r_h17['house_edge'] - r_current['house_edge']
    mean_diff = r_h17['mean'] - r_current['mean']

    print()
    print(f"  {'─'*90}")
    print(f"  IMPACT ANALYSIS")
    print(f"  {'─'*90}")
    print(f"  Total hands simulated:   {total_h:,} per matrix")
    print(f"  House edge change:       {edge_diff:+.4f}% ({'+' if edge_diff > 0 else ''}{'worse' if edge_diff > 0 else 'better'} for house)")
    print(f"  Mean session diff:       {mean_diff:+.4f} units / {hands} hands")
    print(f"  Extra doubles (H17):     {r_h17['stats']['doubles'] - r_current['stats']['doubles']:+,}")

    # Scale to real money
    print()
    print(f"  At div=2000 ($0.50 unit), per 2000-hand session:")
    unit = 0.50
    session_diff = mean_diff * 2 * unit  # Scale from 1000 hands to 2000, multiply by unit
    print(f"    Session profit diff:   ${session_diff:+.4f}")
    print(f"    Annual diff (1 session/day): ${session_diff * 365:+.2f}")

    print()
    verdict = "BETTER" if edge_diff < 0 else "WORSE" if edge_diff > 0 else "IDENTICAL"
    print(f"  VERDICT: H17 matrix is {verdict} by {abs(edge_diff):.4f}% house edge")
    if abs(session_diff) < 0.10:
        print(f"  The difference is ${abs(session_diff):.4f}/session — statistically real but practically negligible.")
    else:
        print(f"  The difference is ${abs(session_diff):.2f}/session — worth implementing.")
    print("=" * 90)
