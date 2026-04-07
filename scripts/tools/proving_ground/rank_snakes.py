#!/usr/bin/env python3
"""PROVING GROUND — Snake Family Profitability Ranking.

All 6 strategies ranked by Monte Carlo (5k sessions) + Provably Fair replay
using Shuffle's verified HMAC-SHA256 algorithm where possible.

PF replay available: MAMBA (dice), COBRA (roulette), TAIPAN (roulette), SIDEWINDER (hilo)
MC only:             BASILISK (baccarat), VIPER (blackjack)
"""
import random, time, json, os, sys
from multiprocessing import Pool, cpu_count

# PF imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proving_ground.provably_fair import shuffle_float, load_seeds

NUM = 5000; SEED = 42; MAX_HANDS = 15000; BANK = 100

# === Game constants ===
RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
DOZ2 = set(range(13,25)); DOZ3 = set(range(25,37))
COBRA_NUMS = RED | {2, 4, 6, 8, 10}  # 18 red + 5 extra black = 23


# ============================================================
# Common session mechanics (trail, stops, soft bust)
# ============================================================

def _check_stops(profit, peak, bank, trail_active, trail_lock, act_t, stop_t, sl_t):
    """Returns (should_stop, trail_active, peak)."""
    # Trail activation
    if not trail_active and act_t > 0 and profit >= act_t:
        trail_active = True
        peak = profit
    if trail_active and profit > peak:
        peak = profit
    # Trail fire
    if trail_active:
        floor = peak * trail_lock / 100
        if profit <= floor:
            return (True, trail_active, peak)
    # Stop loss
    if sl_t > 0 and profit <= -sl_t:
        return (True, trail_active, peak)
    return (False, trail_active, peak)


# ============================================================
# 1. MAMBA — Dice 65% IOL 3.0x
# ============================================================

