# Blackjack Strategy Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a single configurable blackjack script (`rampart.js`) that supports 6 betting systems (flat, d'Alembert, Martingale, Paroli, Oscar's Grind, Fibonacci), optional side bets, configurable stop conditions, and vault-and-continue behavior.

**Architecture:** Single-file script with a config block at top, a betting system dispatcher (`calcNextBet()`), and shared infrastructure (win/loss tracking, vault logic, stop conditions, logging). Each betting system is a self-contained function that takes the current state and returns the next bet size. The `onGameRound` handler uses the built-in `blackJackPerfectNextAction('advanced', 'any')` for all play decisions.

**Tech Stack:** Antebot Code Mode JS (var-only, string concat, no template literals, Math.pow)

---

## Key Design Decisions

1. **Single file, not modular.** Antebot Code Mode runs a single script — no imports. Everything lives in `rampart.js`.
2. **Config block at top** — user edits one section, everything else is "DO NOT EDIT BELOW".
3. **Betting systems are functions** — `calcBet_flat()`, `calcBet_dalembert()`, etc. A dispatcher calls the right one based on config.
4. **Vault-and-continue** — RAMPART v2.1 pattern: at profit milestone, vault via `depositToVault()`, reset seed and cycle state, keep grinding. No walk-away stop.
5. **Stop-loss is the only hard stop** — configurable percentage. Everything else resets on vault.
6. **Side bets are independent** — flat multiplier of base bet, isolated from progression.
7. **`isSimulationMode`** — uses engine API, no manual toggle.

## Reference: Antebot Blackjack API

```
game = 'blackjack'
betSize (float), sideBetPerfectPairs (float), sideBet213 (float)
engine.onBetPlaced(async (lastBet) => { ... })
engine.onGameRound((currentBet, playerHandIndex) => { return action })
engine.onBettingStopped((isManualStop, lastError) => { ... })
engine.stop()
lastBet.win, lastBet.amount, lastBet.payout, lastBet.payoutMultiplier
blackJackPerfectNextAction(currentBet, playerHandIndex, strategy, double)
BLACKJACK_DOUBLE, BLACKJACK_HIT, BLACKJACK_SPLIT, BLACKJACK_STAND
depositToVault(amount), resetSeed(), resetStats(), playHitSound(), log()
isSimulationMode, balance
```

## Convention: Antebot Script Style

- `var` only (no let/const)
- String concat (no template literals)
- `Math.pow()` (no `**`)
- Arrow functions OK for engine callbacks
- `engine.stop()` not bare `stop()`

---

### Task 1: Config Block & Bankroll Init

**Files:**
- Modify: `scripts/blackjack/rampart.js` (full rewrite)

**Step 1: Write the config block**

Replace entire rampart.js with the new config-driven structure. The config block is the user-facing API — everything below is engine code.

```js
// === RAMPART v3.0 — Blackjack Strategy Engine ===
// Configurable betting system + advanced perfect strategy.
// Vault-and-continue at profit milestone. Stop on loss only.
//
// Supported systems: flat, dalembert, martingale, paroli, oscar, fibonacci
// Edit the CONFIG section below. Do not edit below the line.

if (isSimulationMode) {
    setSimulationBalance(100);
    resetSeed();
    resetStats();
    clearConsole();
}

game = 'blackjack';

// ============================================================
// CONFIG — Edit this section
// ============================================================

var CONFIG = {
    // Betting system: 'flat' | 'dalembert' | 'martingale' | 'paroli' | 'oscar' | 'fibonacci'
    system: 'flat',

    // Base bet as fraction of bankroll (0.01 = 1%)
    baseBetPct: 0.01,

    // Max bet cap as fraction of bankroll (0 = no cap)
    maxBetPct: 0.10,

    // Stop conditions
    vaultAtPct: 0.15,       // Vault and reset at +15% profit (0 = disabled)
    stopLossPct: 0.30,      // Hard stop at -30% loss

    // Side bets (set to 0 to disable)
    sideBetPerfectPairs: 0,  // Multiplier of base bet (e.g. 2 = 2x base bet)
    sideBet213: 0,           // Multiplier of base bet

    // Logging
    statusEvery: 50          // Log status every N hands (0 = disabled)
};

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================
```

**Step 2: Write bankroll initialization**

