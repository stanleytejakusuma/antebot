#!/usr/bin/env python3
"""
SIDEWINDER HiLo Optimizer — Monte Carlo parameter sweep.
Models HiLo card game: predict higher/lower, compound multipliers,
skip unfavorable cards, cash out at target multiplier.

HiLo model:
  - Cards drawn uniformly from 1-13 (infinite deck, provably fair RNG)
  - BET_HIGH on card V: prob=(13-V)/13, payout=0.99*13/(13-V)
  - BET_LOW on card V: prob=(V-1)/13, payout=0.99*13/(V-1)
  - 1% house edge per prediction (0.99 factor)
  - Skip middle cards, cash out at accumulated multiplier target

Usage:
  python3 sidewinder-optimizer.py          # Full sweep (5k sessions)
  python3 sidewinder-optimizer.py --quick  # Quick sweep (2k sessions)
"""

import random
import sys
import time
from itertools import product
import statistics

# ============================================================
# HILO MODEL
# ============================================================

def hilo_payout(card_val, bet_high):
    """
    Returns (probability, payout_multiplier) for a single prediction.
    card_val: 1-13 (Ace=1, King=13)
    bet_high: True = predict next card is higher, False = predict lower
    payout_multiplier: what 1x bet returns on win (net, so 1.5 means +0.5 profit)
    """
    if bet_high:
        prob = (13 - card_val) / 13.0
        if prob <= 0:
            return (0.0, 0.0)
        payout = 0.99 * 13.0 / (13 - card_val)
    else:
        prob = (card_val - 1) / 13.0
        if prob <= 0:
            return (0.0, 0.0)
        payout = 0.99 * 13.0 / (card_val - 1)
    return (prob, payout)


def draw_card(rng):
    """Draw a random card value 1-13."""
    return rng.randint(1, 13)


def sim_hand(rng, skip_set, cashout_target, start_val=None):
    """
    Simulate one HiLo hand.

    Args:
        rng: random.Random instance
        skip_set: set of card values to skip (e.g., {5,6,7,8,9})
        cashout_target: cash out when accumulated multiplier >= this value
        start_val: starting card value (None = draw randomly)

    Returns:
        (won: bool, accumulated_multiplier: float)
        won=False means a prediction was wrong (lost the hand)
        won=True means cashed out successfully at or above target
    """
    if start_val is None:
        current_card = draw_card(rng)
    else:
        current_card = start_val

    accumulated = 1.0
    max_draws = 52

    for _ in range(max_draws):
        # Skip unfavorable cards
        if current_card in skip_set:
            current_card = draw_card(rng)
            continue

        # Decide: BET_HIGH if card <= 7, BET_LOW if card > 7
        bet_high = current_card <= 7
        prob, payout = hilo_payout(current_card, bet_high)

        if prob <= 0:
            # Can't bet on this card (e.g., 1 betting low, 13 betting high)
            # Treat as skip
            current_card = draw_card(rng)
            continue

        # Simulate the prediction
        next_card = draw_card(rng)

        # Check if prediction was correct
        if bet_high:
            correct = next_card > current_card
        else:
            correct = next_card < current_card

        if not correct:
            return (False, accumulated)

        # Multiply accumulated payout
        accumulated *= payout
        current_card = next_card

        # Cash out check
        if accumulated >= cashout_target:
            return (True, accumulated)

    # Hit max draws without reaching target — cash out at current
    return (True, accumulated)


# ============================================================
# SESSION SIMULATOR
# ============================================================

