// === RAMPART v2.1 — Blackjack Flat Bet Grind ===
// Pure flat bet + advanced perfect strategy.
// No progression — lowest variance, survive longest.
// At +15%: vault profits, reset seed, keep grinding.
// Stop-loss at -30%. Only stops on loss or max hands.

if (isSimulationMode) {
    setSimulationBalance(100);
    resetSeed();
    resetStats();
    clearConsole();
}

game = 'blackjack';

// --- Config ---
var BASE_PCT = 0.01;           // 1% of bankroll flat bet
var WALK_AWAY_PCT = 0.15;      // Walk away at +15% (take small bites)
var STOP_LOSS_PCT = 0.30;      // Stop at -30% (wider rope to recover)
// var MAX_HANDS = 500;         // Safety cap (disabled)

// --- Dynamic bankroll ---
var BANKROLL = isSimulationMode ? 100 : Math.floor(balance * 100) / 100;
var FLAT_BET = Math.round(BANKROLL * BASE_PCT * 100) / 100;
if (FLAT_BET < 0.01) FLAT_BET = 0.01;
var WALK_AWAY = BANKROLL * WALK_AWAY_PCT;
var STOP_LOSS = BANKROLL * STOP_LOSS_PCT;

// --- State ---
var runningProfit = 0;
var peakProfit = 0;
var handsPlayed = 0;
var totalWins = 0;
var totalLosses = 0;
var totalPushes = 0;
var bestStreak = 0;
var currentWinStreak = 0;
var totalVaulted = 0;
var stopped = false;

betSize = FLAT_BET;
sideBetPerfectPairs = 0;
sideBet213 = 0;

log((isSimulationMode ? '[SIM] ' : '[LIVE] ') + 'RAMPART v2.1 FLAT | Bal: $' + BANKROLL + ' | Bet: $' + FLAT_BET + ' | Vault at: +$' + WALK_AWAY.toFixed(2) + ' | Stop: -$' + STOP_LOSS.toFixed(2));

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
        if (currentWinStreak > bestStreak) bestStreak = currentWinStreak;
    } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
        // --- PUSH ---
        totalPushes++;
        currentWinStreak = 0;
    } else {
        // --- LOSS ---
        runningProfit -= lastBet.amount;
        totalLosses++;
        currentWinStreak = 0;
    }

    // Track peak
    if (runningProfit > peakProfit) peakProfit = runningProfit;

    // --- Profit milestone: vault, reset seed, keep grinding ---
    if (runningProfit >= WALK_AWAY) {
        var vaultAmount = Math.round(runningProfit * 100) / 100;
        totalVaulted += vaultAmount;
        depositToVault(vaultAmount);
        runningProfit = 0;
        peakProfit = 0;
        resetSeed();
        betSize = FLAT_BET;
        log('VAULT +$' + vaultAmount.toFixed(2) + ' | Total: $' + totalVaulted.toFixed(2) + ' | Seed reset | ' + handsPlayed + ' hands');
        return;
    }

    // --- Stop-loss ---
    if (runningProfit <= -STOP_LOSS) {
        log('STOP LOSS -$' + Math.abs(runningProfit).toFixed(2) + ' | ' + handsPlayed + ' hands');
        stopped = true;
        betSize = 0;
        engine.stop();
        return;
    }

    // Always flat bet
    betSize = FLAT_BET;

    // Periodic status
    if (handsPlayed % 50 === 0) {
        log('#' + handsPlayed + ' | P: $' + runningProfit.toFixed(2) + ' | W/L/P: ' + totalWins + '/' + totalLosses + '/' + totalPushes + ' | Bal: $' + balance.toFixed(2));
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
    log('=== RAMPART v2.1 OVER ===');
    log('Hands: ' + handsPlayed + ' | W/L/P: ' + totalWins + '/' + totalLosses + '/' + totalPushes);
    log('Profit: $' + runningProfit.toFixed(2) + ' | Peak: $' + peakProfit.toFixed(2) + ' | Best Streak: ' + bestStreak);
    log('Vaulted: $' + totalVaulted.toFixed(2) + ' | Balance: $' + balance.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