```js
var BANKROLL = isSimulationMode ? 100 : Math.floor(balance * 100) / 100;
var BASE_BET = Math.round(BANKROLL * CONFIG.baseBetPct * 100) / 100;
if (BASE_BET < 0.01) BASE_BET = 0.01;
var MAX_BET = CONFIG.maxBetPct > 0 ? Math.round(BANKROLL * CONFIG.maxBetPct * 100) / 100 : Infinity;
var VAULT_TARGET = CONFIG.vaultAtPct > 0 ? BANKROLL * CONFIG.vaultAtPct : Infinity;
var STOP_LOSS = BANKROLL * CONFIG.stopLossPct;
```

**Step 3: Write shared state variables**

```js
// --- Shared state ---
var runningProfit = 0;
var peakProfit = 0;
var handsPlayed = 0;
var totalWins = 0;
var totalLosses = 0;
var totalPushes = 0;
var bestWinStreak = 0;
var bestLossStreak = 0;
var currentWinStreak = 0;
var currentLossStreak = 0;
var totalVaulted = 0;
var vaultCount = 0;
var stopped = false;
var lastWasWin = false;     // For progression systems
var lastBetAmount = 0;      // Track actual bet placed (before double)

// --- System-specific state ---
var sysStep = 0;            // Paroli win count / Fibonacci index
var cycleProfit = 0;        // Oscar's Grind cycle tracking
var fibSequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89];
```

**Step 4: Write side bet and initial bet setup**

```js
betSize = BASE_BET;
sideBetPerfectPairs = CONFIG.sideBetPerfectPairs > 0 ? Math.round(BASE_BET * CONFIG.sideBetPerfectPairs * 100) / 100 : 0;
sideBet213 = CONFIG.sideBet213 > 0 ? Math.round(BASE_BET * CONFIG.sideBet213 * 100) / 100 : 0;

log((isSimulationMode ? '[SIM] ' : '[LIVE] ') + 'RAMPART v3.0 ' + CONFIG.system.toUpperCase() + ' | Bal: $' + BANKROLL + ' | Bet: $' + BASE_BET + ' | Max: $' + (MAX_BET === Infinity ? 'none' : MAX_BET.toFixed(2)) + ' | Vault: +$' + (VAULT_TARGET === Infinity ? 'off' : VAULT_TARGET.toFixed(2)) + ' | Stop: -$' + STOP_LOSS.toFixed(2));
if (sideBetPerfectPairs > 0 || sideBet213 > 0) {
    log('Side bets: PP=$' + sideBetPerfectPairs.toFixed(2) + ' 21+3=$' + sideBet213.toFixed(2));
}
```

**Step 5: Verify script loads in Antebot sim**

Paste into Antebot Code Mode, run in simulation. Should see the init log line and start playing with flat bets.

**Step 6: Commit**

```
feat: RAMPART v3.0 config block and bankroll init
```

---

### Task 2: Betting System Dispatcher

**Files:**
- Modify: `scripts/blackjack/rampart.js` (append after state vars)

**Step 1: Write all 6 betting system functions**

Each function receives no args, reads from shared state, returns the next bet size in units (will be multiplied by BASE_BET).

```js
// ============================================================
// BETTING SYSTEMS
// ============================================================

function calcBet_flat() {
    return BASE_BET;
}

function calcBet_dalembert() {
    // +1 unit on loss, -1 unit on win, floor at 1 unit
    // On win when profit >= peak: reset to base
    if (!lastWasWin) {
        return lastBetAmount + BASE_BET;
    }
    if (runningProfit >= peakProfit && runningProfit > 0) {
        return BASE_BET;
    }
    var next = lastBetAmount - BASE_BET;
    if (next < BASE_BET) next = BASE_BET;
    return next;
}

function calcBet_martingale() {
    // Double on loss, reset on win
    if (lastWasWin) {
        return BASE_BET;
    }
    return lastBetAmount * 2;
}

function calcBet_paroli() {
    // Double on win (max 3 consecutive), reset on loss
    if (!lastWasWin) {
        sysStep = 0;
        return BASE_BET;
    }
    sysStep++;
    if (sysStep >= 3) {
        sysStep = 0;
        return BASE_BET;
    }
    return lastBetAmount * 2;
}

function calcBet_oscar() {
    // +1 unit on win (capped to not overshoot +1 unit cycle profit)
    // Same bet on loss. Cycle ends at +1 unit profit.
    if (cycleProfit >= BASE_BET) {
        // Cycle complete, reset
        cycleProfit = 0;
        return BASE_BET;
    }
    if (lastWasWin) {
        var next = lastBetAmount + BASE_BET;
        var cap = BASE_BET - cycleProfit;
        if (cap < BASE_BET) cap = BASE_BET;
        if (next > cap) next = cap;
        return next;
    }
    return lastBetAmount;
}

function calcBet_fibonacci() {
    // Follow fibonacci sequence on loss, step back 2 on win
    if (lastWasWin) {
        sysStep -= 2;
        if (sysStep < 0) sysStep = 0;
    } else {
        sysStep++;
        if (sysStep >= fibSequence.length) sysStep = fibSequence.length - 1;
    }
    return BASE_BET * fibSequence[sysStep];
}

// Dispatcher
var SYSTEMS = {
    flat: calcBet_flat,
    dalembert: calcBet_dalembert,
    martingale: calcBet_martingale,
    paroli: calcBet_paroli,
    oscar: calcBet_oscar,
    fibonacci: calcBet_fibonacci
};

function calcNextBet() {
    var fn = SYSTEMS[CONFIG.system];
    if (!fn) {
        log('ERROR: Unknown system: ' + CONFIG.system);
        return BASE_BET;
    }
    var next = fn();
    // Enforce bounds
    next = Math.round(next * 100) / 100;
    if (next < 0.01) next = 0.01;
    if (next > MAX_BET) next = MAX_BET;
    return next;
}
```