def _mamba_mc(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 8 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < 0.65:
            profit += bet * (99.0/65 - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


def _mamba_pf(args):
    floats, bank = args
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * 15 / 100; sl_t = bank * 15 / 100; act_t = bank * 8 / 100
    for f in floats:
        if hands >= MAX_HANDS: break
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        dice_result = int(f * 10001) / 100.0
        if dice_result < 65:
            profit += bet * (99.0/65 - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# 2. COBRA — Roulette 23-number IOL 3.0x
# ============================================================

def _cobra_mc(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 8 / 100
    net_win = 36.0 / 23 - 1  # +0.565x
    win_prob = 23.0 / 37
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < win_prob:
            profit += bet * net_win; mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


def _cobra_pf(args):
    floats, bank = args
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * 15 / 100; sl_t = bank * 15 / 100; act_t = bank * 8 / 100
    net_win = 36.0 / 23 - 1
    for f in floats:
        if hands >= MAX_HANDS: break
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        n = int(f * 37)
        if n in COBRA_NUMS:
            profit += bet * net_win; mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# 3. TAIPAN v2.0 — Roulette Adaptive + Delayed IOL + Bet Cap
# ============================================================

def _taipan_payout(n, ls, expand_at=5):
    """Net payout for roulette number n given current loss streak."""
    if ls >= expand_at:
        # EXPAND mode: two dozens (DOZ2 + DOZ3 = 24 numbers)
        if n in DOZ2 or n in DOZ3: return 0.5  # 36/24 - 1
        return -1.0
    # CRUISE/RECOVERY: 40% dozen2 / 60% red (default cruise split)
    df, ef = 0.4, 0.6
    net = 0.0
    if n in DOZ2: net += df * 2.0   # dozen pays 2:1 on that portion
    else: net -= df
    if n in RED: net += ef * 1.0      # even-money pays 1:1
    else: net -= ef
    return net


def _taipan_mc(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    consec = 0; ls = 0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 8 / 100
    iol = 5.0; delay = 3; cap_pct = 15
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        # Bet cap
        if cap_pct > 0:
            max_a = bal * cap_pct / 100
            if bet > max_a: bet = max_a
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        n = rng.randint(0, 36)
        p = _taipan_payout(n, ls)
        if p > 0:
            profit += bet * p; mult = 1.0; ls = 0; consec = 0
        else:
            profit += bet * p
            ls += 1; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


def _taipan_pf(args):
    floats, bank = args
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    consec = 0; ls = 0
    stop_t = bank * 15 / 100; sl_t = bank * 15 / 100; act_t = bank * 8 / 100
    iol = 5.0; delay = 3; cap_pct = 15
    for f in floats:
        if hands >= MAX_HANDS: break
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if cap_pct > 0:
            max_a = bal * cap_pct / 100
            if bet > max_a: bet = max_a
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        n = int(f * 37)  # PF roulette conversion
        p = _taipan_payout(n, ls)
        if p > 0:
            profit += bet * p; mult = 1.0; ls = 0; consec = 0
        else:
            profit += bet * p
            ls += 1; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# 4. SIDEWINDER — HiLo Adaptive Chain IOL 3.0x
# ============================================================

def _sidewinder_mc(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 8 / 100
    skip = {6, 7, 8}
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        # Mode: capitalize when trail active, recovery when in deficit, else cruise
        if ta:
            co_target = 1.1
        elif profit < -bank * 5 / 100 or mult > 1.5:
            co_target = 2.5
        else:
            co_target = 1.5
        # Simulate HiLo hand (chain predictions until cashout or miss)
        card = rng.randint(1, 13)
        acc = 1.0; won = False
        for _ in range(52):
            if card in skip:
                card = rng.randint(1, 13); continue
            bet_high = card <= 7
            if bet_high:
                winning = 13 - card
            else:
                winning = card - 1
            if winning <= 0:
                card = rng.randint(1, 13); continue
            prob = winning / 13.0
            gross = 0.99 * 13.0 / winning
            nxt = rng.randint(1, 13)
            correct = (nxt > card) if bet_high else (nxt < card)
            if not correct:
                break  # lost
            acc *= gross
            card = nxt
            if acc >= co_target:
                won = True; break
        if won:
            profit += bet * (acc - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


def _sidewinder_pf(args):
    floats, bank = args
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * 15 / 100; sl_t = bank * 15 / 100; act_t = bank * 8 / 100
    skip = {6, 7, 8}
    for f in floats:
        if hands >= MAX_HANDS: break
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if ta:
            co_target = 1.1
        elif profit < -bank * 5 / 100 or mult > 1.5:
            co_target = 2.5
        else:
            co_target = 1.5
        # Seed per-hand RNG from PF float (same approach as provably_fair.py)
        hand_rng = random.Random(int(f * (2 ** 32)))
        card = hand_rng.randint(1, 13)
        acc = 1.0; won = False
        for _ in range(52):
            if card in skip:
                card = hand_rng.randint(1, 13); continue
            bet_high = card <= 7
            winning = (13 - card) if bet_high else (card - 1)
            if winning <= 0:
                card = hand_rng.randint(1, 13); continue
            gross = 0.99 * 13.0 / winning
            nxt = hand_rng.randint(1, 13)
            correct = (nxt > card) if bet_high else (nxt < card)
            if not correct: break
            acc *= gross; card = nxt
            if acc >= co_target: won = True; break
        if won:
            profit += bet * (acc - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# 5. BASILISK — Baccarat Delayed IOL 2.1x (MC only)
# ============================================================
# Baccarat probabilities: Banker 45.86%, Player 44.62%, Tie 9.52%
# Banker pays 0.95x (5% commission), Player pays 1.0x, Tie = push

def _basilisk_mc(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 1000, 0.00101)  # div=1000
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    consec = 0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 8 / 100
    iol = 2.1; delay = 3
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base; consec = 0
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        r = rng.random()
        if r < 0.4586:
            # Banker wins — we win (0.95x due to commission)
            profit += bet * 0.95; mult = 1.0; consec = 0
        elif r < 0.4586 + 0.4462:
            # Player wins — we lose
            profit -= bet; consec += 1
            if consec >= delay:
                mult *= iol
                if bank+profit > 0 and base*mult > (bank+profit)*0.95: mult = 1.0; consec = 0
        else:
            pass  # Tie — push, no change to consec or mult
        if bank+profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# 6. VIPER — Blackjack Strike/Coil/Capitalize (MC only)
# ============================================================
# Calibrated BJ model with conditional probabilities per hand type.
# Doubles/splits have higher win rates (you only do them on favorable spots).
# Calibrated to -0.52% house edge (6-deck, S17, basic strategy).
#
#   Type      | Freq   | Win%  | Loss% | Push% | Bet mult | Sub-EV
#   Blackjack | 4.75%  | 100%  |  0%   |  0%   | 1.5x     | +0.07125
#   Double    | 9.50%  | 56%   | 36%   |  8%   | 2.0x     | +0.03800
#   Split     | 2.50%  | 48%   | 44%   |  8%   | 2.1x     | +0.00210
#   Normal    | 83.25% | 38.7% | 52.7% | 8.6%  | 1.0x     | -0.11655
#   TOTAL EV  = -0.0052 per unit = -0.52%
#
# Strike: Mart 2x. Coil: flat at brake level. Capitalize: Paroli 2x.

def _viper_mc(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    unit = max(bank / 6000, 0.001)  # div=6000
    bet = unit; profit = 0.0; peak = 0.0; ta = False; hands = 0
    mode = 0  # 0=strike, 1=coil, 2=capitalize
    ls = 0; ws = 0; cap_count = 0
    coil_deficit = 0.0; coil_bet = 0.0
    brake_at = 10; cap_streak = 2; cap_max = 2
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 8 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        if bet > bal * 0.95:
            bet = unit; mode = 0; ls = 0
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(unit, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        # Resolve hand — calibrated conditional probabilities
        hand_type = rng.random()
        r = rng.random()
        if hand_type < 0.0475:
            # Blackjack (4.75%) — auto-win 1.5x
            pnl = bet * 1.5
        elif hand_type < 0.0475 + 0.095:
            # Double (9.5%) — 2x bet, favorable spots: 56W/36L/8P
            actual_bet = bet * 2
            if r < 0.56: pnl = actual_bet
            elif r < 0.56 + 0.36: pnl = -actual_bet
            else: pnl = 0
        elif hand_type < 0.0475 + 0.095 + 0.025:
            # Split (2.5%) — ~2.1x avg bet, 48W/44L/8P
            actual_bet = bet * 2.1
            if r < 0.48: pnl = actual_bet
            elif r < 0.48 + 0.44: pnl = -actual_bet
            else: pnl = 0
        else:
            # Normal (83.25%) — 1x bet, 38.7W/52.7L/8.6P
            if r < 0.387: pnl = bet
            elif r < 0.387 + 0.527: pnl = -bet
            else: pnl = 0
        profit += pnl
        # Determine outcome type for mode logic
        is_win = pnl > 0
        is_push = pnl == 0
        is_loss = pnl < 0
        if is_win:
            ws += 1; ls = 0
        elif is_loss:
            ls += 1; ws = 0
        # else push: streaks unchanged
        if profit > peak: peak = profit
        # Mode transitions
        if mode == 0:  # STRIKE
            if is_win:
                bet = unit
                if ws >= cap_streak:
                    mode = 2; cap_count = 0  # -> capitalize
            elif is_loss:
                if brake_at > 0 and ls >= brake_at:
                    coil_bet = bet; coil_deficit = 0; mode = 1  # -> coil
                else:
                    bet = bet * 2
        elif mode == 1:  # COIL
            coil_deficit += pnl
            if is_win and coil_deficit >= 0:
                mode = 0; bet = unit  # recovered
                if ws >= cap_streak:
                    mode = 2; cap_count = 0
            # Stay in coil at same bet
        elif mode == 2:  # CAPITALIZE
            cap_count += 1
            if is_loss or cap_count >= cap_max:
                mode = 0; bet = unit; ws = 0
            elif is_win:
                bet = bet * 2
        if bet < unit: bet = unit
        # Trail-aware cap
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(unit, mt)
        # Stops
        if bank+profit <= 0: return (profit, True, hands)
        if not ta and act_t > 0 and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and (mode == 0 and ls == 0): return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# Stats + formatting
# ============================================================

def stats(results):
    pnls = sorted([r[0] for r in results])
    busts = sum(1 for r in results if r[1])
    avg_h = sum(r[2] for r in results) / len(results) if results else 0
    n = len(pnls)
    if n == 0: return {'median': 0, 'mean': 0, 'bust_pct': 0, 'win_pct': 0, 'p10': 0, 'p90': 0, 'avg_hands': 0}
    return {
        'median': pnls[n//2], 'mean': sum(pnls)/n, 'bust_pct': busts/n*100,
        'win_pct': sum(1 for p in pnls if p > 0)/n*100,
        'p5': pnls[n//20], 'p10': pnls[n//10], 'p90': pnls[9*n//10],
        'avg_hands': avg_h,
    }

def pr(tag, r, bank):
    ra = r['median'] / abs(r['p10']) if r['p10'] != 0 and r['median'] > 0 else -1
    print("  {:<45} ${:>+7.2f} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} {:>6.3f} {:>5.0f}".format(
        tag, r['median'], r['mean'], r['bust_pct'], r['win_pct'], r['p10'], r['p90'], ra, r['avg_hands']))

H = "  {:<45} {:>8} {:>8} {:>6} {:>6} {:>8} {:>8} {:>6} {:>5}".format(
    'Strategy', 'Median', 'Mean', 'Bust%', 'Win%', 'P10', 'P90', 'RA', 'Hands')
S = "  {} {} {} {} {} {} {} {} {}".format('-'*45, '-'*8, '-'*8, '-'*6, '-'*6, '-'*8, '-'*8, '-'*6, '-'*5)


# ============================================================
# PF replay helper
# ============================================================

def run_pf_sessions(pf_func, seeds, bank):
    """Run PF replay across seed pairs, return stats dict."""
    results = []
    for sp in seeds:
        floats = []
        for nonce in range(sp["nonces"]):
            floats.append(shuffle_float(sp["server"], sp["client"], nonce))
        r = pf_func((floats, bank))
        results.append(r)
    return results


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    bank = BANK
    seeds = load_seeds()

    strats = [
        ("MAMBA      dice 65% IOL=3.0x", _mamba_mc),
        ("COBRA      roulette 23num IOL=3.0x", _cobra_mc),
        ("TAIPAN v2  roulette adaptive IOL=5.0x d=3 c=15%", _taipan_mc),
        ("SIDEWINDER hilo skip={6-8} IOL=3.0x", _sidewinder_mc),
        ("BASILISK   baccarat banker IOL=2.1x d=3", _basilisk_mc),
        ("VIPER v3   blackjack strike/coil/cap b=10", _viper_mc),
    ]

    strats_pf = [
        ("MAMBA      dice (PF)", _mamba_pf),
        ("COBRA      roulette (PF)", _cobra_pf),
        ("TAIPAN v2  roulette (PF)", _taipan_pf),
        ("SIDEWINDER hilo (PF)", _sidewinder_pf),
    ]

    print()
    print("=" * 130)
    print("  SNAKE FAMILY PROFITABILITY RANKING")
    print("  Monte Carlo: {} sessions | Provably Fair: {} seed pairs ({} nonces)".format(
        NUM, len(seeds), sum(s["nonces"] for s in seeds)))
    print("  ${} bank | trail=8/60 | 15k max hands".format(bank))
    print("=" * 130)

    # ================================================================
    # RUN 1: Trail only (no SL, no fixed stop) — shows natural bust rates
    # ================================================================
    print()
    print("  " + "~" * 90)
    print("  RUN 1: TRAIL ONLY (no stop loss, no profit stop) — natural bust rates")
    print("  " + "~" * 90)
    print(H); print(S)

    raw_results = []
    for label, func in strats:
        args = [(s, bank, 0, 0) for s in range(NUM)]  # sl=0, stop=0
        r = stats(pool.map(func, args))
        r['tag'] = label
        raw_results.append(r)
        pr(label, r, bank)

    # ================================================================
    # RUN 2: Full safety (trail + SL 15% + stop 15%)
    # ================================================================
    print()
    print("  " + "~" * 90)
    print("  RUN 2: FULL SAFETY (trail 8/60 + SL 15% + stop 15%)")
    print("  " + "~" * 90)
    print(H); print(S)

    safe_results = []
    for label, func in strats:
        args = [(s, bank, 15, 15) for s in range(NUM)]  # sl=15%, stop=15%
        r = stats(pool.map(func, args))
        r['tag'] = label
        safe_results.append(r)
        pr(label, r, bank)

    # ================================================================
    # Provably Fair Replay (trail only — max signal)
    # ================================================================
    print()
    print("  " + "~" * 90)
    print("  PROVABLY FAIR REPLAY ({} seed pairs, Shuffle HMAC-SHA256, trail only)".format(len(seeds)))
    print("  NOTE: {} sessions total. Validates MC against real Shuffle RNG.".format(len(seeds)))
    print("  " + "~" * 90)
    print(H); print(S)

    for label, func in strats_pf:
        results = run_pf_sessions(func, seeds, bank)
        r = stats(results)
        pr(label, r, bank)

    # ================================================================
    # Grand Rankings (using trail-only results for honest bust rates)
    # ================================================================
    print()
    print("=" * 130)
    print("  GRAND RANKING — by median profit (trail only, {} MC sessions)".format(NUM))
    print("=" * 130)
    print(H); print(S)
    raw_results.sort(key=lambda x: x['median'], reverse=True)
    for i, r in enumerate(raw_results):
        pr("#{:<2} {}".format(i+1, r['tag']), r, bank)

    print()
    print("=" * 130)
    print("  RISK-ADJUSTED — median / |P10| (higher = more profit per unit risk)")
    print("=" * 130)
    print(H); print(S)
    for r in raw_results:
        r['ra'] = r['median'] / abs(r['p10']) if r['p10'] != 0 and r['median'] > 0 else -1
    raw_results.sort(key=lambda x: x['ra'], reverse=True)
    for i, r in enumerate(raw_results):
        pr("#{:<2} {}".format(i+1, r['tag']), r, bank)

    print()
    print("=" * 130)
    print("  SAFETY RANKING — by bust% then P10")
    print("=" * 130)
    print(H); print(S)
    raw_results.sort(key=lambda x: (x['bust_pct'], -x['p10']))
    for i, r in enumerate(raw_results):
        pr("#{:<2} {}".format(i+1, r['tag']), r, bank)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 130)
