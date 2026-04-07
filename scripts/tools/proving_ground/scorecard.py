#!/usr/bin/env python3
"""PROVING GROUND — Universal Strategy Scorecard.

ONE primary metric: G (Session Growth Rate)
G = exp(mean(log(max(1 + profit/bank, eps)))) - 1

G naturally captures mean, risk, consistency, and catastrophic loss
in a single number via log-wealth compounding (Kelly/Shannon).

THREE diagnostic dimensions:
- CR (Capture Ratio):  median / |mean| — exit rule quality
- ED (Edge Drag):      wagered/bank × edge% — house edge cost
- CVaR10:              mean of worst 10% — tail risk severity

Plus a projection panel showing bankroll trajectory over N sessions.
"""
import math, statistics


def scorecard(results, bank=100, house_edge_pct=1.0, label=""):
    """Compute the universal scorecard from session results.

    Args:
        results: list of (profit, busted, hands, wagered) tuples
        bank: starting bankroll per session
        house_edge_pct: game's theoretical house edge (dice=1.0, roulette=2.7, etc.)
        label: strategy name for display

    Returns:
        dict with all metrics
    """
    profits = [r[0] for r in results]
    hands_list = [r[2] for r in results]
    wagered_list = [r[3] for r in results]
    n = len(profits)
    sorted_p = sorted(profits)

    # === PRIMARY: Growth Rate G ===
    eps = 0.001  # floor to avoid log(0)
    log_wealth = [math.log(max(1 + p / bank, eps / bank)) for p in profits]
    G = math.exp(statistics.mean(log_wealth)) - 1

    # === BASIC STATS ===
    mean = statistics.mean(profits)
    median = sorted_p[n // 2]
    stdev = statistics.stdev(profits) if n > 1 else 0
    bust_pct = sum(1 for r in results if r[1]) / n * 100
    win_pct = sum(1 for p in profits if p > 0) / n * 100
    avg_hands = statistics.mean(hands_list)
    avg_wagered = statistics.mean(wagered_list)

    # === DIAGNOSTIC 1: Capture Ratio (CR) ===
    CR = median / abs(mean) if mean != 0 else 0

    # === DIAGNOSTIC 2: Edge Drag (ED) ===
    ED = (avg_wagered / bank) * (house_edge_pct / 100)

    # === DIAGNOSTIC 3: CVaR10 ===
    worst_10 = sorted_p[:max(1, n // 10)]
    CVaR10 = statistics.mean(worst_10)

    # === PROJECTIONS ===
    g1 = 1 + G
    proj_10 = bank * (g1 ** 10)
    proj_25 = bank * (g1 ** 25)
    proj_50 = bank * (g1 ** 50)
    half_life = abs(math.log(0.5) / math.log(g1)) if g1 > 0 and g1 != 1 else float('inf')
    double_life = (math.log(2) / math.log(g1)) if g1 > 1 else float('inf')

    # Break-even odds after 10 sessions (P(sum > 0) ≈ Phi(mean*sqrt(10)/stdev))
    if stdev > 0 and n > 1:
        z_10 = (mean * math.sqrt(10)) / stdev
        # Approximate Phi(z) for |z| < 6
        be_10 = 0.5 * (1 + math.erf(z_10 / math.sqrt(2)))
    else:
        be_10 = 0.5

    return {
        'tag': label,
        'G': G, 'G_pct': G * 100,
        'mean': mean, 'median': median, 'stdev': stdev,
        'bust_pct': bust_pct, 'win_pct': win_pct,
        'CR': CR, 'ED': ED, 'ED_pct': ED * 100,
        'CVaR10': CVaR10,
        'avg_hands': avg_hands, 'avg_wagered': avg_wagered,
        'proj_10': proj_10, 'proj_25': proj_25, 'proj_50': proj_50,
        'half_life': half_life, 'double_life': double_life,
        'be_10': be_10 * 100,
    }


def print_scorecard(s, bank=100):
    """Pretty-print a single strategy scorecard."""
    print("  ┌─ {} ─".format(s['tag']) + "─" * max(0, 60 - len(s['tag'])) + "┐")
    print("  │")

    # Primary score
    g_bar = "▓" * max(0, min(50, int((s['G_pct'] + 10) * 5))) + "░" * max(0, 50 - int((s['G_pct'] + 10) * 5))
    grade = "A+" if s['G_pct'] > -0.5 else "A" if s['G_pct'] > -1 else "B" if s['G_pct'] > -2 else "C" if s['G_pct'] > -4 else "D" if s['G_pct'] > -8 else "F"
    print("  │  G = {:>+.4f}  ({:>+.2f}% per session)   Grade: {}".format(s['G'], s['G_pct'], grade))
    print("  │")

    # Diagnostics
    print("  │  CR  = {:>6.2f}   (exit rules capture {:.1f}x the theoretical loss)".format(s['CR'], s['CR']))
    print("  │  ED  = {:>6.2f}%  (house edge drags {:.2f}% of bankroll/session)".format(s['ED_pct'], s['ED_pct']))
    print("  │  CVaR = ${:>+.2f}  (average of worst 10% of sessions)".format(s['CVaR10']))
    print("  │")

    # Raw stats
    print("  │  Mean: ${:>+.2f}  Median: ${:>+.2f}  Stdev: ${:.2f}".format(s['mean'], s['median'], s['stdev']))
    print("  │  Win: {:.1f}%  Bust: {:.1f}%  Hands: {:.0f}  Wagered: ${:.0f}".format(
        s['win_pct'], s['bust_pct'], s['avg_hands'], s['avg_wagered']))
    print("  │")

    # Projections
    print("  │  Projections (starting ${:.0f} per session):".format(bank))
    print("  │    After 10 sessions:  ${:.2f}".format(s['proj_10']))
    print("  │    After 25 sessions:  ${:.2f}".format(s['proj_25']))
    print("  │    After 50 sessions:  ${:.2f}".format(s['proj_50']))
    hl = "{:.0f}".format(s['half_life']) if s['half_life'] < 99999 else "never"
    print("  │    Bankroll half-life: {} sessions".format(hl))
    print("  │    Break-even after 10: {:.1f}% chance".format(s['be_10']))
    print("  │")
    print("  └" + "─" * 65 + "┘")


def print_ranking(scorecards, bank=100):
    """Print ranked comparison table."""
    scorecards.sort(key=lambda x: x['G'], reverse=True)

    print("  {:<4} {:<35} {:>7} {:>7} {:>7} {:>6} {:>6} {:>7} {:>8} {:>5}".format(
        '#', 'Strategy', 'G(%)', 'Mean', 'Median', 'CR', 'ED(%)', 'CVaR10', 'Grade', 'HL'))
    print("  " + "-" * 100)

    for i, s in enumerate(scorecards):
        grade = "A+" if s['G_pct'] > -0.5 else "A" if s['G_pct'] > -1 else "B" if s['G_pct'] > -2 else "C" if s['G_pct'] > -4 else "D" if s['G_pct'] > -8 else "F"
        hl = "{:.0f}".format(s['half_life']) if s['half_life'] < 99999 else "inf"
        print("  {:<4} {:<35} {:>+6.2f}% ${:>+6.2f} ${:>+6.2f} {:>5.1f} {:>5.2f}% ${:>+7.2f} {:>5} {:>5}".format(
            i + 1, s['tag'], s['G_pct'], s['mean'], s['median'],
            s['CR'], s['ED_pct'], s['CVaR10'], grade, hl))
