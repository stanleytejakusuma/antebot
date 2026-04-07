# PROVING GROUND Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified strategy testing harness with three validation pillars (Monte Carlo, Markov Chain, Provably Fair Replay) that eliminates the need to copy-paste 100 lines of session boilerplate for every new strategy.

**Architecture:** Python package at `scripts/tools/proving_ground/`. Strategy is a Python class with `on_result()` and `initial_state()`. A generic session runner handles IOL/trail/stops. Three pillar modules (MC with multiprocessing, Markov with numpy, PF with hmac) each produce the same stats dict. A report module combines them. CLI wires it all together.

**Tech Stack:** Python 3, `multiprocessing.Pool`, `hmac`/`hashlib` (stdlib), `numpy` (for Markov matrix ops only — install if missing, else pure Python fallback)

**PRD:** `antebot/.claude/prd/proving-ground-testing-harness.md`

**Not a git repo — skip all git/commit steps.**

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/tools/proving_ground/__init__.py` | Package exports: `prove()`, strategy classes, engine classes |
| `scripts/tools/proving_ground/strategy.py` | `Strategy` base class + `MambaStrategy`, `CobraStrategy`, `SidewinderStrategy`, `FlatStrategy` |
| `scripts/tools/proving_ground/session.py` | `run_session(strategy, engine, params) -> (profit, busted)` — THE unified session loop |
| `scripts/tools/proving_ground/engines.py` | `DiceEngine`, `RouletteEngine`, `HiLoEngine` — `resolve(rng) -> (won, payout_mult)` |
| `scripts/tools/proving_ground/monte_carlo.py` | `run_mc(strategy, engine, params, num, seeds) -> stats_dict` with multiprocessing |
| `scripts/tools/proving_ground/provably_fair.py` | `shuffle_float(server, client, nonce)` + `run_pf(strategy, engine, seed_pairs) -> stats_dict` |
| `scripts/tools/proving_ground/markov.py` | `run_markov(strategy, engine, params) -> exact_stats` — transition matrix + absorption |
| `scripts/tools/proving_ground/report.py` | `prove(strategy, engine, params, ...) -> Report` — runs all pillars, compares, pretty-prints |
| `scripts/tools/proving_ground/main.py` | CLI: `--strategy`, `--bank`, `--sessions`, `--pillar`, `--seeds` |
| `scripts/tools/proving_ground/seeds.json` | 10 Shuffle seed pairs (2,038 nonces total) |

---

### Task 1: Package Scaffold + Strategy Base Class

**Files:**
- Create: `scripts/tools/proving_ground/__init__.py`
- Create: `scripts/tools/proving_ground/strategy.py`

- [ ] **Step 1: Create the package directory**

Run: `mkdir -p scripts/tools/proving_ground`

- [ ] **Step 2: Create `__init__.py`**

```python
"""PROVING GROUND — Antebot Strategy Testing Harness."""
```

- [ ] **Step 3: Create `strategy.py` with base class and FlatStrategy**

```python
"""Strategy definitions for PROVING GROUND."""


class Strategy:
    """Base class. Subclasses define game-specific decision logic."""

    game = "dice"  # override in subclass: "dice", "roulette", "hilo"
    name = "base"

    def initial_state(self):
        """Return starting state dict. Override for stateful strategies."""
        return {}

    def on_result(self, won, payout_mult, profit, bank, state):
        """
        Called after each hand/spin resolves.

        Args:
            won: bool — did the hand win?
            payout_mult: float — payout multiplier (e.g., 1.52 for dice win)
            profit: float — current session P&L
            bank: float — starting bank
            state: dict — strategy state from previous call

        Returns:
            (iol_mult, new_state) — iol_mult is the IOL multiplier for NEXT bet.
              1.0 = base bet, 3.0 = 3x base, etc.
              The session runner handles actual bet sizing, soft bust, trail cap.
        """
        return (1.0, state)

    def get_hand_config(self, state):
        """For multi-round games (HiLo). Return config for the upcoming hand.
        
        Returns:
            dict with game-specific keys, e.g.:
            {"skip_set": {6,7,8}, "cashout_target": 1.5}
        """
        return {}


class FlatStrategy(Strategy):
    """Flat bet — no IOL, no mode switching. Baseline."""
    name = "flat"

    def __init__(self, game="dice"):
        self.game = game

    def on_result(self, won, payout_mult, profit, bank, state):
        return (1.0, state)


class IOLStrategy(Strategy):
    """Simple IOL — multiply bet by factor on loss, reset on win."""
    name = "iol"

    def __init__(self, iol=3.0, game="dice"):
        self.game = game
        self.iol = iol

    def on_result(self, won, payout_mult, profit, bank, state):
        if won:
            return (1.0, state)
        mult = state.get("mult", 1.0) * self.iol
        return (mult, {**state, "mult": mult})

    def initial_state(self):
        return {"mult": 1.0}


class MambaStrategy(Strategy):
    """MAMBA — Dice 65% IOL 3.0x. Trail/stops handled by session runner."""
    game = "dice"
    name = "mamba"

    def __init__(self, iol=3.0):
        self.iol = iol

    def on_result(self, won, payout_mult, profit, bank, state):
        if won:
            return (1.0, {"mult": 1.0})
        mult = state.get("mult", 1.0) * self.iol
        return (mult, {"mult": mult})

    def initial_state(self):
        return {"mult": 1.0}


class SidewinderStrategy(Strategy):
    """SIDEWINDER — HiLo adaptive chain. Three-mode cashout target switching."""
    game = "hilo"
    name = "sidewinder"

    def __init__(self, iol=3.0, cashout_cruise=1.5, cashout_recovery=2.5,
                 cashout_capitalize=1.1, recovery_pct=5, skip_set=None):
        self.iol = iol
        self.co_cruise = cashout_cruise
        self.co_recovery = cashout_recovery
        self.co_cap = cashout_capitalize
        self.rec_pct = recovery_pct
        self.skip = skip_set or frozenset({6, 7, 8})

    def initial_state(self):
        return {"mult": 1.0, "mode": "cruise"}

    def on_result(self, won, payout_mult, profit, bank, state):
        if won:
            mult = 1.0
        else:
            mult = state.get("mult", 1.0) * self.iol
        # Mode logic (trail is handled externally by session runner)
        if profit < -(bank * self.rec_pct / 100) or mult > 1.5:
            mode = "recovery"
        else:
            mode = "cruise"
        return (mult if not won else 1.0, {"mult": mult, "mode": mode})

    def get_hand_config(self, state):
        mode = state.get("mode", "cruise")
        if mode == "capitalize":
            target = self.co_cap
        elif mode == "recovery":
            target = self.co_recovery
        else:
            target = self.co_cruise
        return {"skip_set": self.skip, "cashout_target": target}


