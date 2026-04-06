#!/usr/bin/env python3
"""
Snake Family Comparison — MAMBA vs COBRA vs VIPER with Trailing Stop
Unified Monte Carlo across all three strategies with identical methodology.

Tests: IOL + trailing stop + stop-loss on dice/roulette/blackjack.

Usage:
  python3 snake-family-comparison.py          # Full (5k sessions)
  python3 snake-family-comparison.py --quick  # Quick (2k sessions)
"""

import random
import sys

# ============================================================
# GAME MODELS
# ============================================================

# MAMBA — Dice 65%
DICE_WIN_PROB = 0.65
DICE_WIN_PAYOUT = 99.0 / 65 - 1  # +0.523x

# COBRA — Roulette 23/37 pure numbers
COBRA_COVERED = 23
COBRA_WIN_PROB = COBRA_COVERED / 37.0  # 62.2%
COBRA_WIN_PAYOUT = 36.0 / COBRA_COVERED - 1  # +0.565x

# VIPER — Blackjack (11-category model, 0.495% edge)
BJ_OUTCOMES = [
    (0.0475, +1.5, "blackjack"),
    (0.3318, +1.0, "win"),
    (0.4292, -1.0, "loss"),
    (0.0848,  0.0, "push"),
    (0.0532, +2.0, "double_win"),
    (0.0418, -2.0, "double_loss"),
    (0.0048, +2.0, "split_win"),
    (0.0056, -2.0, "split_loss"),
    (0.0005,  0.0, "split_push"),
    (0.0004, +4.0, "splitdbl_win"),
    (0.0004, -4.0, "splitdbl_loss"),
]
BJ_CUM = []
_c = 0
for p, _, _ in BJ_OUTCOMES:
    _c += p
    BJ_CUM.append(_c)


def bj_outcome():
    r = random.random()
    for i, cp in enumerate(BJ_CUM):
        if r < cp:
            return BJ_OUTCOMES[i][1], BJ_OUTCOMES[i][2]
    return BJ_OUTCOMES[-1][1], BJ_OUTCOMES[-1][2]


# ============================================================
# UNIFIED SIMULATOR
# ============================================================