**Step 2: Verify each system computes reasonable values**

Mental walkthrough:
- flat: always BASE_BET -> OK
- dalembert: loss -> +1 unit, win -> -1 unit, floor BASE_BET -> OK
- martingale: loss -> 2x, win -> reset -> OK (MAX_BET caps runaway)
- paroli: 3 wins -> 1x, 2x, 4x, reset -> OK
- oscar: cycle to +1 unit -> OK
- fibonacci: 1,1,2,3,5,8... on loss, back 2 on win -> OK

**Step 3: Commit**

```
feat: add 6 betting system functions with dispatcher
```

---

### Task 3: Main Engine Loop (onBetPlaced)

**Files:**
- Modify: `scripts/blackjack/rampart.js` (append after systems)

**Step 1: Write the onBetPlaced handler**

This is the core loop — processes results, updates state, calls calcNextBet, handles vault and stop.

```js
// ============================================================
// ENGINE HANDLERS
// ============================================================

engine.onBetPlaced(async (lastBet) => {
    if (stopped) {
        betSize = 0;
        return;
    }

    handsPlayed++;

    if (lastBet.win && lastBet.payoutMultiplier > 1) {
        // --- WIN ---
        var wonAmount = lastBet.payout - lastBet.amount;
        runningProfit += wonAmount;
        totalWins++;
        currentWinStreak++;
        currentLossStreak = 0;
        lastWasWin = true;
        if (currentWinStreak > bestWinStreak) bestWinStreak = currentWinStreak;

        // Oscar's cycle tracking
        if (CONFIG.system === 'oscar') {
            cycleProfit += wonAmount;
        }
    } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
        // --- PUSH: don't affect progression ---
        totalPushes++;
        // Don't change lastWasWin — treat push as if hand didn't happen for betting
    } else {
        // --- LOSS ---
        runningProfit -= lastBet.amount;
        totalLosses++;
        currentLossStreak++;
        currentWinStreak = 0;
        lastWasWin = false;
        if (currentLossStreak > bestLossStreak) bestLossStreak = currentLossStreak;

        // Oscar's cycle tracking
        if (CONFIG.system === 'oscar') {
            cycleProfit -= lastBet.amount;
        }
    }

    // Track actual bet amount (before any double)
    lastBetAmount = lastBet.amount;

    // Track peak
    if (runningProfit > peakProfit) peakProfit = runningProfit;

    // --- Vault milestone: vault, reset cycle, keep grinding ---
    if (VAULT_TARGET !== Infinity && runningProfit >= VAULT_TARGET) {
        var vaultAmount = Math.round(runningProfit * 100) / 100;
        totalVaulted += vaultAmount;
        vaultCount++;
        depositToVault(vaultAmount);
        log('VAULT #' + vaultCount + ' +$' + vaultAmount.toFixed(2) + ' | Total: $' + totalVaulted.toFixed(2) + ' | Seed reset | ' + handsPlayed + ' hands');

        // Reset cycle state
        runningProfit = 0;
        peakProfit = 0;
        cycleProfit = 0;
        sysStep = 0;
        lastWasWin = false;
        lastBetAmount = BASE_BET;
        resetSeed();
        betSize = BASE_BET;
        return;
    }

    // --- Stop-loss ---
    if (runningProfit <= -STOP_LOSS) {
        log('STOP LOSS -$' + Math.abs(runningProfit).toFixed(2) + ' (' + (Math.abs(runningProfit) / BANKROLL * 100).toFixed(1) + '%) | ' + handsPlayed + ' hands');
        stopped = true;
        betSize = 0;
        engine.stop();
        return;
    }

    // --- Calculate next bet ---
    betSize = calcNextBet();

    // Update side bets proportionally
    if (CONFIG.sideBetPerfectPairs > 0) {
        sideBetPerfectPairs = Math.round(betSize * CONFIG.sideBetPerfectPairs * 100) / 100;
    }
    if (CONFIG.sideBet213 > 0) {
        sideBet213 = Math.round(betSize * CONFIG.sideBet213 * 100) / 100;
    }

    // --- Periodic status ---
    if (CONFIG.statusEvery > 0 && handsPlayed % CONFIG.statusEvery === 0) {
        log('#' + handsPlayed + ' | P: $' + runningProfit.toFixed(2) + ' | W/L/P: ' + totalWins + '/' + totalLosses + '/' + totalPushes + ' | Bet: $' + betSize + ' | Bal: $' + balance.toFixed(2));
    }
});
```