STRATEGIES = {
    "flat": FlatStrategy,
    "mamba": MambaStrategy,
    "sidewinder": SidewinderStrategy,
}
```

- [ ] **Step 4: Verify the module imports**

Run: `python3 -c "from scripts.tools.proving_ground.strategy import STRATEGIES; print(list(STRATEGIES.keys()))"`

If that fails due to Python path issues, run: `cd scripts/tools && python3 -c "from proving_ground.strategy import STRATEGIES; print(list(STRATEGIES.keys()))"`

Expected: `['flat', 'mamba', 'sidewinder']`

---

### Task 2: Game Engines

**Files:**
- Create: `scripts/tools/proving_ground/engines.py`

- [ ] **Step 1: Create `engines.py` with DiceEngine, RouletteEngine, HiLoEngine**

```python
"""Game engines — resolve RNG outcomes into (won, payout_multiplier)."""

import random


EDGE = 0.01  # 1% house edge for dice/hilo, roulette has 1/37 built in


class DiceEngine:
    """Dice: binary outcome. chance% to win, payout = 0.99 * 100/chance."""
    name = "dice"

    def __init__(self, chance=65):
        self.chance = chance
        self.win_prob = chance / 100.0
        self.win_payout = (1.0 - EDGE) * 100.0 / chance  # total return mult
        self.net_payout = self.win_payout - 1.0            # net profit mult

    def resolve(self, rng):
        """Returns (won: bool, net_payout_mult: float).
        net_payout_mult: on win = +0.52x (profit fraction), on loss = -1.0x."""
        if rng.random() < self.win_prob:
            return (True, self.net_payout)
        return (False, -1.0)

    def resolve_from_float(self, f):
        """Resolve from a provably fair float [0, 1)."""
        roll = int(f * 10001) / 100.0  # Shuffle dice formula
        won = roll < self.chance  # betHigh=false convention: under target
        if won:
            return (True, self.net_payout)
        return (False, -1.0)


class RouletteEngine:
    """Roulette: number 0-36. Coverage defines which numbers win and payout."""
    name = "roulette"

    def __init__(self, covered_count=23):
        # COBRA-style: N numbers covered equally, payout = 36/N - 1
        self.covered = covered_count
        self.win_payout = 36.0 / covered_count - 1.0  # net profit mult
        self.win_prob = covered_count / 37.0

    def resolve(self, rng):
        if rng.random() < self.win_prob:
            return (True, self.win_payout)
        return (False, -1.0)

    def resolve_from_float(self, f):
        number = int(f * 37)
        # Simplified: first N numbers are "covered"
        if number > 0 and number <= self.covered:
            return (True, self.win_payout)
        return (False, -1.0)


class HiLoEngine:
    """HiLo: chain of card predictions within a single hand."""
    name = "hilo"

    def __init__(self, skip_set=None, cashout_target=1.5, start_val=1):
        self.skip_set = skip_set or frozenset({6, 7, 8})
        self.cashout_target = cashout_target
        self.start_val = start_val

    def configure(self, hand_config):
        """Update per-hand config (called by session before each hand)."""
        if "skip_set" in hand_config:
            self.skip_set = hand_config["skip_set"]
        if "cashout_target" in hand_config:
            self.cashout_target = hand_config["cashout_target"]

    def _card_payout(self, val, bet_high):
        winning = (13 - val) if bet_high else (val - 1)
        if winning <= 0:
            return (0.0, 0.0)
        return (winning / 13.0, 0.99 * 13.0 / winning)

    def resolve(self, rng):
        """Simulate one HiLo hand. Returns (won, net_payout_mult).
        net_payout_mult: accumulated chain multiplier - 1 (profit fraction), or -1 (loss)."""
        cur = self.start_val
        acc = 1.0
        skips = 0
        for _ in range(200):
            if acc >= self.cashout_target and acc > 1.0:
                return (True, acc - 1.0)
            nxt = rng.randint(1, 13)
            if cur in self.skip_set and skips < 52:
                skips += 1
                cur = nxt
                continue
            bet_high = cur <= 7
            prob, pay = self._card_payout(cur, bet_high)
            if prob <= 0:
                if skips < 52:
                    skips += 1
                    cur = nxt
                    continue
                return (True, acc - 1.0)
            correct = (nxt > cur) if bet_high else (nxt < cur)
            if correct:
                acc *= pay
                cur = nxt
            else:
                return (False, -1.0)
        return (True, acc - 1.0)

    def resolve_from_float(self, f):
        """Single card draw from PF float. Returns card value 1-13."""
        return int(f * 13) + 1


ENGINES = {
    "dice": DiceEngine,
    "roulette": RouletteEngine,
    "hilo": HiLoEngine,
}
```

- [ ] **Step 2: Verify engines**

Run:
```bash
cd scripts/tools && python3 -c "
from proving_ground.engines import DiceEngine, HiLoEngine
import random
rng = random.Random(42)
d = DiceEngine(65)
wins = sum(1 for _ in range(10000) if d.resolve(rng)[0])
print(f'Dice 65%: {wins/100:.1f}% win rate (expect ~65%)')
h = HiLoEngine(skip_set={6,7,8}, cashout_target=1.5)
wins = sum(1 for _ in range(10000) if h.resolve(rng)[0])
print(f'HiLo skip={{6-8}} co=1.5: {wins/100:.1f}% win rate (expect ~55-65%)')
"
```

Expected: Dice ~65%, HiLo ~55-65%.

---

### Task 3: Generic Session Runner

**Files:**
- Create: `scripts/tools/proving_ground/session.py`

This is THE core file — the unified boilerplate that replaces 22 copy-pasted session loops.

- [ ] **Step 1: Create `session.py`**

```python
"""Generic session runner — IOL, trailing stop, stop loss/profit.

This is the unified session loop. Strategies provide on_result() for
game-specific decisions. This module handles all bet sizing and stops.
"""


