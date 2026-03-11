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

    // Side bets (multiplier of base bet, 0 = disabled)
    sideBetPerfectPairs: 0,
    sideBet213: 0,

    // Logging
    statusEvery: 50          // Log status every N hands (0 = disabled)
};

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

// --- Dynamic bankroll ---
var BANKROLL = isSimulationMode ? 100 : Math.floor(balance * 100) / 100;
var BASE_BET = Math.round(BANKROLL * CONFIG.baseBetPct * 100) / 100;
if (BASE_BET < 0.01) BASE_BET = 0.01;
var MAX_BET = CONFIG.maxBetPct > 0 ? Math.round(BANKROLL * CONFIG.maxBetPct * 100) / 100 : Infinity;
var VAULT_TARGET = CONFIG.vaultAtPct > 0 ? BANKROLL * CONFIG.vaultAtPct : Infinity;
var STOP_LOSS = BANKROLL * CONFIG.stopLossPct;

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
var lastWasWin = false;
var lastBetAmount = BASE_BET;

// --- System-specific state ---
var sysStep = 0;
var cycleProfit = 0;
var fibSequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89];

// --- Init bets ---
betSize = BASE_BET;
sideBetPerfectPairs = CONFIG.sideBetPerfectPairs > 0 ? Math.round(BASE_BET * CONFIG.sideBetPerfectPairs * 100) / 100 : 0;
sideBet213 = CONFIG.sideBet213 > 0 ? Math.round(BASE_BET * CONFIG.sideBet213 * 100) / 100 : 0;

log((isSimulationMode ? '[SIM] ' : '[LIVE] ') + 'RAMPART v3.0 ' + CONFIG.system.toUpperCase() + ' | Bal: $' + BANKROLL + ' | Bet: $' + BASE_BET + ' | Max: $' + (MAX_BET === Infinity ? 'none' : MAX_BET.toFixed(2)) + ' | Vault: +$' + (VAULT_TARGET === Infinity ? 'off' : VAULT_TARGET.toFixed(2)) + ' | Stop: -$' + STOP_LOSS.toFixed(2));
if (sideBetPerfectPairs > 0 || sideBet213 > 0) {
    log('Side bets: PP=$' + sideBetPerfectPairs.toFixed(2) + ' 21+3=$' + sideBet213.toFixed(2));
}

// ============================================================
// BETTING SYSTEMS
// ============================================================

function calcBet_flat() {
    return BASE_BET;
}

function calcBet_dalembert() {
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
    if (lastWasWin) {
        return BASE_BET;
    }
    return lastBetAmount * 2;
}

function calcBet_paroli() {
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
    if (cycleProfit >= BASE_BET) {
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
    if (lastWasWin) {
        sysStep -= 2;
        if (sysStep < 0) sysStep = 0;
    } else {
        sysStep++;
        if (sysStep >= fibSequence.length) sysStep = fibSequence.length - 1;
    }
    return BASE_BET * fibSequence[sysStep];
}

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
    next = Math.round(next * 100) / 100;
    if (next < 0.01) next = 0.01;
    if (next > MAX_BET) next = MAX_BET;
    return next;
}

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

        if (CONFIG.system === 'oscar') {
            cycleProfit += wonAmount;
        }
    } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
        // --- PUSH: invisible to progression ---
        totalPushes++;
    } else {
        // --- LOSS ---
        runningProfit -= lastBet.amount;
        totalLosses++;
        currentLossStreak++;
        currentWinStreak = 0;
        lastWasWin = false;
        if (currentLossStreak > bestLossStreak) bestLossStreak = currentLossStreak;

        if (CONFIG.system === 'oscar') {
            cycleProfit -= lastBet.amount;
        }
    }

    // Track peak
    if (runningProfit > peakProfit) peakProfit = runningProfit;

    // --- Vault milestone: vault, reset cycle, keep grinding ---
    if (VAULT_TARGET !== Infinity && runningProfit >= VAULT_TARGET) {
        var vaultAmount = Math.round(runningProfit * 100) / 100;
        totalVaulted += vaultAmount;
        vaultCount++;
        depositToVault(vaultAmount);
        log('VAULT #' + vaultCount + ' +$' + vaultAmount.toFixed(2) + ' | Total: $' + totalVaulted.toFixed(2) + ' | Seed reset | ' + handsPlayed + ' hands');

        runningProfit = 0;
        peakProfit = 0;
        cycleProfit = 0;
        sysStep = 0;
        lastWasWin = false;
        lastBetAmount = BASE_BET;
        resetSeed();
        betSize = BASE_BET;
        if (CONFIG.sideBetPerfectPairs > 0) {
            sideBetPerfectPairs = Math.round(BASE_BET * CONFIG.sideBetPerfectPairs * 100) / 100;
        }
        if (CONFIG.sideBet213 > 0) {
            sideBet213 = Math.round(BASE_BET * CONFIG.sideBet213 * 100) / 100;
        }
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
    lastBetAmount = betSize;

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

engine.onGameRound(function (currentBet, playerHandIndex) {
    if (stopped) return BLACKJACK_STAND;

    var nextAction = blackJackPerfectNextAction(currentBet, playerHandIndex, 'advanced', 'any');

    if (nextAction === BLACKJACK_DOUBLE) {
        betSize *= 2;
    }

    return nextAction;
});

engine.onBettingStopped(function (isManualStop, lastError) {
    playHitSound();
    log('=== RAMPART v3.0 ' + CONFIG.system.toUpperCase() + ' OVER ===');
    log('Hands: ' + handsPlayed + ' | W/L/P: ' + totalWins + '/' + totalLosses + '/' + totalPushes);
    log('Profit: $' + runningProfit.toFixed(2) + ' | Peak: $' + peakProfit.toFixed(2));
    log('Best Win Streak: ' + bestWinStreak + ' | Best Loss Streak: ' + bestLossStreak);
    log('Vaulted: $' + totalVaulted.toFixed(2) + ' (' + vaultCount + ' vaults) | Balance: $' + balance.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