**Step 2: Verify push handling**

Pushes (`payoutMultiplier <= 1`) don't change `lastWasWin` — this means the betting system sees the push as invisible and bases the next bet on the previous real outcome. This prevents progressions from resetting on ties.

**Step 3: Commit**

```
feat: main onBetPlaced loop with vault-and-continue and stop-loss
```

---

### Task 4: Game Round Handler & Session End

**Files:**
- Modify: `scripts/blackjack/rampart.js` (append after onBetPlaced)

**Step 1: Write onGameRound handler**

```js
engine.onGameRound(function (currentBet, playerHandIndex) {
    if (stopped) return BLACKJACK_STAND;

    var nextAction = blackJackPerfectNextAction(currentBet, playerHandIndex, 'advanced', 'any');

    if (nextAction === BLACKJACK_DOUBLE) {
        betSize *= 2;
    }

    return nextAction;
});
```

**Step 2: Write onBettingStopped handler**

```js
engine.onBettingStopped(function (isManualStop, lastError) {
    playHitSound();
    log('=== RAMPART v3.0 ' + CONFIG.system.toUpperCase() + ' OVER ===');
    log('Hands: ' + handsPlayed + ' | W/L/P: ' + totalWins + '/' + totalLosses + '/' + totalPushes);
    log('Profit: $' + runningProfit.toFixed(2) + ' | Peak: $' + peakProfit.toFixed(2));
    log('Best Win Streak: ' + bestWinStreak + ' | Best Loss Streak: ' + bestLossStreak);
    log('Vaulted: $' + totalVaulted.toFixed(2) + ' (' + vaultCount + ' vaults) | Balance: $' + balance.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
```

**Step 3: Commit**

```
feat: game round handler and session summary
```

---

### Task 5: Integration Test — All Systems

**Files:**
- No new files. Test in Antebot Code Mode simulator.

**Step 1: Test flat system**

Set `CONFIG.system = 'flat'`. Run in sim. Verify:
- Bet size stays constant at BASE_BET
- Vault triggers at +15%
- Stop-loss triggers at -30%
- Summary prints correctly

**Step 2: Test d'Alembert system**

Set `CONFIG.system = 'dalembert'`. Run in sim. Verify:
- Bet increases by 1 unit after loss
- Bet decreases by 1 unit after win
- Bet never goes below BASE_BET
- Resets to BASE_BET when profit >= peak

**Step 3: Test martingale system**

Set `CONFIG.system = 'martingale'`. Run in sim. Verify:
- Bet doubles after loss
- Bet resets to BASE_BET after win
- MAX_BET cap prevents runaway (set maxBetPct to 0.05 for safety)

**Step 4: Test paroli system**

Set `CONFIG.system = 'paroli'`. Run in sim. Verify:
- Bet doubles after win, up to 3 consecutive
- After 3 wins or any loss: reset to BASE_BET

**Step 5: Test oscar system**

Set `CONFIG.system = 'oscar'`. Run in sim. Verify:
- Bet stays same after loss
- Bet increases by 1 unit after win
- Cycle resets when cycleProfit >= BASE_BET

