# SIDEWINDER HiLo Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HiLo profit strategy that exploits chain mechanics (skip + dynamic cashout) combined with IOL recovery, targeting +$6.50 median at $100 bank with P10 better than -$25.

**Architecture:** Two deliverables — (1) Python Monte Carlo optimizer that simulates HiLo hands with skip/bet/cashout per-card logic, wraps them in IOL + trailing stop sessions, and sweeps parameters to find optimal config. (2) Antebot JS script using `engine.onGameRound()` for per-card decisions and `engine.onBetPlaced()` for session-level IOL/mode/stop logic. Three-mode state machine (CRUISE/RECOVERY/CAPITALIZE) adjusts the cashout target per hand.

**Tech Stack:** Python 3 (optimizer), JavaScript (Antebot Code Mode — `var` only, string concat, no imports)

**PRD:** `antebot/.claude/prd/sidewinder-hilo-strategy.md`

---

## File Structure

| File | Purpose |
|------|---------|
| `scripts/tools/sidewinder-optimizer.py` | Monte Carlo: HiLo hand sim + session sim + parameter sweep + MAMBA/COBRA comparison |
| `scripts/hilo/sidewinder.js` | Antebot script: onGameRound per-card logic, onBetPlaced session logic, 3-mode state machine |
| `CLAUDE.md` | Add SIDEWINDER to flagship scripts table |

---

### Task 1: HiLo Hand Simulator (Python Core Engine)

**Files:**
- Create: `scripts/tools/sidewinder-optimizer.py`

This task builds the core `sim_hand()` function that simulates a single HiLo hand: start card → sequence of skip/bet/cashout decisions → returns (won: bool, payout_multiplier: float).

- [ ] **Step 1: Create the optimizer file with card math constants**

```python
#!/usr/bin/env python3
"""
SIDEWINDER Optimizer — HiLo Adaptive Chain Monte Carlo
Simulates HiLo hands with skip/bet/cashout per-card logic.
Wraps in IOL + trailing stop sessions. Sweeps parameters.
"""

import random
import sys

# Card values: A=1, 2-10, J=11, Q=12, K=13
CARD_RANKS = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
RANK_TO_VAL = {r: i+1 for i, r in enumerate(CARD_RANKS)}
EDGE = 0.01  # 1% house edge


def hilo_payout(card_val, bet_high):
    """Return (win_probability, payout_multiplier) for a single prediction."""
    if bet_high:
        winning = 13 - card_val  # cards strictly higher
    else:
        winning = card_val - 1   # cards strictly lower
    if winning <= 0:
        return (0.0, 0.0)
    prob = winning / 13.0
    pay = (1.0 - EDGE) * 13.0 / winning  # 0.99 * 13 / winning
    return (prob, pay)
```

- [ ] **Step 2: Run the file to verify it loads without errors**

Run: `python3 scripts/tools/sidewinder-optimizer.py`
Expected: No output, no errors (no `__main__` block yet)

- [ ] **Step 3: Add the `sim_hand()` function**

This is the core HiLo hand simulation. It takes a skip set, cashout target, and returns whether the hand won and the accumulated payout multiplier.

