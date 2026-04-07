"""PROVING GROUND — Pillar 3: Provably Fair Replay.

Replays strategies against real Shuffle seed pairs using the verified
HMAC-SHA256 provably fair algorithm instead of RNG.

Algorithm (verified against Shuffle's verification page):
    float = HMAC-SHA256(server_seed, "client_seed:nonce:0")
            -> first 4 bytes big-endian uint32 / 2^32

Game mappings:
    dice:     floor(float * 10001) / 100
    roulette: floor(float * 37)         -> 0-36
    hilo:     floor(float * 13) + 1     -> 1-13
"""

import hmac
import hashlib
import json
import os
import random as _random


# ---------------------------------------------------------------------------
# Core hash function
# ---------------------------------------------------------------------------

def shuffle_float(server_seed, client_seed, nonce):
    """Compute Shuffle provably fair float for one bet.

    Args:
        server_seed: hex string (revealed server seed)
        client_seed: string (client seed)
        nonce:       int (bet nonce, 0-based)

    Returns:
        float in [0, 1)
    """
    message = client_seed + ":" + str(nonce) + ":0"
    h = hmac.new(
        server_seed.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    )
    digest = h.digest()
    # First 4 bytes, big-endian uint32
    uint32 = (
        (digest[0] << 24) |
        (digest[1] << 16) |
        (digest[2] << 8)  |
        digest[3]
    )
    return uint32 / (2 ** 32)


# ---------------------------------------------------------------------------
# Game converters
# ---------------------------------------------------------------------------

def float_to_dice(f):
    """Shuffle dice result: floor(f * 10001) / 100 -> 0.00 to 100.00."""
    return int(f * 10001) / 100.0


def float_to_roulette(f):
    """Shuffle roulette result: floor(f * 37) -> 0-36."""
    return int(f * 37)


def float_to_hilo_card(f):
    """Shuffle HiLo card: floor(f * 13) + 1 -> 1-13."""
    return int(f * 13) + 1


# ---------------------------------------------------------------------------
# Outcome generation
# ---------------------------------------------------------------------------

def generate_outcomes(server_seed, client_seed, nonce_count, game="dice"):
    """Generate a list of game outcomes for all nonces in a seed pair.

    Args:
        server_seed:  hex string
        client_seed:  string
        nonce_count:  int — number of bets in this seed pair
        game:         "dice", "roulette", or "hilo"

    Returns:
        list of converted outcomes (floats for dice/roulette, ints for hilo)
    """
    converter = {
        "dice": float_to_dice,
        "roulette": float_to_roulette,
        "hilo": float_to_hilo_card,
    }.get(game)

    if converter is None:
        raise ValueError("Unknown game: " + game + ". Use dice, roulette, or hilo.")

    outcomes = []
    for nonce in range(nonce_count):
        f = shuffle_float(server_seed, client_seed, nonce)
        outcomes.append(converter(f))
    return outcomes


# ---------------------------------------------------------------------------
# Seed loading
# ---------------------------------------------------------------------------