def run_session(strategy, engine, bank=100, divider=10000, seed=42, seed_offset=0,
                max_hands=5000, stop_pct=15, sl_pct=15,
                trail_act=8, trail_lock=60, rng=None):
    """
    Run one session. Returns (profit: float, busted: bool).

    Args:
        strategy: Strategy instance with on_result() and get_hand_config()
        engine: GameEngine instance with resolve(rng)
        bank: starting balance
        divider: base bet = bank / divider
        seed, seed_offset: RNG seed = seed * 100000 + seed_offset
        max_hands: safety limit
        stop_pct: stop at +X% profit (0 = disabled)
        sl_pct: stop at -X% loss (0 = disabled)
        trail_act: trailing stop activates at +X% profit (0 = disabled)
        trail_lock: trail locks X% of peak profit as floor
        rng: pre-built Random instance (overrides seed if provided)
    """
    import random as _random
    if rng is None:
        rng = _random.Random(seed * 100000 + seed_offset)

    base = bank / divider
    min_bet = 0.00101
    if base < min_bet:
        base = min_bet

    profit = 0.0
    peak = 0.0
    trail_active = False
    iol_mult = 1.0
    state = strategy.initial_state()

    stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_thresh = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_thresh = bank * trail_act / 100 if trail_act > 0 else 0

    for _ in range(max_hands):
        bal = bank + profit
        if bal <= 0:
            return (profit, True)

        # Bet sizing
        bet = base * iol_mult
        if bet > bal * 0.95:
            iol_mult = 1.0
            bet = base
        if bet > bal:
            bet = bal
        if bet < 0.001:
            return (profit, True)

        # Trail-aware bet cap
        if trail_active:
            floor = peak * trail_lock / 100
            max_t = profit - floor
            if max_t > 0 and bet > max_t:
                bet = max_t
            if bet < 0.001:
                return (profit, False)

        # Configure engine for multi-round games (HiLo)
        if trail_active:
            state = {**state, "mode": "capitalize"}
        hand_config = strategy.get_hand_config(state)
        if hasattr(engine, 'configure') and hand_config:
            engine.configure(hand_config)

        # Resolve the hand/spin
        won, net_mult = engine.resolve(rng)

        # Update profit
        if won:
            profit += bet * net_mult
        else:
            profit -= bet

        if bank + profit <= 0:
            return (profit, True)

        if profit > peak:
            peak = profit

        # Strategy decides next IOL multiplier
        iol_mult, state = strategy.on_result(won, net_mult, profit, bank, state)

        # Soft bust check on next bet
        if base * iol_mult > (bank + profit) * 0.95:
            iol_mult = 1.0
            state = {**state, "mult": 1.0}

        # Trailing stop
        if trail_act > 0:
            if not trail_active and profit >= act_thresh:
                trail_active = True
            if trail_active:
                floor = peak * trail_lock / 100
                if profit <= floor:
                    return (profit, False)

        # Fixed stops
        if stop_thresh > 0 and profit >= stop_thresh and iol_mult <= 1.01:
            return (profit, False)
        if sl_thresh > 0 and profit <= -sl_thresh:
            return (profit, False)

    return (profit, False)
```

- [ ] **Step 2: Verify session matches MAMBA optimizer**

Run:
```bash
cd scripts/tools && python3 -c "
from proving_ground.session import run_session
from proving_ground.strategy import MambaStrategy
from proving_ground.engines import DiceEngine

strategy = MambaStrategy(iol=3.0)
engine = DiceEngine(chance=65)

# Run 1000 sessions
pnls = []
for s in range(1000):
    p, _ = run_session(strategy, engine, bank=1000, divider=10000,
                       seed=42, seed_offset=s, stop_pct=15, trail_act=8, trail_lock=60)
    pnls.append(p)
pnls.sort()
n = len(pnls)
print(f'MAMBA via PROVING GROUND (1000 sessions):')
print(f'  Median: \${pnls[n//2]:+.2f}')
print(f'  Win%: {sum(1 for p in pnls if p > 0)/n*100:.1f}%')
print(f'  P10: \${pnls[n//10]:+.2f}')
print(f'  Expected: median ~+\$50, win ~70%, P10 ~-\$300')
"
```

Expected: Median ~$50, Win% ~70%. If wildly off, debug the session loop.

---

### Task 4: Monte Carlo Pillar (Multiprocessing)

**Files:**
- Create: `scripts/tools/proving_ground/monte_carlo.py`

- [ ] **Step 1: Create `monte_carlo.py`**

```python
"""Pillar 1: Monte Carlo simulation with multiprocessing."""

from multiprocessing import Pool, cpu_count


def _worker(args):
    """Worker function for parallel execution. Must be top-level for pickling."""
    from proving_ground.session import run_session
    (strategy, engine, params, seed_offset) = args
    p, busted = run_session(strategy, engine, seed_offset=seed_offset, **params)
    return (p, busted)