def sim_session(bank, divider, iol, skip_set, cashout_cruise,
                cashout_recovery=None, cashout_capitalize=None,
                trail_act_pct=8, trail_lock_pct=60,
                stop_pct=15, sl_pct=15,
                recovery_threshold_pct=5, recovery_iol_thresh=1.5,
                max_hands=5000, rng=None):
    """
    Simulate one session of SIDEWINDER HiLo.

    Three-mode cashout system:
      CRUISE: normal play, cashout at cashout_cruise
      RECOVERY: when profit < -threshold% or IOL mult > recovery_iol_thresh, cashout at cashout_recovery
      CAPITALIZE: when trailing stop active, cashout at cashout_capitalize

    Trailing stop: activate when profit >= trail_act_pct% of bank.
                   Exit when profit drops below trail_lock_pct% of peak profit.

    Returns (profit, busted)
    """
    if cashout_recovery is None:
        cashout_recovery = cashout_cruise
    if cashout_capitalize is None:
        cashout_capitalize = cashout_cruise
    if rng is None:
        rng = random.Random()

    base_bet = bank / divider
    current_mult = 1.0   # IOL multiplier
    profit = 0.0
    trail_active = False
    peak_profit = 0.0
    busted = False

    for _ in range(max_hands):
        bal = bank + profit

        # Bust check
        if bal <= 0:
            busted = True
            break

        # Stop profit check (not mid-IOL)
        if profit >= bank * stop_pct / 100.0 and current_mult <= 1.0 + 1e-9:
            break

        # Stop loss check
        if profit < -bank * sl_pct / 100.0:
            break

        # Trailing stop check
        if trail_active:
            lock_floor = peak_profit * trail_lock_pct / 100.0
            if profit < lock_floor:
                break

        # Trail activation
        if not trail_active and profit >= bank * trail_act_pct / 100.0:
            trail_active = True
            peak_profit = profit

        if trail_active and profit > peak_profit:
            peak_profit = profit

        # Determine mode
        recovery_threshold = bank * recovery_threshold_pct / 100.0
        if trail_active:
            mode = 'CAPITALIZE'
        elif profit < -recovery_threshold or current_mult > recovery_iol_thresh:
            mode = 'RECOVERY'
        else:
            mode = 'CRUISE'

        # Select cashout target
        if mode == 'CAPITALIZE':
            target = cashout_capitalize
        elif mode == 'RECOVERY':
            target = cashout_recovery
        else:
            target = cashout_cruise

        # Calculate bet size
        bet = base_bet * current_mult

        # Soft bust protection: if next bet > 95% of balance, reset IOL
        if bet > bal * 0.95:
            current_mult = 1.0
            bet = base_bet

        # Trail-aware bet cap: don't let a loss breach the trail lock floor
        if trail_active:
            lock_floor = peak_profit * trail_lock_pct / 100.0
            max_loss_allowed = profit - lock_floor
            if max_loss_allowed < bet:
                # Cap the bet to what we can afford to lose without breaching floor
                bet = max(base_bet, max_loss_allowed)
                bet = min(bet, bal * 0.95)

        bet = max(bet, base_bet * 0.01)  # safety floor

        # Simulate the hand
        won, multiplier = sim_hand(rng, skip_set, target)

        if won:
            # Profit = bet * (multiplier - 1)
            hand_profit = bet * (multiplier - 1.0)
            profit += hand_profit
            current_mult = 1.0  # reset IOL on win
        else:
            # Lost the bet
            profit -= bet
            current_mult *= iol  # escalate IOL

    return (profit, busted)


def sim_batch(num, bank=100, divider=100, iol=2.0, skip_set=None,
              cashout_cruise=1.5, cashout_recovery=2.5, cashout_capitalize=1.2,
              trail_act_pct=8, trail_lock_pct=60,
              stop_pct=15, sl_pct=15, seed_base=42, **kwargs):
    """
    Run N sessions, return stats dict.
    """
    if skip_set is None:
        skip_set = frozenset({5, 6, 7, 8, 9})

    profits = []
    busts = 0

    for i in range(num):
        rng = random.Random(seed_base * 100000 + i)
        profit, busted = sim_session(
            bank=bank, divider=divider, iol=iol,
            skip_set=skip_set,
            cashout_cruise=cashout_cruise,
            cashout_recovery=cashout_recovery,
            cashout_capitalize=cashout_capitalize,
            trail_act_pct=trail_act_pct,
            trail_lock_pct=trail_lock_pct,
            stop_pct=stop_pct, sl_pct=sl_pct,
            rng=rng,
            **kwargs
        )
        profits.append(profit)
        if busted:
            busts += 1

    profits.sort()
    n = len(profits)
    median = statistics.median(profits)
    mean = sum(profits) / n
    bust_pct = 100.0 * busts / n
    win_pct = 100.0 * sum(1 for p in profits if p > 0) / n
    p5 = profits[int(n * 0.05)]
    p10 = profits[int(n * 0.10)]
    p90 = profits[int(n * 0.90)]

    return {
        'median': median,
        'mean': mean,
        'bust_pct': bust_pct,
        'win_pct': win_pct,
        'p5': p5,
        'p10': p10,
        'p90': p90,
    }