```python
def sim_hand(rng, skip_set, cashout_target, start_val=1):
    """
    Simulate one HiLo hand.
    
    Args:
        rng: random.Random instance
        skip_set: set of card values (1-13) to skip
        cashout_target: cash out when accumulated multiplier >= this
        start_val: starting card value (1=Ace, default)
    
    Returns:
        (won: bool, multiplier: float)
        won=True means we cashed out. multiplier is the accumulated payout.
        won=False means a prediction was wrong. multiplier is irrelevant (lost bet).
    """
    current_val = start_val
    accumulated = 1.0
    skips_used = 0
    max_skips = 52

    for _ in range(200):  # safety limit
        # Check cashout
        if accumulated >= cashout_target and accumulated > 1.0:
            return (True, accumulated)

        # Draw next card
        next_val = rng.randint(1, 13)

        # Skip logic
        if current_val in skip_set and skips_used < max_skips:
            skips_used += 1
            current_val = next_val
            continue

        # Decide direction: bet HIGH if current <= 7, LOW if current > 7
        # Special cases: A(1) always HIGH, K(13) always LOW
        if current_val <= 7:
            bet_high = True
        else:
            bet_high = False

        prob, pay = hilo_payout(current_val, bet_high)
        if prob <= 0:
            # Edge case: can't bet in this direction (e.g., LOW on Ace)
            # Skip instead if possible
            if skips_used < max_skips:
                skips_used += 1
                current_val = next_val
                continue
            else:
                return (True, accumulated)  # forced cashout

        # Resolve prediction
        if bet_high:
            correct = next_val > current_val
        else:
            correct = next_val < current_val

        if correct:
            accumulated *= pay
            current_val = next_val
        else:
            return (False, 0.0)  # lost the hand

    # Exceeded safety limit — cash out
    return (True, accumulated)
```

- [ ] **Step 4: Add a quick sanity test in `__main__`**

```python
if __name__ == "__main__":
    # Sanity test: run 10000 hands, check win rate and avg multiplier
    rng = random.Random(42)
    skip_set = {5, 6, 7, 8, 9}  # skip middle cards
    wins = 0
    total_mult = 0.0
    n = 10000
    for _ in range(n):
        won, mult = sim_hand(rng, skip_set, cashout_target=1.5)
        if won:
            wins += 1
            total_mult += mult
    print(f"Sanity test: {n} hands, skip={{5-9}}, cashout=1.5x")
    print(f"  Win rate: {wins/n*100:.1f}%")
    print(f"  Avg win mult: {total_mult/max(wins,1):.3f}x")
    print(f"  Expected: ~60-70% win rate, ~1.5-1.8x avg multiplier")
```

- [ ] **Step 5: Run sanity test**

Run: `python3 scripts/tools/sidewinder-optimizer.py`
Expected: Output showing ~60-70% win rate and ~1.5-1.8x average multiplier. If win rate is <40% or >90%, the hand logic has a bug.

- [ ] **Step 6: Commit**

```bash
git add scripts/tools/sidewinder-optimizer.py
git commit -m "feat(sidewinder): add HiLo hand simulator core engine"
```

---

### Task 2: Session Simulator (IOL + Trailing Stop + Modes)

**Files:**
- Modify: `scripts/tools/sidewinder-optimizer.py`

Wrap the hand simulator in a full session: IOL escalation on loss, trailing stop, stop loss/profit, three-mode state machine.

- [ ] **Step 1: Add the `sim_session()` function**

Add this after `sim_hand()`:

