// === Blackjack Oscar's Grind ===
// Exact Wikipedia algorithm: https://en.wikipedia.org/wiki/Oscar%27s_grind
// On loss: keep same bet. On win: increase by 1 unit (capped to not overshoot).
// Cycle ends at +1 unit profit, then reset.

// --- Mode ---
var SIM_MODE = true;  // Set to false for live betting

if (SIM_MODE) {
    resetStats();
    resetSeed();
}

game = 'blackjack';

// --- Config ---
var BET_PCT = 0.0025;                        // 0.25% of bankroll per unit
var STOP_LOSS_PCT = 0.30;                    // Stop at 30% drawdown
var VAULT_EVERY = 5;                         // Vault every $5
var SEED_RESET_INTERVAL = 100;               // Reset seed every 100% profit milestone

// --- Dynamic bankroll ---
var BANKROLL = SIM_MODE ? 100 : Math.floor(balance * 100) / 100;
var UNIT = Math.round(BANKROLL * BET_PCT * 100) / 100;
if (UNIT < 0.01) UNIT = 0.01;
var STOP_LOSS = BANKROLL * STOP_LOSS_PCT;

betSize = UNIT;
sideBetPerfectPairs = 0;
sideBet213 = 0;

log((SIM_MODE ? '[SIM] ' : '[LIVE] ') + 'Oscar Grind | Balance: $' + BANKROLL + ' | Unit: $' + UNIT + ' | Stop: -$' + STOP_LOSS.toFixed(2));

// --- State ---
var cycleProfit = 0;
var cyclesCompleted = 0;
var runningProfit = 0;
var totalVaulted = 0;
var handsPlayed = 0;
var peakProfit = 0;
var seedResetAt = 0;
var stopped = false;

engine.onBetPlaced(async (lastBet) => {
    if (stopped) {
        betSize = 0;
        return;
    }

    handsPlayed++;

    if (lastBet._win && lastBet._payoutMultiplier > 1) {
        // --- WIN ---
        var wonAmount = lastBet._payout - lastBet._amount;
        runningProfit += wonAmount;
        cycleProfit += wonAmount;

        if (cycleProfit >= UNIT) {
            // Cycle complete
            cyclesCompleted++;
            log('CYCLE #' + cyclesCompleted + ' +$' + cycleProfit.toFixed(2) + ' | Total: $' + runningProfit.toFixed(2) + ' | Bal: $' + balance.toFixed(2));
            cycleProfit = 0;
            betSize = UNIT;
        } else {
            // Increase by 1 unit, cap to not overshoot cycle target
            var newBet = betSize + UNIT;
            var capBet = UNIT - cycleProfit;
            betSize = Math.min(newBet, capBet);
            betSize = Math.round(betSize * 100) / 100;
            if (betSize < UNIT) betSize = UNIT;
        }
    } else if (lastBet._win && lastBet._payoutMultiplier <= 1) {
        // Push — keep everything the same
    } else {
        // --- LOSS: keep same bet size ---
        runningProfit -= lastBet._amount;
        cycleProfit -= lastBet._amount;
    }

    // Track peak
    if (runningProfit > peakProfit) {
        peakProfit = runningProfit;
    }

    // --- Reset seed at 100% profit milestones ---
    var profitPct = (runningProfit / BANKROLL) * 100;
    var nextThreshold = seedResetAt + SEED_RESET_INTERVAL;
    if (profitPct >= nextThreshold && nextThreshold > 0) {
        seedResetAt = Math.floor(profitPct / SEED_RESET_INTERVAL) * SEED_RESET_INTERVAL;
        resetSeed();
        log('SEED RESET at ' + profitPct.toFixed(1) + '% profit ($' + runningProfit.toFixed(2) + ')');
    }

    // --- Vault profits ---
    if (runningProfit - totalVaulted >= VAULT_EVERY) {
        var toVault = Math.floor((runningProfit - totalVaulted) / VAULT_EVERY) * VAULT_EVERY;
        totalVaulted += toVault;
        log('VAULT $' + toVault + ' | Total: $' + totalVaulted + ' | Hand #' + handsPlayed);
    }

    // --- Stop on 30% drawdown ---
    if (runningProfit <= -STOP_LOSS) {
        log('STOP: Down $' + Math.abs(runningProfit).toFixed(2) + ' (' + (Math.abs(runningProfit) / BANKROLL * 100).toFixed(1) + '%) after ' + handsPlayed + ' hands');
        log('Cycles: ' + cyclesCompleted + ' | Vaulted: $' + totalVaulted + ' | Peak: $' + peakProfit.toFixed(2));
        stopped = true;
        betSize = 0;
        stop();
        return;
    }

    // Status every 100 hands
    if (handsPlayed % 100 === 0) {
        log('--- #' + handsPlayed + ' | P: $' + runningProfit.toFixed(2) + ' | Cycles: ' + cyclesCompleted + ' | CycleP: $' + cycleProfit.toFixed(2) + ' | Bet: $' + betSize + ' | Bal: $' + balance.toFixed(2) + ' ---');
    }
});

engine.onGameRound((currentBet, playerHandIndex) => {
    if (stopped) {
        return BLACKJACK_STAND;
    }

    var nextAction = blackJackPerfectNextAction(currentBet, playerHandIndex, 'advanced', 'any');

    if (nextAction === BLACKJACK_DOUBLE) {
        betSize *= 2;
    }

    return nextAction;
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log('=== SESSION OVER ===');
    log('Mode: ' + (SIM_MODE ? 'SIMULATION' : 'LIVE'));
    log('Hands: ' + handsPlayed + ' | Profit: $' + runningProfit.toFixed(2) + ' | Cycles: ' + cyclesCompleted + ' | Vaulted: $' + totalVaulted);
    log('Peak: $' + peakProfit.toFixed(2) + ' | Final balance: $' + balance.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