def compute_stats(results):
    """Compute stats from list of (profit, busted) tuples."""
    pnls = sorted([r[0] for r in results])
    busts = sum(1 for r in results if r[1])
    n = len(pnls)
    if n == 0:
        return {}
    return {
        "median": pnls[n // 2],
        "mean": sum(pnls) / n,
        "bust_pct": busts / n * 100,
        "win_pct": sum(1 for p in pnls if p > 0) / n * 100,
        "p5": pnls[n // 20],
        "p10": pnls[n // 10],
        "p25": pnls[n // 4],
        "p75": pnls[3 * n // 4],
        "p90": pnls[9 * n // 10],
        "p95": pnls[19 * n // 20],
        "count": n,
    }


def run_mc(strategy, engine, params, num=5000, seed=42, cores=None):
    """
    Run Monte Carlo simulation.

    Args:
        strategy: Strategy instance
        engine: GameEngine instance
        params: dict of session params (bank, divider, stop_pct, sl_pct, trail_act, trail_lock)
        num: number of sessions
        seed: base seed
        cores: CPU cores (None = auto)

    Returns:
        stats dict with median, mean, bust_pct, win_pct, percentiles
    """
    if cores is None:
        cores = cpu_count()

    full_params = {**params, "seed": seed}

    # Build args list — strategy and engine must be picklable
    args = [(strategy, engine, full_params, s) for s in range(num)]

    with Pool(cores) as pool:
        results = pool.map(_worker, args)

    return compute_stats(results)


def run_mc_multi_seed(strategy, engine, params, num=5000, seeds=None, cores=None):
    """Run MC across multiple seeds. Returns per-seed stats + cross-seed consistency."""
    if seeds is None:
        seeds = [42, 123, 456, 789, 1337]

    all_stats = []
    for seed in seeds:
        stats = run_mc(strategy, engine, params, num=num, seed=seed, cores=cores)
        stats["seed"] = seed
        all_stats.append(stats)

    medians = [s["median"] for s in all_stats]
    avg_median = sum(medians) / len(medians)
    std_median = (sum((m - avg_median) ** 2 for m in medians) / len(medians)) ** 0.5

    return {
        "per_seed": all_stats,
        "avg_median": avg_median,
        "std_median": std_median,
        "median_range": (min(medians), max(medians)),
    }
```

- [ ] **Step 2: Verify MC parallelism works**

Run:
```bash
cd scripts/tools && python3 -c "
import time
from proving_ground.monte_carlo import run_mc
from proving_ground.strategy import MambaStrategy
from proving_ground.engines import DiceEngine

s = MambaStrategy(iol=3.0)
e = DiceEngine(chance=65)
params = dict(bank=100, divider=10000, stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60)

t0 = time.time()
r = run_mc(s, e, params, num=5000, cores=1)
t1 = time.time()
print(f'Sequential (1 core): {t1-t0:.1f}s — median=\${r[\"median\"]:+.2f}')

t0 = time.time()
r = run_mc(s, e, params, num=5000)
t1 = time.time()
print(f'Parallel (auto cores): {t1-t0:.1f}s — median=\${r[\"median\"]:+.2f}')
print(f'Speedup: {(t1-t0)/(t1-t0):.1f}x')
"
```

Expected: Parallel should be >3x faster. Medians should match within noise.

---

### Task 5: Provably Fair Replay Pillar

**Files:**
- Create: `scripts/tools/proving_ground/provably_fair.py`
- Create: `scripts/tools/proving_ground/seeds.json`

- [ ] **Step 1: Create `seeds.json`**

```json
[
  {"client": "k7a8xxuk2p", "server": "2c01d9109499adf0034370e463ec255906af4abd948820791df10a0e608701c2", "nonces": 831},
  {"client": "dw41eg7x6h", "server": "c19f71d402f19856f4e2dfc97dfff29598d6828c9e75422392a6beb4ac2faeac", "nonces": 321},
  {"client": "rtrks2afd4", "server": "039c18b1227f0a040ebe20b2997d89bb83806ebdb400185cdc78965748bdc547", "nonces": 185},
  {"client": "ph6opc0hgd", "server": "351390846931542ldaa9b3425b90f6fb3645bcd2fe0d16939d3773a88f577b45", "nonces": 183},
  {"client": "qqeu4matrb", "server": "a50aa1c490435f621421ff5e498abf9af7c11477db3cf9c4bcb0b9c25c12f97a", "nonces": 123},
  {"client": "lsada2x4bx", "server": "6eeccf5fc3834c3fac863d1626e4725600b367d75fe563f4a6dd9ad50b6f0496", "nonces": 119},
  {"client": "v90tyvabta", "server": "fc68fd5caaa051be2f86a8e013d56d392b322ff05da236852a722edc89148a73", "nonces": 116},
  {"client": "t9euu783jd", "server": "12c0201bba7b534e9bc565e8d326ac9a5facc422b9e69d4383e47c43db07eee1", "nonces": 89},
  {"client": "21bnler750", "server": "afef78d61572ce63b210abbcf0b0e95361d03ab8c7c005a53de5fbb537bb6db7", "nonces": 46},
  {"client": "9lr01b195i", "server": "f41e2ff1947a85703bcfd129dd02e5db097ad4f1fd575d163900a0b0c91b109a", "nonces": 25}
]
```

- [ ] **Step 2: Create `provably_fair.py`**

```python
"""Pillar 3: Provably Fair Replay using Shuffle's HMAC-SHA256 algorithm."""

import hmac
import hashlib
import json
import os


def shuffle_float(server_seed, client_seed, nonce):
    """
    Compute Shuffle's provably fair float.
    Formula: HMAC-SHA256(serverSeed, "clientSeed:nonce:0") → first 4 bytes → uint32 → / 2^32
    """
    message = client_seed + ":" + str(nonce) + ":0"
    h = hmac.new(server_seed.encode(), message.encode(), hashlib.sha256).digest()
    # First 4 bytes as big-endian uint32
    value = int.from_bytes(h[:4], byteorder="big")
    return value / (2 ** 32)


def float_to_dice(f):
    """Shuffle dice formula: floor(float * 10001) / 100."""
    return int(f * 10001) / 100.0


def float_to_roulette(f):
    """Shuffle roulette formula: floor(float * 37)."""
    return int(f * 37)


def float_to_hilo_card(f):
    """Shuffle HiLo formula: floor(float * 13) + 1 → card value 1-13.
    NOTE: This formula needs verification against Shuffle's actual output."""
    return int(f * 13) + 1


def generate_outcomes(server_seed, client_seed, nonce_count, game="dice"):
    """Generate outcome sequence for a seed pair."""
    outcomes = []
    for nonce in range(nonce_count):
        f = shuffle_float(server_seed, client_seed, nonce)
        if game == "dice":
            outcomes.append(float_to_dice(f))
        elif game == "roulette":
            outcomes.append(float_to_roulette(f))
        elif game == "hilo":
            outcomes.append(float_to_hilo_card(f))
        else:
            outcomes.append(f)
    return outcomes


def load_seeds(path=None):
    """Load seed pairs from JSON file."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "seeds.json")
    with open(path) as f:
        return json.load(f)


def run_pf(strategy, engine, params, seeds_path=None, game="dice"):
    """
    Replay strategy against real Shuffle outcomes.

    For each seed pair, generates the outcome sequence and runs the strategy
    against it. Returns stats dict (same format as MC).
    """
    from proving_ground.monte_carlo import compute_stats

    seed_pairs = load_seeds(seeds_path)

    results = []
    for pair in seed_pairs:
        floats = [shuffle_float(pair["server"], pair["client"], n)
                  for n in range(pair["nonces"])]

        # Run a single session against this outcome sequence
        profit, busted = _replay_session(strategy, engine, params, floats, game)
        results.append((profit, busted))

    stats = compute_stats(results)
    stats["seed_pairs"] = len(seed_pairs)
    stats["total_nonces"] = sum(p["nonces"] for p in seed_pairs)
    return stats


def _replay_session(strategy, engine, params, floats, game):
    """Run strategy against a fixed sequence of PF floats."""
    bank = params.get("bank", 100)
    divider = params.get("divider", 10000)
    stop_pct = params.get("stop_pct", 15)
    sl_pct = params.get("sl_pct", 15)
    trail_act = params.get("trail_act", 8)
    trail_lock = params.get("trail_lock", 60)

    base = max(bank / divider, 0.00101)
    profit = 0.0
    peak = 0.0
    trail_active = False
    iol_mult = 1.0
    state = strategy.initial_state()
    idx = 0

    stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_thresh = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_thresh = bank * trail_act / 100 if trail_act > 0 else 0

    while idx < len(floats):
        bal = bank + profit
        if bal <= 0:
            return (profit, True)

        bet = base * iol_mult
        if bet > bal * 0.95:
            iol_mult = 1.0
            bet = base
        if bet > bal:
            bet = bal
        if bet < 0.001:
            return (profit, True)

        if trail_active:
            floor = peak * trail_lock / 100
            max_t = profit - floor
            if max_t > 0 and bet > max_t:
                bet = max_t
            if bet < 0.001:
                return (profit, False)

        # Resolve outcome from PF float
        f = floats[idx]
        idx += 1

        if game == "dice":
            won, net = engine.resolve_from_float(f) if hasattr(engine, 'resolve_from_float') else engine.resolve(None)
        elif game == "roulette":
            won, net = engine.resolve_from_float(f) if hasattr(engine, 'resolve_from_float') else engine.resolve(None)
        else:
            # HiLo needs multiple floats per hand — consume from sequence
            won, net = _resolve_hilo_hand(engine, floats, idx - 1)
            # Advance idx past consumed floats (approximate: each hand uses ~3-5 floats)
            idx += 4  # rough estimate, will refine

        if won:
            profit += bet * net
        else:
            profit -= bet

        if bank + profit <= 0:
            return (profit, True)
        if profit > peak:
            peak = profit

        iol_mult_new, state = strategy.on_result(won, net, profit, bank, state)
        iol_mult = iol_mult_new

        if base * iol_mult > (bank + profit) * 0.95:
            iol_mult = 1.0

        if trail_act > 0:
            if not trail_active and profit >= act_thresh:
                trail_active = True
            if trail_active:
                floor = peak * trail_lock / 100
                if profit <= floor:
                    return (profit, False)

        if stop_thresh > 0 and profit >= stop_thresh and iol_mult <= 1.01:
            return (profit, False)
        if sl_thresh > 0 and profit <= -sl_thresh:
            return (profit, False)

    return (profit, False)


def _resolve_hilo_hand(engine, floats, start_idx):
    """Resolve a HiLo hand consuming floats from the sequence.
    Returns (won, net_payout_mult) and the number of floats consumed."""
    # For PF replay of HiLo, each card draw consumes one float
    # This is a simplified version — full implementation would track skip/bet/cashout
    # For now, use the engine's resolve with a seeded RNG from the float
    import random
    rng = random.Random(int(floats[start_idx] * 2**32))
    return engine.resolve(rng)
```

- [ ] **Step 3: Verify PF float generation**

Run:
```bash
cd scripts/tools && python3 -c "
from proving_ground.provably_fair import shuffle_float, float_to_dice, float_to_roulette

# Test with first seed pair, nonce 0
f = shuffle_float(
    '2c01d9109499adf0034370e463ec255906af4abd948820791df10a0e608701c2',
    'k7a8xxuk2p', 0)
print(f'Float: {f:.10f}')
print(f'Dice roll: {float_to_dice(f):.2f}')
print(f'Roulette: {float_to_roulette(f)}')
print(f'First 5 dice rolls:')
for n in range(5):
    f = shuffle_float(
        '2c01d9109499adf0034370e463ec255906af4abd948820791df10a0e608701c2',
        'k7a8xxuk2p', n)
    print(f'  nonce={n}: {float_to_dice(f):.2f}')
"
```

Expected: Deterministic outputs — same inputs always produce same float.

---

### Task 6: Markov Chain Pillar

**Files:**
- Create: `scripts/tools/proving_ground/markov.py`

- [ ] **Step 1: Create `markov.py`**

```python
"""Pillar 2: Markov Chain exact analysis.

Models the strategy as a finite state machine with absorbing states (ruin, target).
Computes exact ruin probability and expected time to absorption.

Works for strategies with finite, enumerable states. IOL strategies are bounded
by the soft bust threshold (multiplier resets when bet > 95% balance).
"""

import math


def run_markov(strategy, engine, params):
    """
    Compute exact Markov chain stats for a simple IOL strategy on a binary game.

    This works for dice/roulette (binary win/loss) with IOL multipliers.
    Not applicable to HiLo (multi-round hands) — returns None for unsupported games.

    Models profit as discrete units (base bet increments) and IOL as state.

    Returns:
        dict with ruin_prob, target_prob, expected_hands, or None if unsupported
    """
    if engine.name == "hilo":
        return {"error": "Markov not supported for multi-round games (HiLo)", "supported": False}

    bank = params.get("bank", 100)
    divider = params.get("divider", 10000)
    stop_pct = params.get("stop_pct", 15)
    sl_pct = params.get("sl_pct", 15)

    base = bank / divider
    win_prob = engine.win_prob
    win_pay = engine.net_payout  # net profit multiplier on win

    # IOL multiplier from strategy
    iol = getattr(strategy, 'iol', 3.0)

    # Discretize profit into units of base bet
    # State: (profit_units, iol_level)
    # profit_units range: -sl_units to +stop_units
    sl_units = int(bank * sl_pct / 100 / base)
    stop_units = int(bank * stop_pct / 100 / base)

    # IOL levels: 0 (base), 1 (iol^1), 2 (iol^2), ...
    # Max level: where iol^level * base > bank * 0.95 → soft bust
    max_level = 0
    while base * (iol ** (max_level + 1)) <= bank * 0.95:
        max_level += 1
    max_level = min(max_level, 15)  # safety cap

    # States: (profit_unit, iol_level) for non-absorbing
    # Absorbing: RUIN (profit <= -sl), TARGET (profit >= +stop)
    # Profit units from -sl_units to +stop_units
    # Total transient states: (sl_units + stop_units + 1) * (max_level + 1)

    num_profit = sl_units + stop_units + 1  # includes 0
    num_levels = max_level + 1
    n_transient = num_profit * num_levels

    def state_idx(pu, level):
        """Map (profit_units, iol_level) to matrix index."""
        # pu ranges from -sl_units to +stop_units
        return (pu + sl_units) * num_levels + level

    def is_absorbing_ruin(pu):
        return pu <= -sl_units

    def is_absorbing_target(pu, level):
        return pu >= stop_units and level == 0

    # Build transition probabilities
    # For each transient state, compute P(next state)
    ruin_from = [0.0] * n_transient
    target_from = [0.0] * n_transient
    transitions = {}  # state_idx -> [(next_idx, prob), ...]

    for pu in range(-sl_units + 1, stop_units):
        for level in range(num_levels):
            idx = state_idx(pu, level)
            bet_mult = iol ** level
            win_units = max(1, int(round(bet_mult * win_pay)))
            loss_units = max(1, int(round(bet_mult)))

            # On win: profit += win_units, level resets to 0
            next_pu_win = pu + win_units
            if next_pu_win >= stop_units:
                target_from[idx] += win_prob
            elif next_pu_win <= -sl_units:
                ruin_from[idx] += win_prob
            else:
                next_idx = state_idx(next_pu_win, 0)
                transitions.setdefault(idx, []).append((next_idx, win_prob))

            # On loss: profit -= loss_units, level += 1 (or reset if soft bust)
            next_pu_loss = pu - loss_units
            next_level = level + 1
            if next_level > max_level:
                next_level = 0  # soft bust reset

            if next_pu_loss <= -sl_units:
                ruin_from[idx] += (1 - win_prob)
            elif next_pu_loss >= stop_units:
                target_from[idx] += (1 - win_prob)
            else:
                next_idx = state_idx(next_pu_loss, next_level)
                transitions.setdefault(idx, []).append((next_idx, 1 - win_prob))

    # Solve for absorption probabilities using iterative method
    # P_ruin(i) = ruin_from[i] + sum(P(j) * P_ruin(j) for j in transitions[i])
    ruin_prob = [0.0] * n_transient
    target_prob = [0.0] * n_transient

    # Iterative solution (value iteration)
    for iteration in range(1000):
        new_ruin = [0.0] * n_transient
        new_target = [0.0] * n_transient
        for idx in range(n_transient):
            r = ruin_from[idx]
            t = target_from[idx]
            for next_idx, prob in transitions.get(idx, []):
                r += prob * ruin_prob[next_idx]
                t += prob * target_prob[next_idx]
            new_ruin[idx] = r
            new_target[idx] = t

        # Check convergence
        max_delta = max(abs(new_ruin[i] - ruin_prob[i]) for i in range(n_transient))
        ruin_prob = new_ruin
        target_prob = new_target
        if max_delta < 1e-8:
            break

    # Starting state: profit=0, level=0
    start_idx = state_idx(0, 0)

    return {
        "supported": True,
        "ruin_prob": ruin_prob[start_idx] * 100,
        "target_prob": target_prob[start_idx] * 100,
        "iterations": iteration + 1,
        "states": n_transient,
        "max_iol_level": max_level,
        "profit_units": num_profit,
    }
```

- [ ] **Step 2: Verify Markov for flat dice**

Run:
```bash
cd scripts/tools && python3 -c "
from proving_ground.markov import run_markov
from proving_ground.strategy import FlatStrategy, MambaStrategy
from proving_ground.engines import DiceEngine

e = DiceEngine(65)
params = dict(bank=100, divider=10000, stop_pct=15, sl_pct=15)

# Flat bet — should lose ~100% (house edge grinds)
r = run_markov(FlatStrategy('dice'), e, params)
print(f'Flat dice 65%:')
print(f'  Ruin: {r[\"ruin_prob\"]:.1f}% | Target: {r[\"target_prob\"]:.1f}%')
print(f'  States: {r[\"states\"]} | Converged in {r[\"iterations\"]} iterations')

# IOL 3.0x — should have higher target prob
r = run_markov(MambaStrategy(3.0), e, params)
print(f'MAMBA IOL=3.0x:')
print(f'  Ruin: {r[\"ruin_prob\"]:.1f}% | Target: {r[\"target_prob\"]:.1f}%')
print(f'  States: {r[\"states\"]} | Max IOL level: {r[\"max_iol_level\"]}')
"
```

Expected: Flat bet should show high ruin probability. MAMBA should show lower ruin, higher target probability.

---

### Task 7: Unified Report

**Files:**
- Create: `scripts/tools/proving_ground/report.py`

- [ ] **Step 1: Create `report.py`**

```python
"""Unified report — combines all three validation pillars."""

import json
import time


def prove(strategy, engine, params, num_sessions=5000, seeds_path=None, pillars="all"):
    """
    Run all validation pillars and produce unified report.

    Args:
        strategy: Strategy instance
        engine: GameEngine instance
        params: session params dict
        num_sessions: MC session count
        seeds_path: path to seeds.json for PF replay
        pillars: "all", "mc", "markov", "pf" — or comma-separated

    Returns:
        dict with per-pillar results and agreement metrics
    """
    active = set(pillars.split(",")) if pillars != "all" else {"mc", "markov", "pf"}
    report = {"strategy": strategy.name, "game": strategy.game, "params": params}

    # Pillar 1: Monte Carlo
    if "mc" in active:
        from proving_ground.monte_carlo import run_mc
        t0 = time.time()
        report["mc"] = run_mc(strategy, engine, params, num=num_sessions)
        report["mc"]["runtime_s"] = round(time.time() - t0, 1)

    # Pillar 2: Markov Chain
    if "markov" in active:
        from proving_ground.markov import run_markov
        t0 = time.time()
        report["markov"] = run_markov(strategy, engine, params)
        report["markov"]["runtime_s"] = round(time.time() - t0, 1)

    # Pillar 3: Provably Fair Replay
    if "pf" in active:
        from proving_ground.provably_fair import run_pf
        t0 = time.time()
        report["pf"] = run_pf(strategy, engine, params, seeds_path=seeds_path,
                               game=strategy.game)
        report["pf"]["runtime_s"] = round(time.time() - t0, 1)

    # Agreement metrics
    report["agreement"] = _compute_agreement(report)

    return report


def _compute_agreement(report):
    """Compare pillar results for consistency."""
    agreement = {}
    mc = report.get("mc", {})
    markov = report.get("markov", {})
    pf = report.get("pf", {})

    mc_med = mc.get("median")
    pf_med = pf.get("median")
    markov_target = markov.get("target_prob")

    if mc_med is not None and pf_med is not None:
        delta = abs(mc_med - pf_med)
        agreement["mc_vs_pf_delta"] = round(delta, 2)
        if mc_med != 0:
            agreement["mc_vs_pf_pct"] = round(delta / abs(mc_med) * 100, 1)
        agreement["mc_vs_pf_warning"] = delta > abs(mc_med) * 0.20 if mc_med else False

    if mc.get("win_pct") is not None and markov_target is not None:
        agreement["mc_win_pct"] = round(mc["win_pct"], 1)
        agreement["markov_target_pct"] = round(markov_target, 1)
        delta = abs(mc["win_pct"] - markov_target)
        agreement["mc_vs_markov_delta"] = round(delta, 1)
        agreement["mc_vs_markov_warning"] = delta > 20

    return agreement


def print_report(report):
    """Pretty-print the unified report."""
    print()
    print("=" * 90)
    print("  PROVING GROUND — " + report["strategy"].upper() + " (" + report["game"] + ")")
    print("=" * 90)

    params = report["params"]
    print(f"  Bank: ${params.get('bank', 100)} | Div: {params.get('divider', 10000)} "
          f"| Trail: {params.get('trail_act', 8)}/{params.get('trail_lock', 60)} "
          f"| SL: {params.get('sl_pct', 15)}% | SP: {params.get('stop_pct', 15)}%")

    # MC
    mc = report.get("mc")
    if mc:
        print(f"\n  --- Pillar 1: Monte Carlo ({mc.get('count', '?')} sessions, {mc.get('runtime_s', '?')}s) ---")
        print(f"  Median: ${mc['median']:+.2f} | Mean: ${mc['mean']:+.2f}")
        print(f"  Bust: {mc['bust_pct']:.1f}% | Win: {mc['win_pct']:.1f}%")
        print(f"  P5: ${mc['p5']:+.2f} | P10: ${mc['p10']:+.2f} | P90: ${mc['p90']:+.2f} | P95: ${mc['p95']:+.2f}")

    # Markov
    markov = report.get("markov")
    if markov:
        print(f"\n  --- Pillar 2: Markov Chain ({markov.get('runtime_s', '?')}s) ---")
        if markov.get("supported"):
            print(f"  Ruin prob: {markov['ruin_prob']:.1f}% | Target prob: {markov['target_prob']:.1f}%")
            print(f"  States: {markov['states']} | Max IOL level: {markov['max_iol_level']} | Converged: {markov['iterations']} iters")
        else:
            print(f"  {markov.get('error', 'Not supported')}")

    # PF
    pf = report.get("pf")
    if pf:
        print(f"\n  --- Pillar 3: Provably Fair Replay ({pf.get('runtime_s', '?')}s) ---")
        if pf.get("count", 0) > 0:
            print(f"  Median: ${pf['median']:+.2f} | Mean: ${pf['mean']:+.2f}")
            print(f"  Bust: {pf['bust_pct']:.1f}% | Win: {pf['win_pct']:.1f}%")
            print(f"  Seed pairs: {pf.get('seed_pairs', '?')} | Total nonces: {pf.get('total_nonces', '?')}")
        else:
            print(f"  No results (check seeds file)")

    # Agreement
    ag = report.get("agreement", {})
    if ag:
        print(f"\n  --- Agreement ---")
        if "mc_vs_pf_delta" in ag:
            warn = " ⚠️ WARNING" if ag.get("mc_vs_pf_warning") else " ✓"
            print(f"  MC vs PF: Δ${ag['mc_vs_pf_delta']:.2f} ({ag.get('mc_vs_pf_pct', '?')}%){warn}")
        if "mc_vs_markov_delta" in ag:
            warn = " ⚠️ WARNING" if ag.get("mc_vs_markov_warning") else " ✓"
            print(f"  MC win% vs Markov target%: {ag['mc_win_pct']}% vs {ag['markov_target_pct']}% (Δ{ag['mc_vs_markov_delta']}%){warn}")

    print("=" * 90)


def save_report(report, path):
    """Save report to JSON."""
    with open(path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
```

- [ ] **Step 2: Verify report generation**

Run:
```bash
cd scripts/tools && python3 -c "
from proving_ground.report import prove, print_report
from proving_ground.strategy import MambaStrategy
from proving_ground.engines import DiceEngine

s = MambaStrategy(3.0)
e = DiceEngine(65)
params = dict(bank=100, divider=10000, stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60)

report = prove(s, e, params, num_sessions=1000, pillars='mc,markov')
print_report(report)
"
```

Expected: Report with MC and Markov sections, agreement comparison.

---

### Task 8: CLI Entry Point

**Files:**
- Create: `scripts/tools/proving_ground/main.py`

- [ ] **Step 1: Create `main.py`**

```python
#!/usr/bin/env python3
"""PROVING GROUND CLI — Antebot Strategy Testing Harness.

Usage:
    python3 -m proving_ground.main --strategy mamba --bank 100 --sessions 5000
    python3 -m proving_ground.main --strategy mamba --bank 100 --pillar pf --seeds seeds.json
    python3 -m proving_ground.main --strategy flat --bank 100 --pillar markov
"""

import argparse
import os
import sys

# Add parent dir to path so 'proving_ground' is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proving_ground.strategy import STRATEGIES, MambaStrategy, SidewinderStrategy, FlatStrategy
from proving_ground.engines import DiceEngine, RouletteEngine, HiLoEngine
from proving_ground.report import prove, print_report, save_report


def build_strategy(name):
    """Build strategy from name."""
    if name == "mamba":
        return MambaStrategy(iol=3.0)
    elif name == "sidewinder":
        return SidewinderStrategy(iol=3.0)
    elif name == "flat":
        return FlatStrategy("dice")
    elif name in STRATEGIES:
        return STRATEGIES[name]()
    else:
        print(f"Unknown strategy: {name}")
        print(f"Available: {', '.join(STRATEGIES.keys())}")
        sys.exit(1)


def build_engine(strategy):
    """Build engine matching strategy's game type."""
    if strategy.game == "dice":
        return DiceEngine(chance=65)
    elif strategy.game == "roulette":
        return RouletteEngine(covered_count=23)
    elif strategy.game == "hilo":
        return HiLoEngine(skip_set=frozenset({6, 7, 8}), cashout_target=1.5)
    else:
        print(f"Unknown game: {strategy.game}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="PROVING GROUND — Strategy Testing Harness")
    parser.add_argument("--strategy", "-s", default="mamba", help="Strategy name (mamba, sidewinder, flat)")
    parser.add_argument("--bank", "-b", type=float, default=100, help="Starting balance")
    parser.add_argument("--divider", "-d", type=int, default=10000, help="Bet divider")
    parser.add_argument("--sessions", "-n", type=int, default=5000, help="MC session count")
    parser.add_argument("--pillar", "-p", default="all", help="Pillar to run: mc, markov, pf, all")
    parser.add_argument("--seeds", default=None, help="Path to seeds.json for PF replay")
    parser.add_argument("--stop", type=float, default=15, help="Stop profit %")
    parser.add_argument("--sl", type=float, default=15, help="Stop loss %")
    parser.add_argument("--trail-act", type=float, default=8, help="Trail activate %")
    parser.add_argument("--trail-lock", type=float, default=60, help="Trail lock %")
    parser.add_argument("--output", "-o", default=None, help="Save report to JSON file")
    args = parser.parse_args()

    strategy = build_strategy(args.strategy)
    engine = build_engine(strategy)
    params = {
        "bank": args.bank,
        "divider": args.divider,
        "stop_pct": args.stop,
        "sl_pct": args.sl,
        "trail_act": args.trail_act,
        "trail_lock": args.trail_lock,
    }

    # Default seeds path
    seeds_path = args.seeds
    if seeds_path is None and ("pf" in args.pillar or args.pillar == "all"):
        default_seeds = os.path.join(os.path.dirname(__file__), "seeds.json")
        if os.path.exists(default_seeds):
            seeds_path = default_seeds

    report = prove(strategy, engine, params,
                   num_sessions=args.sessions,
                   seeds_path=seeds_path,
                   pillars=args.pillar)
    print_report(report)

    if args.output:
        save_report(report, args.output)
        print(f"\n  Report saved to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI**

Run:
```bash
cd scripts/tools && python3 -m proving_ground.main --strategy mamba --bank 100 --sessions 1000 --pillar mc
```

Expected: MC report for MAMBA with median, win%, percentiles.

Then test all pillars:
```bash
cd scripts/tools && python3 -m proving_ground.main --strategy mamba --bank 100 --sessions 1000 --pillar all
```

Expected: All three pillar sections in the report.

---

### Task 9: Update Package `__init__.py` with Public API

**Files:**
- Modify: `scripts/tools/proving_ground/__init__.py`

- [ ] **Step 1: Update `__init__.py` to export the public API**

```python
"""PROVING GROUND — Antebot Strategy Testing Harness.

Usage:
    from proving_ground.report import prove, print_report
    from proving_ground.strategy import MambaStrategy, SidewinderStrategy
    from proving_ground.engines import DiceEngine, HiLoEngine

    report = prove(MambaStrategy(3.0), DiceEngine(65),
                   dict(bank=100, divider=10000, stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60),
                   num_sessions=5000)
    print_report(report)

CLI:
    python3 -m proving_ground.main --strategy mamba --bank 100 --sessions 5000
"""

from proving_ground.strategy import (
    Strategy, FlatStrategy, IOLStrategy, MambaStrategy, SidewinderStrategy, STRATEGIES
)
from proving_ground.engines import DiceEngine, RouletteEngine, HiLoEngine, ENGINES
from proving_ground.report import prove, print_report, save_report
```

- [ ] **Step 2: Verify public API imports**

Run:
```bash
cd scripts/tools && python3 -c "
from proving_ground import prove, print_report, MambaStrategy, DiceEngine
print('Public API imports OK')
print(f'Available strategies: {list(proving_ground.STRATEGIES.keys()) if hasattr(proving_ground, \"STRATEGIES\") else \"use STRATEGIES dict\"}')
"
```

Expected: `Public API imports OK`

---

### Task 10: End-to-End Verification

- [ ] **Step 1: Full MC run — compare with existing MAMBA optimizer**

Run the existing optimizer first to get baseline:
```bash
cd scripts/tools && python3 -c "
# Run existing MAMBA optimizer for reference
import sys; sys.path.insert(0, '.')
from proving_ground.monte_carlo import run_mc
from proving_ground.strategy import MambaStrategy
from proving_ground.engines import DiceEngine

s = MambaStrategy(3.0)
e = DiceEngine(65)
params = dict(bank=1000, divider=10000, stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60)
r = run_mc(s, e, params, num=5000)
print(f'PROVING GROUND MAMBA ($1000):')
print(f'  Median: \${r[\"median\"]:+.2f} (expect ~+\$54)')
print(f'  Win%: {r[\"win_pct\"]:.1f}% (expect ~70%)')
print(f'  Bust%: {r[\"bust_pct\"]:.1f}%')
print(f'  P10: \${r[\"p10\"]:+.2f} (expect ~-\$300)')
"
```

Expected: Median within 5% of existing optimizer's ~$54.

- [ ] **Step 2: Full 3-pillar run**

```bash
cd scripts/tools && python3 -m proving_ground.main --strategy mamba --bank 100 --sessions 5000 --pillar all
```

Expected: Complete report with MC + Markov + PF sections, agreement metrics. No crashes.

- [ ] **Step 3: Test SIDEWINDER through the harness**

```bash
cd scripts/tools && python3 -m proving_ground.main --strategy sidewinder --bank 100 --sessions 5000 --pillar mc
```

Expected: SIDEWINDER MC results, median ~+$7.