```python
def sim_session(bank=100, divider=10000, iol=2.0, seed_offset=0, seed=42,
                skip_set=None, cashout_cruise=1.5, cashout_recovery=2.5,
                cashout_capitalize=1.2, recovery_threshold=5,
                max_hands=5000, stop_pct=15, sl_pct=15,
                trail_act=8, trail_lock=60, start_val=1):
    """
    Simulate one SIDEWINDER session.
    
    Modes:
        CRUISE: default, cashout at cashout_cruise
        RECOVERY: when profit < -recovery_threshold% or IOL mult > 1.5
        CAPITALIZE: when trail is active
    """
    if skip_set is None:
        skip_set = {5, 6, 7, 8, 9}

    rng = random.Random(seed * 100000 + seed_offset)
    base = bank / divider
    min_bet = 0.00101
    if base < min_bet:
        base = min_bet

    mult = 1.0
    profit = 0.0
    peak = 0.0
    hands = 0
    trail_active = False

    stop_thresh = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_thresh = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_thresh = bank * trail_act / 100 if trail_act > 0 else 0

    for _ in range(max_hands):
        bal = bank + profit
        if bal <= 0:
            return profit, True  # bust

        bet = base * mult
        if bet > bal * 0.95:
            mult = 1.0
            bet = base
        if bet > bal:
            bet = bal
        if bet < 0.001:
            return profit, True  # bust

        # Trail-aware bet cap
        if trail_active:
            floor = peak * trail_lock / 100
            max_t = profit - floor
            if max_t > 0 and bet > max_t:
                bet = max_t
            if bet < 0.001:
                return profit, False  # trail exit

        hands += 1

        # Determine mode and cashout target
        if trail_active:
            target = cashout_capitalize
        elif profit < -(bank * recovery_threshold / 100) or mult > 1.5:
            target = cashout_recovery
        else:
            target = cashout_cruise

        # Simulate the hand
        won, hand_mult = sim_hand(rng, skip_set, target, start_val)

        if won:
            profit += bet * (hand_mult - 1.0)
            mult = 1.0
        else:
            profit -= bet
            mult *= iol
            nb = base * mult
            if bank + profit > 0 and nb > (bank + profit) * 0.95:
                mult = 1.0

        if bank + profit <= 0:
            return profit, True  # bust

        if profit > peak:
            peak = profit

        # Trail
        if trail_act > 0:
            if not trail_active and profit >= act_thresh:
                trail_active = True
            if trail_active:
                floor = peak * trail_lock / 100
                if profit <= floor:
                    return profit, False  # trail exit

        # Stop profit
        if stop_thresh > 0 and profit >= stop_thresh and mult <= 1.01:
            return profit, False

        # Stop loss
        if sl_thresh > 0 and profit <= -sl_thresh:
            return profit, False

    return profit, False
```

- [ ] **Step 2: Add the `sim_batch()` function to run N sessions**

```python
def sim_batch(num=5000, **kwargs):
    """Run num sessions and return stats."""
    pnls = []
    busts = 0
    for s in range(num):
        p, busted = sim_session(seed_offset=s, **kwargs)
        pnls.append(p)
        if busted:
            busts += 1

    pnls.sort()
    nr = len(pnls)
    return {
        'median': pnls[nr // 2],
        'mean': sum(pnls) / nr,
        'bust_pct': busts / nr * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / nr * 100,
        'p5': pnls[nr // 20],
        'p10': pnls[nr // 10],
        'p90': pnls[9 * nr // 10],
    }
```

- [ ] **Step 3: Replace the `__main__` sanity test with a session sanity test**

Replace the existing `__main__` block:

```python
if __name__ == "__main__":
    # Quick sanity: one config
    print("Session sanity test: $100 bank, IOL=2.0x, cashout cruise=1.5x")
    r = sim_batch(num=1000, bank=100, divider=10000, iol=2.0,
                  cashout_cruise=1.5, cashout_recovery=2.5, cashout_capitalize=1.2)
    print(f"  Median: ${r['median']:+.2f}")
    print(f"  Mean:   ${r['mean']:+.2f}")
    print(f"  Bust:   {r['bust_pct']:.1f}%")
    print(f"  Win:    {r['win_pct']:.1f}%")
    print(f"  P10:    ${r['p10']:+.2f}")
    print(f"  P90:    ${r['p90']:+.2f}")
    print(f"  Expected: positive median, bust < 5%, win > 50%")
```

- [ ] **Step 4: Run session sanity test**

Run: `python3 scripts/tools/sidewinder-optimizer.py`
Expected: Positive median, bust < 5%, win > 50%. If median is negative or bust > 20%, debug the session logic.

- [ ] **Step 5: Commit**

```bash
git add scripts/tools/sidewinder-optimizer.py
git commit -m "feat(sidewinder): add session simulator with IOL, trail, modes"
```

---

### Task 3: Parameter Sweep + MAMBA/COBRA Comparison

**Files:**
- Modify: `scripts/tools/sidewinder-optimizer.py`

Replace the `__main__` block with a full parameter sweep and head-to-head comparison.

- [ ] **Step 1: Add print helper**

