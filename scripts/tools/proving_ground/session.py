"""PROVING GROUND — Unified session loop.

Replaces 22 copy-pasted simulation loops with a single configurable runner.
Mirrors the battle-tested logic from mamba-trail-v2.py and sidewinder-optimizer.py.
"""

import random as _random


def run_session(
    strategy,
    engine,
    bank=100,
    divider=10000,
    seed=42,
    seed_offset=0,
    max_hands=5000,
    stop_pct=15,
    sl_pct=15,
    trail_act=8,
    trail_lock=60,
    rng=None,
):
    """Run one betting session and return (profit, busted).

    Args:
        strategy:    Strategy instance (MambaStrategy, SidewinderStrategy, etc.)
        engine:      Engine instance (DiceEngine, HiLoEngine, etc.)
        bank:        Starting bankroll
        divider:     Base bet divisor — base = max(bank/divider, 0.00101)
        seed:        RNG seed base
        seed_offset: Per-session offset (use loop index for reproducibility)
        max_hands:   Maximum hands before forced exit
        stop_pct:    Stop profit threshold as % of bank (0 = disabled)
        sl_pct:      Stop loss threshold as % of bank (0 = disabled)
        trail_act:   Trail activates at this % profit above bank (0 = disabled)
        trail_lock:  Trail fires when profit <= peak * trail_lock% (0 = disabled)
        rng:         Optional pre-seeded random.Random instance (overrides seed)

    Returns:
        (profit: float, busted: bool)
    """
    # --- RNG setup ---
    if rng is None:
        rng = _random.Random(seed * 100000 + seed_offset)

    # --- Base bet ---
    base = max(bank / divider, 0.00101)

    # --- State init ---
    state = strategy.initial_state()
    iol_mult = 1.0
    profit = 0.0
    peak = 0.0
    trail_active = False
    busted = False

    # --- Threshold precompute ---
    stop_thresh = bank * stop_pct / 100.0 if stop_pct > 0 else None
    sl_thresh = bank * sl_pct / 100.0 if sl_pct > 0 else None
    act_thresh = bank * trail_act / 100.0 if trail_act > 0 else None

    for _ in range(max_hands):
        bal = bank + profit

        # Hard bust
        if bal <= 0:
            busted = True
            break

        # Stop loss
        if sl_thresh is not None and profit < -sl_thresh:
            break

        # Trailing stop check (fires immediately, no multiplier gate)
        if trail_active:
            floor = peak * trail_lock / 100.0
            if profit <= floor:
                break

        # Trail activation and peak update
        if act_thresh is not None and not trail_active and profit >= act_thresh:
            trail_active = True
            peak = profit
        if trail_active and profit > peak:
            peak = profit

        # Stop profit (gated: only exit when not mid-IOL)
        if stop_thresh is not None and profit >= stop_thresh and iol_mult <= 1.01:
            break

        # --- Bet sizing ---
        bet = base * iol_mult

        # Soft bust: next bet exceeds 95% of balance — reset IOL
        if bet > bal * 0.95:
            iol_mult = 1.0
            bet = base

        # Hard floor: bet can't exceed balance
        if bet > bal:
            bet = bal

        # Trail-aware bet cap: don't let a loss breach the lock floor
        if trail_active:
            floor = peak * trail_lock / 100.0
            max_loss_allowed = profit - floor
            if max_loss_allowed < bet:
                bet = max(base, max_loss_allowed)
                bet = min(bet, bal * 0.95)

        # Safety floor
        if bet < 0.001:
            busted = True
            break

        # --- HiLo mode override: session runner forces capitalize when trail active ---
        if trail_active and hasattr(strategy, "get_hand_config"):
            state = dict(state)
            state["mode"] = "capitalize"

        # --- Engine configuration (for HiLo) ---
        if hasattr(strategy, "get_hand_config"):
            hand_config = strategy.get_hand_config(state)
            if hasattr(engine, "configure") and hand_config:
                engine.configure(hand_config)

        # --- Resolve hand ---
        won, net_mult = engine.resolve(rng)

        # --- Update profit ---
        if won:
            profit += bet * net_mult
        else:
            profit += bet * net_mult  # net_mult = -1.0 on loss, so profit -= bet

        # --- After-result bust check ---
        if bank + profit <= 0:
            busted = True
            break

        # --- Strategy update ---
        iol_mult, state = strategy.on_result(won, net_mult, profit, bank, state)

        # Soft bust check on new multiplier (prevent next iteration overshoot)
        next_bet = base * iol_mult
        next_bal = bank + profit
        if next_bal > 0 and next_bet > next_bal * 0.95:
            iol_mult = 1.0

    return (profit, busted)