# ============================================================
# MAMBA BASELINE (dice 65%, IOL 3.0x)
# ============================================================

def sim_mamba(bank=100, num=5000, divider=100,
              trail_act_pct=8, trail_lock_pct=60,
              stop_pct=15, sl_pct=15, seed_base=42):
    """
    MAMBA dice baseline: 65% chance, IOL 3.0x, same trail/stop logic.
    Dice: win prob=65%, net payout=(99/65 - 1)=0.5231x
    """
    win_prob = 0.65
    win_payout = 99.0 / 65.0 - 1.0  # ~0.5231

    iol = 3.0
    base_bet = bank / divider

    profits = []
    busts = 0

    for i in range(num):
        rng = random.Random(seed_base * 100000 + i)
        profit = 0.0
        current_mult = 1.0
        trail_active = False
        peak_profit = 0.0
        busted = False

        for _ in range(5000):
            bal = bank + profit
            if bal <= 0:
                busted = True
                break

            if profit >= bank * stop_pct / 100.0 and current_mult <= 1.0 + 1e-9:
                break

            if profit < -bank * sl_pct / 100.0:
                break

            if trail_active:
                lock_floor = peak_profit * trail_lock_pct / 100.0
                if profit < lock_floor:
                    break

            if not trail_active and profit >= bank * trail_act_pct / 100.0:
                trail_active = True
                peak_profit = profit

            if trail_active and profit > peak_profit:
                peak_profit = profit

            bet = base_bet * current_mult
            if bet > bal * 0.95:
                current_mult = 1.0
                bet = base_bet

            if trail_active:
                lock_floor = peak_profit * trail_lock_pct / 100.0
                max_loss_allowed = profit - lock_floor
                if max_loss_allowed < bet:
                    bet = max(base_bet, max_loss_allowed)
                    bet = min(bet, bal * 0.95)

            bet = max(bet, base_bet * 0.01)

            won = rng.random() < win_prob
            if won:
                profit += bet * win_payout
                current_mult = 1.0
            else:
                profit -= bet
                current_mult *= iol

        profits.append(profit)
        if busted:
            busts += 1

    profits.sort()
    n = len(profits)
    return {
        'median': statistics.median(profits),
        'mean': sum(profits) / n,
        'bust_pct': 100.0 * busts / n,
        'win_pct': 100.0 * sum(1 for p in profits if p > 0) / n,
        'p5': profits[int(n * 0.05)],
        'p10': profits[int(n * 0.10)],
        'p90': profits[int(n * 0.90)],
    }


# ============================================================
# SANITY CHECK
# ============================================================