```python
def pr(tag, r):
    print(f"  {tag:<55} ${r['median']:>+7.2f} ${r['mean']:>+7.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+7.2f} ${r['p90']:>+7.2f}")
```

- [ ] **Step 2: Add MAMBA baseline simulator**

```python
def sim_mamba(bank=100, num=5000, divider=10000, iol=3.0, seed=42,
              stop_pct=15, sl_pct=15, trail_act=8, trail_lock=60):
    """MAMBA baseline: dice 65% IOL 3.0x."""
    WIN_PROB = 0.65
    WIN_PAY = 99.0 / 65.0 - 1.0
    pnls = []
    busts = 0
    for s in range(num):
        random.seed(seed * 100000 + s)
        base = bank / divider
        if base < 0.00101:
            base = 0.00101
        mult = 1.0
        profit = 0.0
        peak = 0.0
        trail_active = False
        stop_thresh = bank * stop_pct / 100
        sl_thresh = bank * sl_pct / 100
        act_thresh = bank * trail_act / 100
        for _ in range(5000):
            bal = bank + profit
            if bal <= 0:
                busts += 1; break
            bet = base * mult
            if bet > bal * 0.95:
                mult = 1.0; bet = base
            if bet > bal: bet = bal
            if bet < 0.001:
                busts += 1; break
            if random.random() < WIN_PROB:
                profit += bet * WIN_PAY; mult = 1.0
            else:
                profit -= bet; mult *= iol
                if bank + profit > 0 and base * mult > (bank + profit) * 0.95:
                    mult = 1.0
            if bank + profit <= 0:
                busts += 1; break
            if profit > peak: peak = profit
            if not trail_active and profit >= act_thresh:
                trail_active = True
            if trail_active:
                floor = peak * trail_lock / 100
                if profit <= floor: break
            if profit >= stop_thresh and mult <= 1.01: break
            if profit <= -sl_thresh: break
        pnls.append(profit)
    pnls.sort()
    nr = len(pnls)
    return {
        'median': pnls[nr // 2], 'mean': sum(pnls) / nr,
        'bust_pct': busts / nr * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / nr * 100,
        'p10': pnls[nr // 10], 'p90': pnls[9 * nr // 10],
    }
```

- [ ] **Step 3: Replace `__main__` with full sweep**

