"""PROVING GROUND — Pillar 2: Exact Markov chain analysis.

Models a binary-outcome betting strategy as an absorbing Markov chain and
solves for exact ruin/target absorption probabilities via value iteration.

Supported engines: DiceEngine, RouletteEngine (fixed win_prob and net_payout).
Not supported: HiLoEngine (multi-round, variable outcome per hand).
"""


def run_markov(strategy, engine, params):
    """Exact Markov chain analysis for binary-outcome games.

    Args:
        strategy: Strategy instance (must have .iol attribute for IOL level).
                  FlatStrategy (iol=1.0), MambaStrategy, IOLStrategy, etc.
        engine:   Engine instance with .win_prob and .net_payout attributes.
                  Must be DiceEngine or RouletteEngine (not HiLoEngine).
        params:   Dict with keys:
                    bank      - starting bankroll (e.g. 100)
                    divider   - base bet divisor (e.g. 10000)
                    stop_pct  - profit target as % of bank (e.g. 15)
                    sl_pct    - stop loss as % of bank (e.g. 15)

    Returns:
        Dict with keys:
            supported    - True (or False with error key if unsupported)
            ruin_prob    - float, probability of ruin in % (0-100)
            target_prob  - float, probability of hitting target in % (0-100)
            iterations   - int, value-iteration steps to converge
            states       - int, total transient states in the chain
            max_iol_level - int, highest IOL level modelled
            profit_units - int, profit range modelled (stop_units + sl_units)
    """
    # --- Guard: reject multi-round engines ---
    if engine.name == "hilo":
        return {
            "supported": False,
            "error": "Markov not supported for multi-round games (HiLo)",
        }

    # --- Guard: engine must expose net_payout ---
    if not hasattr(engine, "net_payout"):
        return {
            "supported": False,
            "error": "Engine missing net_payout attribute",
        }

    # --- Params ---
    bank = float(params["bank"])
    divider = float(params["divider"])
    stop_pct = float(params["stop_pct"])
    sl_pct = float(params["sl_pct"])

    base = max(bank / divider, 0.00101)
    win_prob = engine.win_prob
    loss_prob = 1.0 - win_prob
    net_payout = engine.net_payout  # net profit factor on win (e.g. 0.5231)

    # --- IOL multiplier ---
    # FlatStrategy has no .iol attribute; treat as 1.0
    iol = getattr(strategy, "iol", 1.0)

    # --- Profit units ---
    # Express all profit in base-bet increments (1 unit = 1 base bet)
    # Rounded to integers for discrete state space.
    stop_units = int(round(bank * stop_pct / 100.0 / base))
    sl_units = int(round(bank * sl_pct / 100.0 / base))

    # Guard against degenerate parameters
    if stop_units < 1:
        stop_units = 1
    if sl_units < 1:
        sl_units = 1

    # --- Max IOL level ---
    # level L is valid when base * iol^L <= bank * 0.95
    # i.e. iol^L <= bank * 0.95 / base
    # level L+1 would trigger soft bust
    max_budget = bank * 0.95 / base
    max_level = 0
    if iol > 1.0:
        level = 0
        while True:
            bet_mult = iol ** (level + 1)
            if bet_mult > max_budget:
                break
            level += 1
            if level > 50:  # safety cap
                break
        max_level = level
    # For flat (iol=1.0) max_level is always 0

    # --- State encoding ---
    # State = (pu, level) where pu is profit in base-bet units
    # pu range: [-sl_units, +stop_units]  (inclusive endpoints are absorbing)
    # level range: [0, max_level]
    # Transient: pu strictly inside (-sl_units, +stop_units)
    #   AND NOT already absorbed
    # Absorbing: RUIN (pu <= -sl_units) or TARGET (pu >= +stop_units AND level==0)
    #
    # We index transient states only.
    # pu_range: pu values that are NOT yet absorbed
    #   i.e. -sl_units < pu < stop_units  (start is 0, inside range)
    # plus pu==stop_units only if level > 0 (mid-IOL, can't exit yet)
    # Actually: session exits stop only when iol_mult <= 1 (level==0).
    # So absorbing TARGET = pu >= stop_units AND level == 0
    # If pu >= stop_units AND level > 0 → still transient (mid-IOL)

    def is_absorbing(pu, level):
        if pu <= -sl_units:
            return "ruin"
        if pu >= stop_units and level == 0:
            return "target"
        return None

    # Enumerate transient states
    # pu range: from (-sl_units+1) to very large positive (but capped at stop_units + some buffer)
    # When mid-IOL (level > 0), profit can exceed stop_units — clamp at stop_units + sl_units to keep finite
    pu_min = -sl_units + 1
    pu_max = stop_units + sl_units  # generous upper bound for mid-IOL accumulation

    transient_states = []
    state_index = {}
    for pu in range(pu_min, pu_max + 1):
        for lv in range(0, max_level + 1):
            if is_absorbing(pu, lv) is None:
                idx = len(transient_states)
                transient_states.append((pu, lv))
                state_index[(pu, lv)] = idx

    n_states = len(transient_states)

    if n_states == 0:
        return {
            "supported": False,
            "error": "No transient states — check bank/divider/stop_pct/sl_pct parameters",
        }

    # --- Build transition matrix (sparse: list of (to_idx, prob) per state) ---
    # For value iteration we only need the sparse transitions.
    transitions = []         # transitions[i] = list of (j, prob) tuples
    ruin_direct = [0.0] * n_states   # direct prob of absorbing to ruin from state i
    target_direct = [0.0] * n_states  # direct prob of absorbing to target from state i

    for i, (pu, lv) in enumerate(transient_states):
        trans_i = []

        # Current bet size in units = iol^lv (for lv=0 → 1 unit)
        bet_units = iol ** lv if iol > 1.0 else 1.0
        # For flat (iol=1.0), bet_units always = 1.0

        # --- WIN transition ---
        win_profit_delta = bet_units * net_payout   # net profit on win in units
        next_pu_win = pu + int(round(win_profit_delta))
        next_lv_win = 0  # always reset IOL on win

        absorb = is_absorbing(next_pu_win, next_lv_win)
        if absorb == "ruin":
            ruin_direct[i] += win_prob
        elif absorb == "target":
            target_direct[i] += win_prob
        else:
            # Clamp pu to pu_max for states that drift past our upper bound while mid-IOL
            # (at level 0 they'd absorb to target already; here it must be level>0)
            clamped_pu = min(next_pu_win, pu_max)
            dest = (clamped_pu, next_lv_win)
            if dest in state_index:
                trans_i.append((state_index[dest], win_prob))
            else:
                # Out-of-bound — treat as absorbed to nearest boundary
                if clamped_pu >= stop_units:
                    target_direct[i] += win_prob
                else:
                    ruin_direct[i] += win_prob

        # --- LOSS transition ---
        # Bet = iol^lv units lost
        loss_delta = -bet_units  # lose the bet (net_mult = -1.0 on loss)
        next_pu_loss = pu + int(round(loss_delta))

        # Next level: level + 1, unless that triggers soft bust
        next_lv_raw = lv + 1
        next_bet_mult = iol ** next_lv_raw if iol > 1.0 else 1.0
        # Soft bust: if next bet > 95% of remaining balance → reset to level 0
        # In units: next_bet_units > (bank + next_pu_loss*base) * 0.95 / base
        remaining_units = (bank / base) + next_pu_loss
        if next_bet_mult > remaining_units * 0.95 or next_lv_raw > max_level:
            next_lv_loss = 0  # soft bust resets IOL
        else:
            next_lv_loss = next_lv_raw

        absorb = is_absorbing(next_pu_loss, next_lv_loss)
        if absorb == "ruin":
            ruin_direct[i] += loss_prob
        elif absorb == "target":
            target_direct[i] += loss_prob
        else:
            clamped_pu = max(next_pu_loss, pu_min)
            clamped_pu = min(clamped_pu, pu_max)
            dest = (clamped_pu, next_lv_loss)
            if dest in state_index:
                trans_i.append((state_index[dest], loss_prob))
            else:
                if clamped_pu <= -sl_units:
                    ruin_direct[i] += loss_prob
                else:
                    ruin_direct[i] += loss_prob  # safe default

        transitions.append(trans_i)

    # --- Value iteration solver ---
    # ruin_prob[i]   = P(reach ruin | start at state i)
    # target_prob[i] = P(reach target | start at state i)
    #
    # ruin_prob[i]   = ruin_direct[i]   + sum_j P(i→j) * ruin_prob[j]
    # target_prob[i] = target_direct[i] + sum_j P(i→j) * target_prob[j]

    ruin_v = [rd for rd in ruin_direct]
    target_v = [td for td in target_direct]

    max_iter = 50000
    tol = 1e-8
    iterations = 0

    for it in range(max_iter):
        max_delta = 0.0
        new_ruin = [0.0] * n_states
        new_target = [0.0] * n_states

        for i in range(n_states):
            r = ruin_direct[i]
            t = target_direct[i]
            for j, prob in transitions[i]:
                r += prob * ruin_v[j]
                t += prob * target_v[j]
            new_ruin[i] = r
            new_target[i] = t
            delta = abs(new_ruin[i] - ruin_v[i]) + abs(new_target[i] - target_v[i])
            if delta > max_delta:
                max_delta = delta

        ruin_v = new_ruin
        target_v = new_target
        iterations = it + 1

        if max_delta < tol:
            break

    # --- Initial state = (0, 0): zero profit, level 0 ---
    start = (0, 0)
    if start in state_index:
        i0 = state_index[start]
        ruin_pct = ruin_v[i0] * 100.0
        target_pct = target_v[i0] * 100.0
    else:
        # Start is absorbing (shouldn't happen with sane params)
        absorb = is_absorbing(0, 0)
        ruin_pct = 100.0 if absorb == "ruin" else 0.0
        target_pct = 100.0 if absorb == "target" else 0.0

    return {
        "supported": True,
        "ruin_prob": ruin_pct,
        "target_prob": target_pct,
        "iterations": iterations,
        "states": n_states,
        "max_iol_level": max_level,
        "profit_units": stop_units + sl_units,
    }