def sim(game, iol, divider, bank, num, max_bets, seed,
        stop_pct=15, stop_loss_pct=0,
        trail_act=8, trail_lock=60,
        brake_at=0, cap_streak=0, cap_max=0, cap_mult=1.0):
    """
    Unified sim for dice/roulette/blackjack.
    game: 'dice', 'roulette', 'blackjack'
    """
    pnls = []
    busts = 0
    trail_exits = 0
    target_exits = 0
    stoploss_exits = 0
    total_bets = 0

    for s in range(num):
        random.seed(seed * 100000 + s)

        base = bank / divider
        mult = 1.0
        profit = 0.0
        peak = 0.0
        bets = 0
        ws = 0
        ls = 0
        trail_active = False
        mode = 'strike'
        cap_count = 0
        is_braking = False

        stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
        sl_thresh = bank * stop_loss_pct / 100 if stop_loss_pct > 0 else 0
        act_thresh = bank * trail_act / 100 if trail_act > 0 else 0
        session_over = False

        for _ in range(max_bets):
            if session_over:
                break

            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            # Determine bet size
            if mode == 'cap':
                bet = base * cap_mult
            elif is_braking:
                bet = base * mult  # hold at brake level
            else:
                bet = base * mult

            # Trail-aware bet cap
            if trail_active and trail_act > 0:
                floor = peak * trail_lock / 100
                max_trail_bet = profit - floor
                if max_trail_bet > 0 and bet > max_trail_bet:
                    bet = max_trail_bet

            # Soft bust
            if bet > bal * 0.95:
                mult = 1.0
                bet = base
                is_braking = False
            if bet > bal:
                bet = bal
            if bet < 0.001:
                busts += 1
                break

            bets += 1

            # === GAME-SPECIFIC OUTCOME ===
            if game == 'dice':
                won = random.random() < DICE_WIN_PROB
                if won:
                    profit += bet * DICE_WIN_PAYOUT
                else:
                    profit -= bet
                is_push = False
                payout_mult = DICE_WIN_PAYOUT if won else -1.0

            elif game == 'roulette':
                n = random.randint(0, 36)
                won = n < COBRA_COVERED
                if won:
                    profit += bet * COBRA_WIN_PAYOUT
                else:
                    profit -= bet
                is_push = False
                payout_mult = COBRA_WIN_PAYOUT if won else -1.0

            elif game == 'blackjack':
                payout_mult, label = bj_outcome()
                won = payout_mult > 0
                is_push = payout_mult == 0
                profit += bet * payout_mult

            # Bust check
            if bank + profit <= 0:
                busts += 1
                break

            # Win/loss tracking
            if is_push:
                pass
            elif won:
                ws += 1
                ls = 0
            else:
                ws = 0
                ls += 1

            # Peak tracking
            if profit > peak:
                peak = profit

            # === STRATEGY LOGIC ===
            if is_push:
                pass  # no change on push
            elif mode == 'strike':
                if won:
                    mult = 1.0
                    is_braking = False
                    # Check capitalize trigger
                    if cap_streak > 0 and ws >= cap_streak:
                        mode = 'cap'
                        cap_count = 0
                else:
                    if is_braking:
                        pass  # stay flat during brake
                    elif brake_at > 0 and ls >= brake_at:
                        is_braking = True
                    else:
                        mult *= iol

                    # Soft bust check on next bet
                    nb = base * mult
                    if bank + profit > 0 and nb > (bank + profit) * 0.95:
                        mult = 1.0
                        is_braking = False

            elif mode == 'cap':
                cap_count += 1
                if not won or cap_count >= cap_max:
                    mode = 'strike'
                    ws = 0
                    mult = 1.0 if won else iol
                    is_braking = False

            # === TRAILING STOP ===
            if trail_act > 0:
                if not trail_active and profit >= act_thresh:
                    trail_active = True
                if trail_active:
                    floor = peak * trail_lock / 100
                    if profit <= floor:
                        trail_exits += 1
                        session_over = True
                        continue

            # === FIXED STOP ===
            if stop_thresh > 0 and profit >= stop_thresh and mult <= 1.01 and not is_braking:
                target_exits += 1
                session_over = True
                continue

            # === STOP LOSS ===
            if sl_thresh > 0 and profit <= -sl_thresh:
                stoploss_exits += 1
                session_over = True
                continue

        total_bets += bets
        pnls.append(profit)

    pnls.sort()
    n = len(pnls)
    return {
        'median': pnls[n // 2],
        'mean': sum(pnls) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n * 100,
        'p10': pnls[n // 10],
        'p90': pnls[9 * n // 10],
        'avg_bets': total_bets / n,
        'trail_exits': trail_exits,
        'target_exits': target_exits,
        'sl_exits': stoploss_exits,
    }


def pr(tag, r, bl=None):
    m = " **" if bl is not None and r['median'] > bl else (" *" if r['median'] > 0 else "")
    t = r['avg_bets'] / 10 / 60  # assume 10/s for dice, adjust display
    te = r.get('trail_exits', 0)
    tg = r.get('target_exits', 0)
    sl = r.get('sl_exits', 0)
    exits = f"T{te:>4} S{tg:>4} L{sl:>4}"
    print(f"  {tag:<52} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} {exits}{m}")


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42

    H = (f"  {'Config':<52} {'Med':>9} {'Mean':>9} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} {'Trail/Stop/SL':>14}")
    S = (f"  {'─'*52} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*9} {'─'*9} {'─'*14}")

    print()
    print("=" * 130)
    print("  SNAKE FAMILY COMPARISON — MAMBA vs COBRA vs VIPER")
    print(f"  {num:,} sessions | ${bank:,} | Trailing Stop + Stop Loss")
    print("=" * 130)

    # ============================================================
    # SECTION 1: BASELINES (no trailing stop)
    # ============================================================
    print("\n  === BASELINES (no trailing stop, stop=15%) ===")
    print(H); print(S)

    configs = [
        ("MAMBA dice IOL3.0x div=10k", 'dice', 3.0, 10000, 0, 0, 0, 0, 0, 1.0),
        ("MAMBA dice IOL3.0x div=8k", 'dice', 3.0, 8000, 0, 0, 0, 0, 0, 1.0),
        ("COBRA roulette IOL3.0x div=10k", 'roulette', 3.0, 10000, 0, 0, 0, 0, 0, 1.0),
        ("COBRA roulette IOL3.0x div=8k", 'roulette', 3.0, 8000, 0, 0, 0, 0, 0, 1.0),
        ("VIPER bj Mart2x div=6k", 'blackjack', 2.0, 6000, 0, 0, 0, 0, 0, 1.0),
        ("VIPER bj Mart2x div=6k brake@10", 'blackjack', 2.0, 6000, 10, 0, 0, 0, 0, 1.0),
        ("VIPER bj Mart2x div=6k brake@10 cap2/2", 'blackjack', 2.0, 6000, 10, 0, 2, 2, 2.0, 1.0),
    ]

    for tag, game, iol, div, brake, _, cs, cm, cmult, _ in configs:
        r = sim(game, iol, div, bank, num, 10000, seed,
                stop_pct=15, trail_act=0, trail_lock=0,
                brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
        pr(tag, r)

    # ============================================================
    # SECTION 2: WITH TRAILING STOP (act=8%, lock=60%)
    # ============================================================
    print("\n  === WITH TRAILING STOP (act=8%, lock=60%, stop=15%) ===")
    print(H); print(S)

    for tag, game, iol, div, brake, _, cs, cm, cmult, _ in configs:
        r = sim(game, iol, div, bank, num, 10000, seed,
                stop_pct=15, trail_act=8, trail_lock=60,
                brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
        pr(tag + " +trail", r)

    # ============================================================
    # SECTION 3: WITH TRAILING STOP + STOP LOSS
    # ============================================================
    print("\n  === WITH TRAILING STOP + STOP LOSS 15% ===")
    print(H); print(S)

    for tag, game, iol, div, brake, _, cs, cm, cmult, _ in configs:
        r = sim(game, iol, div, bank, num, 10000, seed,
                stop_pct=15, stop_loss_pct=15,
                trail_act=8, trail_lock=60,
                brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
        pr(tag + " +trail+SL", r)

    # ============================================================
    # SECTION 4: TRAIL PARAMETER SWEEP PER GAME
    # ============================================================
    for game, tag_base, iol, div, brake, cs, cm, cmult in [
        ('dice', 'MAMBA', 3.0, 10000, 0, 0, 0, 1.0),
        ('roulette', 'COBRA', 3.0, 10000, 0, 0, 0, 1.0),
        ('blackjack', 'VIPER', 2.0, 6000, 10, 2, 2, 2.0),
    ]:
        print(f"\n  === {tag_base} TRAIL SWEEP (stop=15%) ===")
        print(H); print(S)

        # Baseline
        r_bl = sim(game, iol, div, bank, num, 10000, seed,
                   stop_pct=15, trail_act=0, trail_lock=0,
                   brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
        pr(f"{tag_base} baseline (no trail)", r_bl)
        bl = r_bl['median']

        for act in [3, 5, 8, 10]:
            for lock in [40, 50, 60, 70, 80]:
                tag = f"{tag_base} act={act}% lock={lock}%"
                r = sim(game, iol, div, bank, num, 10000, seed,
                        stop_pct=15, trail_act=act, trail_lock=lock,
                        brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
                pr(tag, r, bl)
            print()

    # ============================================================
    # SECTION 5: STOP LOSS SWEEP
    # ============================================================
    print(f"\n  === STOP LOSS SWEEP (trail=8/60, stop=15%) ===")
    print(H); print(S)

    for game, tag_base, iol, div, brake, cs, cm, cmult in [
        ('dice', 'MAMBA', 3.0, 10000, 0, 0, 0, 1.0),
        ('roulette', 'COBRA', 3.0, 10000, 0, 0, 0, 1.0),
        ('blackjack', 'VIPER', 2.0, 6000, 10, 2, 2, 2.0),
    ]:
        for sl in [0, 10, 15, 20, 30, 50]:
            tag = f"{tag_base} SL={sl}%"
            r = sim(game, iol, div, bank, num, 10000, seed,
                    stop_pct=15, stop_loss_pct=sl,
                    trail_act=8, trail_lock=60,
                    brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
            pr(tag, r)
        print()

    # ============================================================
    # SECTION 6: FINAL HEAD-TO-HEAD (best config per game)
    # ============================================================
    print("\n  === FINAL HEAD-TO-HEAD ===")
    print(H); print(S)

    # Best configs per game — test at multiple stop levels
    for stop in [8, 10, 15, 20]:
        print(f"\n  Stop = {stop}%:")
        print(H); print(S)

        # MAMBA: trail 8/60 + SL 15%
        r = sim('dice', 3.0, 10000, bank, num, 10000, seed,
                stop_pct=stop, stop_loss_pct=15, trail_act=8, trail_lock=60)
        pr("MAMBA (dice 65% IOL3.0x)", r)

        # COBRA: trail 8/60 + SL 15%
        r = sim('roulette', 3.0, 10000, bank, num, 10000, seed,
                stop_pct=stop, stop_loss_pct=15, trail_act=8, trail_lock=60)
        pr("COBRA (roulette 23/37 IOL3.0x)", r)

        # VIPER: trail 8/60 + SL 15% + brake@10 + cap2/2
        r = sim('blackjack', 2.0, 6000, bank, num, 10000, seed,
                stop_pct=stop, stop_loss_pct=15, trail_act=8, trail_lock=60,
                brake_at=10, cap_streak=2, cap_max=2, cap_mult=2.0)
        pr("VIPER (BJ Mart2x brake@10 cap2/2)", r)

    # ============================================================
    # SUMMARY
    # ============================================================
    print()
    print("=" * 130)
    print("  SUMMARY — Snake Family at stop=15%, trail=8/60, SL=15%")
    print("=" * 130)

    results = {}
    for name, game, iol, div, brake, cs, cm, cmult in [
        ("MAMBA (Dice)", 'dice', 3.0, 10000, 0, 0, 0, 1.0),
        ("COBRA (Roulette)", 'roulette', 3.0, 10000, 0, 0, 0, 1.0),
        ("VIPER (Blackjack)", 'blackjack', 2.0, 6000, 10, 2, 2, 2.0),
    ]:
        r = sim(game, iol, div, bank, num, 10000, seed,
                stop_pct=15, stop_loss_pct=15, trail_act=8, trail_lock=60,
                brake_at=brake, cap_streak=cs, cap_max=cm, cap_mult=cmult)
        results[name] = r
        speed = {'dice': 10, 'roulette': 5, 'blackjack': 2}[game]
        session_min = r['avg_bets'] / speed / 60
        hourly = r['median'] / (session_min / 60) if session_min > 0 else 0

        print(f"\n  {name}:")
        print(f"    Median: ${r['median']:+.2f} | Mean: ${r['mean']:+.2f}")
        print(f"    Bust: {r['bust_pct']:.1f}% | Win: {r['win_pct']:.1f}%")
        print(f"    P10: ${r['p10']:+.2f} | P90: ${r['p90']:+.2f}")
        print(f"    Avg bets: {r['avg_bets']:.0f} | Session: {session_min:.1f} min @ {speed}/s")
        print(f"    $/hour: ${hourly:+.0f}")
        print(f"    Exits: Trail={r['trail_exits']} Target={r['target_exits']} SL={r['sl_exits']}")

    print()
    # Rank
    ranked = sorted(results.items(), key=lambda x: x[1]['median'], reverse=True)
    print("  RANKING BY MEDIAN:")
    for i, (name, r) in enumerate(ranked):
        print(f"    {i+1}. {name}: ${r['median']:+.2f} (bust {r['bust_pct']:.1f}%)")
    print("=" * 130)