```python
if __name__ == "__main__":
    bank = 100
    num = 5000

    H = (f"  {'Config':<55} {'Med':>8} {'Mean':>8} "
         f"{'Bust%':>6} {'Win%':>6} {'P10':>8} {'P90':>8}")
    S = (f"  {'─'*55} {'─'*8} {'─'*8} {'─'*6} {'─'*6} {'─'*8} {'─'*8}")

    print()
    print("=" * 110)
    print(f"  SIDEWINDER OPTIMIZER — HiLo Adaptive Chain")
    print(f"  {num:,} sessions | ${bank} bank | trail=8/60 SL=15% stop=15%")
    print("=" * 110)

    # MAMBA baseline
    print("\n  === BASELINES ===")
    print(H); print(S)
    r_mamba = sim_mamba(bank, num)
    pr("MAMBA dice 65% IOL=3.0x div=10k", r_mamba)

    # Skip range variants
    SKIP_CONFIGS = {
        "skip 5-9 (middle 5)": {5, 6, 7, 8, 9},
        "skip 4-10 (middle 7)": {4, 5, 6, 7, 8, 9, 10},
        "skip 6-8 (narrow 3)": {6, 7, 8},
        "no skip (bet all)": set(),
    }

    # Sweep: IOL x cashout_cruise x skip
    print("\n  === SINGLE-MODE SWEEP (cruise cashout only, no mode switching) ===")
    print(H); print(S)
    all_configs = []
    for skip_name, skip_set in SKIP_CONFIGS.items():
        for iol in [1.5, 2.0, 2.5, 3.0]:
            for co in [1.2, 1.5, 2.0, 2.5, 3.0]:
                r = sim_batch(num=num, bank=bank, iol=iol, skip_set=skip_set,
                              cashout_cruise=co, cashout_recovery=co,
                              cashout_capitalize=co)
                r['tag'] = f"{skip_name} IOL={iol}x co={co}x"
                r['iol'] = iol
                r['co'] = co
                r['skip'] = skip_name
                all_configs.append(r)

    all_configs.sort(key=lambda x: x['median'], reverse=True)
    for r in all_configs[:20]:
        pr(r['tag'], r)

    # Best single-mode config
    best_single = all_configs[0]
    print(f"\n  Best single-mode: {best_single['tag']}")
    print(f"    Median: ${best_single['median']:+.2f} | P10: ${best_single['p10']:+.2f}")

    # Multi-mode sweep using best skip + IOL
    best_skip_name = best_single['skip']
    best_skip = SKIP_CONFIGS[best_skip_name]
    best_iol = best_single['iol']

    print(f"\n  === MULTI-MODE SWEEP (using {best_skip_name}, IOL={best_iol}x) ===")
    print(H); print(S)
    mode_configs = []
    for co_c in [1.2, 1.5, 2.0]:
        for co_r in [2.0, 2.5, 3.0, 4.0]:
            for co_cap in [1.1, 1.2, 1.5]:
                if co_r <= co_c:
                    continue
                r = sim_batch(num=num, bank=bank, iol=best_iol,
                              skip_set=best_skip,
                              cashout_cruise=co_c, cashout_recovery=co_r,
                              cashout_capitalize=co_cap)
                r['tag'] = f"C={co_c}x R={co_r}x Cap={co_cap}x"
                mode_configs.append(r)

    mode_configs.sort(key=lambda x: x['median'], reverse=True)
    for r in mode_configs[:15]:
        pr(r['tag'], r)

    # HEAD TO HEAD
    print()
    print("=" * 110)
    print("  HEAD-TO-HEAD vs MAMBA ($100)")
    print("=" * 110)
    print(H); print(S)
    pr("MAMBA dice 65% IOL=3.0x", r_mamba)
    best_mode = mode_configs[0] if mode_configs else best_single
    pr(f"SIDEWINDER best: {best_mode['tag']}", best_mode)
    pr(f"SIDEWINDER single: {best_single['tag']}", best_single)

    delta = best_mode['median'] - r_mamba['median']
    print(f"\n  Delta vs MAMBA: ${delta:+.2f} median")
    print("=" * 110)
```

- [ ] **Step 4: Run the full sweep**

Run: `python3 scripts/tools/sidewinder-optimizer.py`
Expected: Ranked table of configs, head-to-head vs MAMBA. Look for configs with median > MAMBA's median and P10 > -$25. This run will take 1-3 minutes.

- [ ] **Step 5: Commit**

```bash
git add scripts/tools/sidewinder-optimizer.py
git commit -m "feat(sidewinder): add parameter sweep and MAMBA comparison"
```

---

### Task 4: Build Antebot Script

**Files:**
- Create: `scripts/hilo/sidewinder.js`

Build the Antebot script using the optimal parameters from Task 3's sweep results. Use MAMBA's structure as the pattern. All code uses `var`, string concatenation, `engine.stop()`.

- [ ] **Step 1: Create the hilo directory**

Run: `mkdir -p scripts/hilo`

- [ ] **Step 2: Create `sidewinder.js` with config section**

Use the best parameters from the optimizer output. The values below are reasonable defaults — replace with optimizer results if they differ.