def sanity_check():
    """
    Verify core mechanics before running sweep.
    Returns True if all checks pass.
    """
    print("Running sanity checks...")
    rng = random.Random(1337)
    passed = True

    # Check 1: hilo_payout math
    p, m = hilo_payout(1, True)   # Ace, bet high: 12/13 prob, 0.99*13/12 payout
    expected_prob = 12/13
    expected_mult = 0.99 * 13/12
    if abs(p - expected_prob) > 1e-9 or abs(m - expected_mult) > 1e-9:
        print(f"  FAIL hilo_payout(1, True): got ({p:.4f}, {m:.4f}), expected ({expected_prob:.4f}, {expected_mult:.4f})")
        passed = False
    else:
        print(f"  OK   hilo_payout(1,HIGH): prob={p:.4f} mult={m:.4f}")

    p2, m2 = hilo_payout(13, False)  # King, bet low: 12/13 prob, same payout
    if abs(p2 - 12/13) > 1e-9:
        print(f"  FAIL hilo_payout(13, False): prob={p2:.4f}")
        passed = False
    else:
        print(f"  OK   hilo_payout(13,LOW):  prob={p2:.4f} mult={m2:.4f}")

    # Check 2: impossible bets return 0
    p3, m3 = hilo_payout(13, True)  # King can't go higher
    if p3 != 0.0:
        print(f"  FAIL hilo_payout(13, True) should be 0 prob, got {p3}")
        passed = False
    else:
        print(f"  OK   hilo_payout(13,HIGH) edge: prob=0 (correct)")

    # Check 3: hand win rate with skip={5-9} at cashout=1.5x
    wins = 0
    N = 10000
    for i in range(N):
        rng2 = random.Random(i)
        won, _ = sim_hand(rng2, frozenset({5,6,7,8,9}), 1.5)
        if won:
            wins += 1
    win_rate = 100.0 * wins / N
    print(f"  Hand win rate (skip 5-9, cashout=1.5x): {win_rate:.1f}% (expect 60-70%)")
    if not (55 <= win_rate <= 75):
        print(f"  WARN hand win rate {win_rate:.1f}% outside expected 55-75% range")
        # Not a hard failure, just warn

    # Check 4: session produces reasonable results
    r = sim_batch(500, bank=100, divider=100, iol=2.0,
                  skip_set=frozenset({5,6,7,8,9}),
                  cashout_cruise=1.5, cashout_recovery=2.5, cashout_capitalize=1.2)
    print(f"  Session check (500 runs): median=${r['median']:+.2f} bust={r['bust_pct']:.1f}% win={r['win_pct']:.1f}%")
    if r['bust_pct'] > 30:
        print(f"  WARN bust rate {r['bust_pct']:.1f}% seems high")

    print(f"  Sanity {'PASSED' if passed else 'FAILED'}")
    print()
    return passed


# ============================================================
# PRINT FORMATTER
# ============================================================

def pr(tag, r):
    print(f"  {tag:<55} ${r['median']:>+7.2f} ${r['mean']:>+7.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+7.2f} ${r['p90']:>+7.2f}")


def print_header():
    print(f"  {'Config':<55} {'Median':>8} {'Mean':>8} {'Bust':>6} {'Win':>6} {'P10':>8} {'P90':>8}")
    print("  " + "-" * 105)


# ============================================================
# SKIP SET HELPERS
# ============================================================

SKIP_CONFIGS = {
    '{5-9}':  frozenset({5, 6, 7, 8, 9}),
    '{4-10}': frozenset({4, 5, 6, 7, 8, 9, 10}),
    '{6-8}':  frozenset({6, 7, 8}),
    '{}':     frozenset(),
}


# ============================================================
# MAIN — PARAMETER SWEEP
# ============================================================