def load_seeds(path=None):
    """Load seed pairs from seeds.json.

    Args:
        path: absolute path to seeds.json. Defaults to same directory as this file.

    Returns:
        list of dicts with keys: client, server, nonces
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds.json")
    with open(path, "r") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Session replay (mirrors session.py's run_session)
# ---------------------------------------------------------------------------

def _replay_session(
    strategy,
    engine,
    floats,
    bank=100,
    divider=10000,
    max_hands=5000,
    stop_pct=15,
    sl_pct=15,
    trail_act=8,
    trail_lock=60,
    game="dice",
):
    """Replay one session against a list of provably fair floats.

    Mirrors run_session() from session.py but consumes floats from a list
    instead of using an RNG.

    For dice/roulette: engine.resolve_from_float(floats[idx]) per hand.
    For hilo:          random.Random(int(f * 2**32)) seeded per hand,
                       engine.resolve(rng).

    Args:
        strategy:   Strategy instance
        engine:     Engine instance with resolve_from_float (dice/roulette)
                    or resolve(rng) (hilo)
        floats:     list of floats from generate_outcomes() (raw floats,
                    NOT converted — conversion happens here for hilo)
        bank:       starting bankroll
        divider:    base bet divisor
        max_hands:  max bets before forced exit
        stop_pct:   profit stop as % of bank (0=disabled)
        sl_pct:     stop loss as % of bank (0=disabled)
        trail_act:  trail activation at % profit (0=disabled)
        trail_lock: trail fires when profit <= peak * trail_lock% (0=disabled)
        game:       "dice", "roulette", or "hilo"

    Returns:
        (profit: float, busted: bool)
    """
    base = max(bank / divider, 0.00101)

    state = strategy.initial_state()
    iol_mult = 1.0
    profit = 0.0
    peak = 0.0
    trail_active = False
    busted = False

    stop_thresh = bank * stop_pct / 100.0 if stop_pct > 0 else None
    sl_thresh = bank * sl_pct / 100.0 if sl_pct > 0 else None
    act_thresh = bank * trail_act / 100.0 if trail_act > 0 else None

    n_floats = len(floats)

    for idx in range(min(max_hands, n_floats)):
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

        # Trail-aware bet cap
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

        # HiLo mode override: capitalize when trail active
        if trail_active and hasattr(strategy, "get_hand_config"):
            state = dict(state)
            state["mode"] = "capitalize"

        # Engine configuration (for HiLo)
        if hasattr(strategy, "get_hand_config"):
            hand_config = strategy.get_hand_config(state)
            if hasattr(engine, "configure") and hand_config:
                engine.configure(hand_config)

        # --- Resolve hand from provably fair float ---
        f = floats[idx]
        if game == "hilo":
            # Seed a per-hand RNG from the float for multi-draw HiLo chains
            hand_rng = _random.Random(int(f * (2 ** 32)))
            won, net_mult = engine.resolve(hand_rng)
        else:
            won, net_mult = engine.resolve_from_float(f)

        # --- Update profit ---
        if won:
            profit += bet * net_mult
        else:
            profit += bet * net_mult  # net_mult = -1.0 on loss

        # After-result bust check
        if bank + profit <= 0:
            busted = True
            break

        # Strategy update
        iol_mult, state = strategy.on_result(won, net_mult, profit, bank, state)

        # Soft bust check on new multiplier
        next_bet = base * iol_mult
        next_bal = bank + profit
        if next_bal > 0 and next_bet > next_bal * 0.95:
            iol_mult = 1.0

    return (profit, busted)


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

def run_pf(strategy, engine, params, seeds_path=None, game="dice"):
    """Run provably fair replay across all seed pairs.

    For each seed pair in seeds.json:
      1. Generate raw floats for all nonces
      2. Replay strategy/engine against those floats
      3. Collect (profit, busted) results

    Args:
        strategy:    Strategy instance
        engine:      Engine instance
        params:      dict — session params passed to _replay_session.
                     Supported keys: bank, divider, max_hands, stop_pct,
                     sl_pct, trail_act, trail_lock
        seeds_path:  path to seeds.json (None = default)
        game:        "dice", "roulette", or "hilo"

    Returns:
        dict with keys:
            results:   list of (profit, busted) per seed pair
            stats:     compute_stats output (if monte_carlo available)
                       or a minimal fallback dict
    """
    seeds = load_seeds(seeds_path)

    results = []
    for seed_pair in seeds:
        # Generate raw floats (not converted) for replay
        raw_floats = []
        for nonce in range(seed_pair["nonces"]):
            raw_floats.append(
                shuffle_float(seed_pair["server"], seed_pair["client"], nonce)
            )

        session_params = {
            "bank": params.get("bank", 100),
            "divider": params.get("divider", 10000),
            "max_hands": params.get("max_hands", 5000),
            "stop_pct": params.get("stop_pct", 15),
            "sl_pct": params.get("sl_pct", 15),
            "trail_act": params.get("trail_act", 8),
            "trail_lock": params.get("trail_lock", 60),
            "game": game,
        }

        profit, busted = _replay_session(
            strategy, engine, raw_floats, **session_params
        )
        results.append((profit, busted))

    # Compute stats — use monte_carlo.compute_stats if available
    try:
        from proving_ground.monte_carlo import compute_stats
        stats = compute_stats(results)
    except ImportError:
        profits = [r[0] for r in results]
        n = len(profits)
        busted_count = sum(1 for r in results if r[1])
        stats = {
            "n": n,
            "median": sorted(profits)[n // 2] if n else 0.0,
            "bust_rate": busted_count / n if n else 0.0,
            "min": min(profits) if profits else 0.0,
            "max": max(profits) if profits else 0.0,
        }

    stats["seed_pairs"] = len(seeds)
    stats["total_nonces"] = sum(sp.get("nonces", 0) for sp in seeds)
    return stats
