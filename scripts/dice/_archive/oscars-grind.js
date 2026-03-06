// === Dice Oscar's Grind ===
// Exact Wikipedia algorithm: https://en.wikipedia.org/wiki/Oscar%27s_grind
// On loss: keep same bet. On win: increase by 1 unit (capped to not overshoot).
// Cycle ends at +1 unit profit, then reset.
//
// Dice edge: ~1% house edge at 50% win chance (payout 1.98x)
// We use 52% win chance (payout ~1.9038x) for slightly more frequent wins
// at the cost of slightly lower payout per win.

// --- Mode ---
var SIM_MODE = true;  // Set to false for live betting

if (SIM_MODE) {
    resetStats();
    resetSeed();
}

game = 'dice';

// --- Dice Config ---
chance = 52;          // 52% win probability
isOver = true;        // Roll over

// --- Strategy Config ---
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

log((SIM_MODE ? '[SIM] ' : '[LIVE] ') + 'Dice Oscar Grind | Balance: $' + BANKROLL + ' | Unit: $' + UNIT + ' | Stop: -$' + STOP_LOSS.toFixed(2) + ' | Chance: ' + chance + '%');

// --- State ---
var cycleProfit = 0;
var cyclesCompleted = 0;
var runningProfit = 0;
var totalVaulted = 0;
var rollsPlayed = 0;
var peakProfit = 0;
var seedResetAt = 0;
var stopped = false;
var wins = 0;
var losses = 0;

engine.onBetPlaced(async (lastBet) => {
    if (stopped) {
        betSize = 0;
        return;
    }

    rollsPlayed++;

    if (lastBet._win) {
        // --- WIN ---
        wins++;
        var wonAmount = lastBet._payout - lastBet._amount;
        runningProfit += wonAmount;
        cycleProfit += wonAmount;

        if (cycleProfit >= UNIT) {
            // Cycle complete
            cyclesCompleted++;
            log('CYCLE #' + cyclesCompleted + ' +$' + cycleProfit.toFixed(4) + ' | Total: $' + runningProfit.toFixed(2) + ' | Bal: $' + balance.toFixed(2));
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
    } else {
        // --- LOSS: keep same bet size (Oscar's core rule) ---
        losses++;
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
        log('VAULT $' + toVault + ' | Total: $' + totalVaulted + ' | Roll #' + rollsPlayed);
    }

    // --- Stop on 30% drawdown ---
    if (runningProfit <= -STOP_LOSS) {
        log('STOP: Down $' + Math.abs(runningProfit).toFixed(2) + ' (' + (Math.abs(runningProfit) / BANKROLL * 100).toFixed(1) + '%) after ' + rollsPlayed + ' rolls');
        log('Cycles: ' + cyclesCompleted + ' | Vaulted: $' + totalVaulted + ' | Peak: $' + peakProfit.toFixed(2));
        log('W/L: ' + wins + '/' + losses + ' (' + (wins / rollsPlayed * 100).toFixed(1) + '%)');
        stopped = true;
        betSize = 0;
        stop();
        return;
    }

    // Status every 500 rolls (dice is much faster than blackjack)
    if (rollsPlayed % 500 === 0) {
        log('--- #' + rollsPlayed + ' | P: $' + runningProfit.toFixed(2) + ' | Cycles: ' + cyclesCompleted + ' | CycleP: $' + cycleProfit.toFixed(4) + ' | Bet: $' + betSize + ' | W/L: ' + wins + '/' + losses + ' | Bal: $' + balance.toFixed(2) + ' ---');
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log('=== SESSION OVER ===');
    log('Mode: ' + (SIM_MODE ? 'SIMULATION' : 'LIVE'));
    log('Rolls: ' + rollsPlayed + ' | Profit: $' + runningProfit.toFixed(2) + ' | Cycles: ' + cyclesCompleted + ' | Vaulted: $' + totalVaulted);
    log('Peak: $' + peakProfit.toFixed(2) + ' | W/L: ' + wins + '/' + losses + ' (' + (rollsPlayed > 0 ? (wins / rollsPlayed * 100).toFixed(1) : '0') + '%)');
    log('Final balance: $' + balance.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