```javascript
// SIDEWINDER v1.0 — HiLo Adaptive Chain Profit Strategy
// Skip middle cards, chain predictions, cash out at dynamic target.
// Three modes: CRUISE (safe chains) / RECOVERY (longer chains) / CAPITALIZE (short chains)
// IOL 2.0x on hand loss. Trail 8/60 + SL 15%.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) / TAIPAN (Roulette v2) / SIDEWINDER (HiLo)

strategyTitle = "SIDEWINDER";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "hilo";

// USER CONFIG
// ============================================================
divider = 10000;
iolMultiplier = 2.0;

// Starting card (A = guaranteed 92% first prediction)
startCard = { rank: "A", suit: "C" };

// Skip range: card values to skip (0 = never skip that value)
// A=1, 2, 3, 4, 5, 6, 7, 8, 9, 10, J=11, Q=12, K=13
// Default: skip 5-9 (middle cards with ~50% either direction)
skipMin = 5;
skipMax = 9;

// Cashout targets per mode (accumulated multiplier)
cashoutCruise = 1.5;       // CRUISE: safe, consistent
cashoutRecovery = 2.5;     // RECOVERY: bigger swings to recover deficit
cashoutCapitalize = 1.2;   // CAPITALIZE: lock profits fast

// Recovery mode threshold (% of bank below zero)
recoveryThresholdPct = 5;

// Trailing stop
trailActivatePct = 8;
trailLockPct = 60;

// Stop conditions
stopTotalPct = 15;
stopOnLoss = 15;
stopAfterHands = 0;

// Reset stats on start
resetOnStart = true;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
}

if (resetOnStart) {
  resetStats();
  clearConsole();
}

startBalance = balance;

// Enforce minimum bet
minBet = 0.00101;
baseBet = startBalance / divider;
if (baseBet < minBet) {
  baseBet = minBet;
  log("#FFFF2A", "Min bet enforced: $" + baseBet.toFixed(5));
}
betSize = baseBet;

// Card value lookup
rankValues = {
  "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
  "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13
};

// Thresholds
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
stopLossThreshold = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;
recoveryThreshold = startBalance * recoveryThresholdPct / 100;

// State
currentMultiplier = 1;
handsPlayed = 0;
totalWins = 0;
totalLosses = 0;
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
peakProfit = 0;
totalWagered = 0;
maxBetSeen = baseBet;
recoveries = 0;
currentChainCost = 0;
biggestRecovery = 0;
stopped = false;
summaryPrinted = false;

// Trailing stop state
trailActive = false;
trailFloor = 0;
trailStopFired = false;

// Mode tracking
currentMode = "cruise";
cruiseHands = 0;
recoveryHands = 0;
capitalizeHands = 0;

// Per-hand tracking
handCards = "";
handSkips = 0;
handPredictions = 0;

// ============================================================
// GAME ROUND — Per-card decision within each hand
// ============================================================

engine.onGameRound(function (currentBet) {
  lastRound = currentBet.state.rounds.at(-1);

  // Get current card rank
  currentRank = lastRound && lastRound.card
    ? lastRound.card.rank
    : currentBet.state.startCard.rank;
  currentVal = rankValues[currentRank] || 7;

  // Get accumulated multiplier
  payoutMultiplier = lastRound ? lastRound.payoutMultiplier : 0;

  // Track skips in this hand
  skippedCards = 0;
  for (i = 0; i < currentBet.state.rounds.length; i++) {
    if (currentBet.state.rounds[i].action === "skip") skippedCards++;
  }

  // Determine cashout target based on current mode
  cashoutTarget = cashoutCruise;
  if (currentMode === "recovery") cashoutTarget = cashoutRecovery;
  if (currentMode === "capitalize") cashoutTarget = cashoutCapitalize;

  // CASHOUT: if accumulated multiplier meets target
  if (payoutMultiplier >= cashoutTarget) {
    return HILO_CASHOUT;
  }

  // SKIP: if card is in middle range
  if (currentVal >= skipMin && currentVal <= skipMax && skippedCards < 52) {
    return HILO_SKIP;
  }

  // BET: high if low card, low if high card
  if (currentVal <= 7) {
    handPredictions++;
    return HILO_BET_HIGH;
  } else {
    handPredictions++;
    return HILO_BET_LOW;
  }
});

// ============================================================
// BET PLACED — Session-level logic after each hand resolves
// ============================================================

engine.onBetPlaced(async function () {
  if (stopped) return;

  handsPlayed++;
  totalWagered += lastBet.amount;

  isWin = lastBet.win;

  if (isWin) {
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;

    recoveryAmt = baseBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    betSize = baseBet;
  } else {
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;

    currentChainCost += lastBet.amount;
    currentMultiplier *= iolMultiplier;

    // Soft bust
    nextBet = baseBet * currentMultiplier;
    if (nextBet > balance * 0.95) {
      currentMultiplier = 1;
      currentChainCost = 0;
    }
    betSize = baseBet * currentMultiplier;
  }

  if (profit > peakProfit) peakProfit = profit;

  // Trail-aware bet cap
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && betSize > maxTrailBet) {
      betSize = maxTrailBet;
    }
  }

  if (betSize < minBet) betSize = minBet;
  if (betSize > maxBetSeen) maxBetSeen = betSize;

  // Mode transitions
  if (trailActive) {
    currentMode = "capitalize";
    capitalizeHands++;
  } else if (profit < -recoveryThreshold || currentMultiplier > 1.5) {
    currentMode = "recovery";
    recoveryHands++;
  } else {
    currentMode = "cruise";
    cruiseHands++;
  }

  // Reset per-hand tracking
  handCards = "";
  handSkips = 0;
  handPredictions = 0;

  // Logging
  scriptLog();

  // Trailing stop check
  trailingStopCheck();
  if (stopped) return;

  // Stop checks
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && handsPlayed >= stopAfterHands) {
    log("#FFFF2A", "Dev stop: " + handsPlayed + " hands reached");
    stopped = true;
    logSummary();
    engine.stop();
  }
});

// ============================================================
// TRAILING STOP
// ============================================================

function trailingStopCheck() {
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
  }
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    if (profit <= trailFloor) {
      trailStopFired = true;
      log("#FFD700", "TRAILING STOP! Profit $" + profit.toFixed(2) + " < floor $" + trailFloor.toFixed(2));
      stopped = true;
      logSummary();
      engine.stop();
    }
  }
}

// ============================================================
// STOP CHECKS
// ============================================================

function stopProfitCheck() {
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentMultiplier <= 1.01) {
    log("#4FFB4F", "Target reached! P&L: $" + profit.toFixed(2));
    stopped = true;
    logSummary();
    engine.stop();
  }
}

function stopLossCheck() {
  if (stopLossThreshold > 0 && profit < -stopLossThreshold) {
    log("#FD6868", "Stop loss! $" + (-profit).toFixed(2) + " loss (-" + stopOnLoss + "%)");
    stopped = true;
    logSummary();
    engine.stop();
  }
}

// ============================================================
// LOGGING
// ============================================================

function modeColor() {
  if (currentMode === "cruise") return "#00FF7F";
  if (currentMode === "recovery") return "#FF6B6B";
  if (currentMode === "capitalize") return "#FFD700";
  return "#FFFFFF";
}

function logBanner() {
  log(
    "#FF4500",
    "================================\n SIDEWINDER v" + version +
    "\n================================\n by " + author + " | HiLo Adaptive Chain" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentBet = baseBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";

  trailBar = "";
  if (trailActive) {
    trailBar = " | TRAIL: floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = " | Trail arms at $" + trailActivateThreshold.toFixed(2);
  }

  cashoutTarget = cashoutCruise;
  if (currentMode === "recovery") cashoutTarget = cashoutRecovery;
  if (currentMode === "capitalize") cashoutTarget = cashoutCapitalize;

  log("#FF4500", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(5) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log(modeColor(), "Mode: " + currentMode.toUpperCase() + " | Cashout: " + cashoutTarget.toFixed(1) + "x | LS: " + lossStreak);
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2));
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Skip: " + skipMin + "-" + skipMax);
  log("#42CAF7", "Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);

  cPct = handsPlayed > 0 ? (cruiseHands / handsPlayed * 100).toFixed(0) : "0";
  rPct = handsPlayed > 0 ? (recoveryHands / handsPlayed * 100).toFixed(0) : "0";
  capPct = handsPlayed > 0 ? (capitalizeHands / handsPlayed * 100).toFixed(0) : "0";
  log("#FF4500", "CRUISE:" + cruiseHands + "(" + cPct + "%) REC:" + recoveryHands + "(" + rPct + "%) CAP:" + capitalizeHands + "(" + capPct + "%)");
  log("#FD71FD", "Hands: " + handsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4));
}

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  exitType = trailStopFired ? "TRAILING STOP" : "TARGET/MANUAL";
  log(
    "#FF4500",
    "================================\n SIDEWINDER v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("Hands: " + handsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2));
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);

  cPct = handsPlayed > 0 ? (cruiseHands / handsPlayed * 100).toFixed(0) : "0";
  rPct = handsPlayed > 0 ? (recoveryHands / handsPlayed * 100).toFixed(0) : "0";
  capPct = handsPlayed > 0 ? (capitalizeHands / handsPlayed * 100).toFixed(0) : "0";
  log("#FF4500", "Modes — CRUISE:" + cruiseHands + "(" + cPct + "%) REC:" + recoveryHands + "(" + rPct + "%) CAP:" + capitalizeHands + "(" + capPct + "%)");

  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
```