if __name__ == '__main__':
    quick = '--quick' in sys.argv
    NUM = 2000 if quick else 5000
    BANK = 100
    DIVIDER = 100
    TRAIL_ACT = 8
    TRAIL_LOCK = 60
    STOP = 15
    SL = 15

    print("=" * 110)
    print(f"  SIDEWINDER HiLo Optimizer  |  bank=${BANK}  sessions={NUM}  trail={TRAIL_ACT}/{TRAIL_LOCK}  stop={STOP}%  sl={SL}%")
    print("=" * 110)
    print()

    # Run sanity checks first
    ok = sanity_check()
    if not ok:
        print("Sanity checks failed — review logic before trusting sweep results.")
        print()

    # --------------------------------------------------------
    # PHASE 1: Single-mode sweep (all cashouts the same)
    # --------------------------------------------------------
    print("=" * 110)
    print("  PHASE 1 — Single-Mode Sweep: skip × IOL × cashout")
    print("=" * 110)
    print()

    IOL_VALUES    = [1.5, 2.0, 2.5, 3.0]
    CASHOUT_VALUES = [1.2, 1.5, 2.0, 2.5, 3.0]

    results_p1 = []
    t0 = time.time()
    total_p1 = len(SKIP_CONFIGS) * len(IOL_VALUES) * len(CASHOUT_VALUES)
    done = 0

    for skip_name, skip_set in SKIP_CONFIGS.items():
        for iol in IOL_VALUES:
            for co in CASHOUT_VALUES:
                r = sim_batch(NUM, bank=BANK, divider=DIVIDER, iol=iol,
                              skip_set=skip_set,
                              cashout_cruise=co, cashout_recovery=co, cashout_capitalize=co,
                              trail_act_pct=TRAIL_ACT, trail_lock_pct=TRAIL_LOCK,
                              stop_pct=STOP, sl_pct=SL)
                tag = f"skip={skip_name} iol={iol:.1f}x cashout={co:.1f}x"
                results_p1.append((tag, r, skip_name, iol, co))
                done += 1
                if done % 10 == 0:
                    elapsed = time.time() - t0
                    eta = elapsed / done * (total_p1 - done)
                    print(f"  Phase 1: {done}/{total_p1}  elapsed={elapsed:.0f}s  eta={eta:.0f}s", end='\r')

    print(" " * 80, end='\r')
    elapsed_p1 = time.time() - t0
    print(f"  Phase 1 complete in {elapsed_p1:.1f}s")
    print()

    results_p1.sort(key=lambda x: x[1]['median'], reverse=True)
    print("  Top 20 by median profit:")
    print_header()
    for tag, r, *_ in results_p1[:20]:
        pr(tag, r)
    print()

    # Determine best skip+IOL combo from Phase 1
    best_skip_name, best_iol = results_p1[0][2], results_p1[0][3]
    best_skip_set = SKIP_CONFIGS[best_skip_name]
    print(f"  Best skip={best_skip_name}  IOL={best_iol:.1f}x  (used for Phase 2)")
    print()

    # --------------------------------------------------------
    # PHASE 2: Multi-mode sweep
    # --------------------------------------------------------
    print("=" * 110)
    print(f"  PHASE 2 — Multi-Mode Sweep: cruise × recovery × capitalize  (skip={best_skip_name} iol={best_iol:.1f}x)")
    print("=" * 110)
    print()

    CRUISE_VALUES     = [1.2, 1.5, 2.0]
    RECOVERY_VALUES   = [2.0, 2.5, 3.0, 4.0]
    CAPITALIZE_VALUES = [1.1, 1.2, 1.5]

    results_p2 = []
    t1 = time.time()
    total_p2 = sum(1 for cr in CRUISE_VALUES for rec in RECOVERY_VALUES
                   for cap in CAPITALIZE_VALUES if rec > cr)
    done2 = 0

    for cr in CRUISE_VALUES:
        for rec in RECOVERY_VALUES:
            if rec <= cr:
                continue  # recovery must be > cruise
            for cap in CAPITALIZE_VALUES:
                r = sim_batch(NUM, bank=BANK, divider=DIVIDER, iol=best_iol,
                              skip_set=best_skip_set,
                              cashout_cruise=cr, cashout_recovery=rec, cashout_capitalize=cap,
                              trail_act_pct=TRAIL_ACT, trail_lock_pct=TRAIL_LOCK,
                              stop_pct=STOP, sl_pct=SL)
                tag = f"cruise={cr:.1f}x rec={rec:.1f}x cap={cap:.1f}x"
                results_p2.append((tag, r))
                done2 += 1
                if done2 % 5 == 0:
                    elapsed = time.time() - t1
                    eta = elapsed / done2 * (total_p2 - done2)
                    print(f"  Phase 2: {done2}/{total_p2}  elapsed={elapsed:.0f}s  eta={eta:.0f}s", end='\r')

    print(" " * 80, end='\r')
    elapsed_p2 = time.time() - t1
    print(f"  Phase 2 complete in {elapsed_p2:.1f}s")
    print()

    results_p2.sort(key=lambda x: x[1]['median'], reverse=True)
    print("  Top 15 by median profit:")
    print_header()
    for tag, r in results_p2[:15]:
        pr(f"skip={best_skip_name} iol={best_iol:.1f}x {tag}", r)
    print()

    best_p2_tag, best_p2_r = results_p2[0]

    # --------------------------------------------------------
    # PHASE 3: Head-to-head vs MAMBA
    # --------------------------------------------------------
    print("=" * 110)
    print("  PHASE 3 — Head-to-Head: MAMBA vs Best SIDEWINDER Configs")
    print("=" * 110)
    print()

    print(f"  Running MAMBA baseline ({NUM} sessions)...")
    mamba_r = sim_mamba(bank=BANK, num=NUM, divider=DIVIDER,
                        trail_act_pct=TRAIL_ACT, trail_lock_pct=TRAIL_LOCK,
                        stop_pct=STOP, sl_pct=SL)

    print_header()
    pr("MAMBA (dice 65% IOL=3.0x)", mamba_r)
    print()

    # Best single-mode config
    best_p1_tag, best_p1_r, best_p1_skip, best_p1_iol, best_p1_co = results_p1[0]
    pr(f"SIDEWINDER P1-best: {best_p1_tag}", best_p1_r)

    # Best multi-mode config
    pr(f"SIDEWINDER P2-best: skip={best_skip_name} iol={best_iol:.1f}x {best_p2_tag}", best_p2_r)

    # Top 3 from Phase 1
    print()
    print("  Top 5 SIDEWINDER Phase 1 configs:")
    print_header()
    for tag, r, *_ in results_p1[:5]:
        pr(f"  {tag}", r)

    print()
    print("  Top 5 SIDEWINDER Phase 2 configs:")
    print_header()
    for tag, r in results_p2[:5]:
        pr(f"  skip={best_skip_name} iol={best_iol:.1f}x {tag}", r)

    print()
    print("=" * 110)
    print(f"  SUMMARY")
    print("=" * 110)
    print(f"  MAMBA median:              ${mamba_r['median']:>+7.2f}  bust={mamba_r['bust_pct']:.1f}%  win={mamba_r['win_pct']:.1f}%")
    print(f"  SIDEWINDER P1-best median: ${best_p1_r['median']:>+7.2f}  bust={best_p1_r['bust_pct']:.1f}%  win={best_p1_r['win_pct']:.1f}%")
    print(f"  SIDEWINDER P2-best median: ${best_p2_r['median']:>+7.2f}  bust={best_p2_r['bust_pct']:.1f}%  win={best_p2_r['win_pct']:.1f}%")
    delta_p1 = best_p1_r['median'] - mamba_r['median']
    delta_p2 = best_p2_r['median'] - mamba_r['median']
    print(f"  P1 vs MAMBA: {delta_p1:>+.2f}  |  P2 vs MAMBA: {delta_p2:>+.2f}")

    if best_p2_r['median'] > mamba_r['median']:
        print(f"  SIDEWINDER BEATS MAMBA by ${delta_p2:>+.2f} (multi-mode)")
    elif best_p1_r['median'] > mamba_r['median']:
        print(f"  SIDEWINDER BEATS MAMBA by ${delta_p1:>+.2f} (single-mode)")
    else:
        print(f"  MAMBA holds the lead — SIDEWINDER did not beat MAMBA at bank=${BANK}")
    print()
    total_time = time.time() - t0
    print(f"  Total runtime: {total_time:.1f}s")
    print("=" * 110)