**Step 6: Test fibonacci system**

Set `CONFIG.system = 'fibonacci'`. Run in sim. Verify:
- Bet follows 1,1,2,3,5,8... sequence on consecutive losses
- Steps back 2 on win
- MAX_BET cap prevents runaway

**Step 7: Test side bets**

Set `CONFIG.sideBetPerfectPairs = 2`. Run any system. Verify:
- sideBetPerfectPairs = 2x betSize
- Side bets scale with progression

**Step 8: Commit**

```
test: verify all 6 betting systems in Antebot simulator
```

---

### Task 6: Edge Cases & Polish

**Files:**
- Modify: `scripts/blackjack/rampart.js`

**Step 1: Handle first-hand edge case for d'Alembert/Oscar**

On the very first hand, `lastBetAmount` is 0 (not yet set from a result). Fix by initializing `lastBetAmount = BASE_BET` and setting it BEFORE the system calculates:

```js
// In state init section:
var lastBetAmount = BASE_BET;
```

This is already correct because `lastBetAmount` gets set to `lastBet.amount` after each hand, and the first hand uses `betSize = BASE_BET`.

Actually, the issue is that `lastBet.amount` on the first call to `onBetPlaced` IS the first bet's amount. So `lastBetAmount = lastBet.amount` works correctly — the system functions will use it for the NEXT bet calculation. No fix needed, but verify this in testing.

**Step 2: Handle double-down bet tracking**

When `BLACKJACK_DOUBLE` fires, `betSize *= 2` happens in `onGameRound`. But `lastBet.amount` in the next `onBetPlaced` reflects the doubled amount. This is correct for profit/loss tracking, but for progression purposes we want the BASE bet (pre-double).

Fix: track the intended bet separately.

```js
// Add after calcNextBet() call:
var intendedBet = betSize;  // Store pre-double amount
```

Then in onBetPlaced, use `intendedBet` for `lastBetAmount` instead of `lastBet.amount`:

Actually, simpler: `lastBetAmount` should be set to `betSize` BEFORE the hand plays (i.e., at the end of onBetPlaced when we set the next bet). This way it captures the intended bet, not the doubled one.

```js
// At end of onBetPlaced, after calcNextBet():
betSize = calcNextBet();
lastBetAmount = betSize;  // Track intended bet for progression
```

And remove the `lastBetAmount = lastBet.amount;` line from the win/loss tracking section.

**Step 3: Commit**

```
fix: track intended bet for progression, not doubled amount
```

---

### Task 7: Archive Old Scripts & Final Commit

**Files:**
- Move: `scripts/blackjack/oscars-grind.js` -> `scripts/blackjack/_archive/oscars-grind.js`
- Move: `scripts/blackjack/variance-hunter-v1.js` -> `scripts/blackjack/_archive/variance-hunter-v1.js`
- Move: `scripts/blackjack/variance-hunter-v2.js` -> `scripts/blackjack/_archive/variance-hunter-v2.js`

**Step 1: Create archive directory and move old scripts**

```bash
mkdir -p scripts/blackjack/_archive
mv scripts/blackjack/oscars-grind.js scripts/blackjack/_archive/
mv scripts/blackjack/variance-hunter-v1.js scripts/blackjack/_archive/
mv scripts/blackjack/variance-hunter-v2.js scripts/blackjack/_archive/
```

**Step 2: Final commit**

```
chore: archive old blackjack scripts, RAMPART v3.0 is the unified engine
```

---

## Summary

| Task | Description | Key Output |
|------|-------------|------------|
| 1 | Config block & bankroll init | User-facing config API |
| 2 | 6 betting system functions | calcNextBet() dispatcher |
| 3 | Main engine loop | onBetPlaced with vault-and-continue |
| 4 | Game round & session end | Perfect strategy + summary |
| 5 | Integration test all systems | Verify in Antebot sim |
| 6 | Edge cases (double-down tracking) | Correct progression after doubles |
| 7 | Archive old scripts | Clean directory |

## What's NOT in Scope

- **B2B detection** (P1) — deferred. Can be added as a stop condition later.
- **Streak-triggered actions** (P2) — deferred. Current streak tracking is sufficient for logging.
- **Custom bet matrix** — using built-in `blackJackPerfectNextAction('advanced', 'any')` which is equivalent. The community d'Alembert's manual matrix is unnecessary overhead.
- **Simulation batch runner** (like SIEGE's 250-sample sim) — deferred. Can port from SIEGE later.