- [ ] **Step 3: Commit**

```bash
git add scripts/hilo/sidewinder.js
git commit -m "feat(sidewinder): add Antebot HiLo script with 3-mode state machine"
```

---

### Task 5: Update CLAUDE.md Flagship Table

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add SIDEWINDER to the flagship scripts table**

Add this row to the `## Flagship Scripts` table in `CLAUDE.md`, after the TAIPAN entry:

```
| `scripts/hilo/sidewinder.js` | HiLo | SIDEWINDER v1.0 — Adaptive chain (skip+cashout+IOL), 3-mode state machine, trail 8/60, IOL 2.0x |
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add SIDEWINDER to flagship scripts table"
```

---

### Task 6: Run Optimizer and Tune Parameters

This task is executed manually — run the optimizer, read results, update the script's defaults if needed.

- [ ] **Step 1: Run the optimizer**

Run: `python3 scripts/tools/sidewinder-optimizer.py`

Read the output. Look for:
1. Best single-mode config (skip range × IOL × cashout)
2. Best multi-mode config (CRUISE/RECOVERY/CAPITALIZE cashout targets)
3. Head-to-head vs MAMBA

- [ ] **Step 2: Update `sidewinder.js` config if optimizer found better parameters**

If the optimizer's best config differs from the defaults in the script, update:
- `iolMultiplier`
- `skipMin` / `skipMax`
- `cashoutCruise` / `cashoutRecovery` / `cashoutCapitalize`
- `divider`

Also update the comment header with actual Monte Carlo results.

- [ ] **Step 3: Commit if parameters changed**

```bash
git add scripts/hilo/sidewinder.js
git commit -m "tune(sidewinder): update params from optimizer results"
```

---

### Task 7: Sim Verification

- [ ] **Step 1: Run SIDEWINDER in Antebot sim mode**

Paste `scripts/hilo/sidewinder.js` into Antebot Code Mode. Set `stopAfterHands = 20` for a quick test. Run in simulation mode.

Verify:
- Banner prints with correct version
- Hands are being played (hands counter increments)
- Skip decisions fire on middle cards (look for skip patterns in bet history)
- Cashout fires when multiplier target reached
- Mode transitions logged (CRUISE/RECOVERY/CAPITALIZE)
- Stop fires after 20 hands

- [ ] **Step 2: Remove dev stop and run full sim session**

Set `stopAfterHands = 0` and run a full sim session. Verify:
- Session ends via trailing stop or fixed stop (not running forever)
- P&L in summary is reasonable (positive for wins, negative capped at ~SL%)
- Mode breakdown shows all three modes used

- [ ] **Step 3: Screenshot results for reference**

Take screenshots of the final summary for reference.
