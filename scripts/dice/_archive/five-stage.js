// === Dice Five-Stage Progressive ===
// Inspired by forum "Five-Stage Dice" strategy (thread 817)
// 5 phases with increasing bet sizes, each targeting 2x return.
// Falls back to base phase on loss streak. Advances on cycle completion.
// Combined with seed resets and vaulting for variance hunting.
//
// Phase 1: 1 unit base, grind cycles
// Phase 2: 2 units, unlock after 5 cycles
// Phase 3: 4 units, unlock after 15 cycles
// Phase 4: 8 units, unlock after 30 cycles
// Phase 5: 16 units, unlock after 50 cycles
// On 3 consecutive losses in any phase > 1, drop back one phase.

// --- Mode ---
var SIM_MODE = true;

if (SIM_MODE) {
    resetStats();
    resetSeed();
}

game = 'dice';

// --- Dice Config ---
chance = 52;          // 52% win probability
isOver = true;

// --- Strategy Config ---
var BET_PCT = 0.0025;                        // 0.25% of bankroll per unit
var STOP_LOSS_PCT = 0.30;
var VAULT_EVERY = 5;
var SEED_RESET_INTERVAL = 100;

// --- Phase definitions ---
var PHASE_MULTIPLIERS = [1, 2, 4, 8, 16];
var PHASE_UNLOCK_CYCLES = [0, 5, 15, 30, 50];
var PHASE_DROP_LOSSES = 3;                   // Drop phase after N consecutive losses

// --- Dynamic bankroll ---
var BANKROLL = SIM_MODE ? 100 : Math.floor(balance * 100) / 100;
var UNIT = Math.round(BANKROLL * BET_PCT * 100) / 100;
if (UNIT < 0.01) UNIT = 0.01;
var STOP_LOSS = BANKROLL * STOP_LOSS_PCT;

// --- State ---
var currentPhase = 0;
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
var consecutiveLosses = 0;

var phaseBet = UNIT * PHASE_MULTIPLIERS[currentPhase];
betSize = phaseBet;

log((SIM_MODE ? '[SIM] ' : '[LIVE] ') + 'Five-Stage Dice | Balance: $' + BANKROLL + ' | Unit: $' + UNIT + ' | Stop: -$' + STOP_LOSS.toFixed(2) + ' | Phase: 1');

engine.onBetPlaced(async (lastBet) => {
    if (stopped) {
        betSize = 0;
        return;
    }

    rollsPlayed++;

    if (lastBet._win) {
        // --- WIN ---
        wins++;
        consecutiveLosses = 0;
        var wonAmount = lastBet._payout - lastBet._amount;
        runningProfit += wonAmount;
        cycleProfit += wonAmount;

        var cycleTarget = UNIT * PHASE_MULTIPLIERS[currentPhase];

        if (cycleProfit >= cycleTarget) {
            // Cycle complete
            cyclesCompleted++;

            // Check phase advancement
            var maxPhase = 0;
            for (var p = PHASE_MULTIPLIERS.length - 1; p >= 0; p--) {
                if (cyclesCompleted >= PHASE_UNLOCK_CYCLES[p]) {
                    maxPhase = p;
                    break;
                }
            }
            if (maxPhase > currentPhase) {
                currentPhase = maxPhase;
                log('PHASE UP -> ' + (currentPhase + 1) + ' (x' + PHASE_MULTIPLIERS[currentPhase] + ') after ' + cyclesCompleted + ' cycles');
            }

            log('CYCLE #' + cyclesCompleted + ' [P' + (currentPhase + 1) + '] +$' + cycleProfit.toFixed(4) + ' | Total: $' + runningProfit.toFixed(2) + ' | Bal: $' + balance.toFixed(2));
            cycleProfit = 0;
            phaseBet = UNIT * PHASE_MULTIPLIERS[currentPhase];
            betSize = phaseBet;
        } else {
            // Oscar's rule: increase by 1 phase-unit, cap to not overshoot
            var newBet = betSize + phaseBet;
            var capBet = cycleTarget - cycleProfit;
            betSize = Math.min(newBet, capBet);
            betSize = Math.round(betSize * 100) / 100;
            if (betSize < phaseBet) betSize = phaseBet;
        }
    } else {
        // --- LOSS ---
        losses++;
        consecutiveLosses++;
        runningProfit -= lastBet._amount;
        cycleProfit -= lastBet._amount;

        // Drop phase on consecutive losses
        if (consecutiveLosses >= PHASE_DROP_LOSSES && currentPhase > 0) {
            currentPhase--;
            phaseBet = UNIT * PHASE_MULTIPLIERS[currentPhase];
            betSize = phaseBet;
            cycleProfit = 0;  // Reset cycle on phase drop
            consecutiveLosses = 0;
            log('PHASE DOWN -> ' + (currentPhase + 1) + ' (x' + PHASE_MULTIPLIERS[currentPhase] + ') after ' + PHASE_DROP_LOSSES + ' losses');
        }
        // Otherwise keep same bet (Oscar's rule)
    }

    // Track peak
    if (runningProfit > peakProfit) {
        peakProfit = runningProfit;
    }

    // --- Reset seed at milestones ---
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

    // --- Stop on drawdown ---
    if (runningProfit <= -STOP_LOSS) {
        log('STOP: Down $' + Math.abs(runningProfit).toFixed(2) + ' (' + (Math.abs(runningProfit) / BANKROLL * 100).toFixed(1) + '%) after ' + rollsPlayed + ' rolls');
        log('Cycles: ' + cyclesCompleted + ' | Phase: ' + (currentPhase + 1) + ' | Vaulted: $' + totalVaulted + ' | Peak: $' + peakProfit.toFixed(2));
        log('W/L: ' + wins + '/' + losses + ' (' + (wins / rollsPlayed * 100).toFixed(1) + '%)');
        stopped = true;
        betSize = 0;
        stop();
        return;
    }

    // Status every 500 rolls
    if (rollsPlayed % 500 === 0) {
        log('--- #' + rollsPlayed + ' | P: $' + runningProfit.toFixed(2) + ' | Phase: ' + (currentPhase + 1) + ' | Cycles: ' + cyclesCompleted + ' | Bet: $' + betSize + ' | W/L: ' + wins + '/' + losses + ' | Bal: $' + balance.toFixed(2) + ' ---');
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log('=== SESSION OVER ===');
    log('Mode: ' + (SIM_MODE ? 'SIMULATION' : 'LIVE'));
    log('Rolls: ' + rollsPlayed + ' | Profit: $' + runningProfit.toFixed(2) + ' | Cycles: ' + cyclesCompleted + ' | Phase: ' + (currentPhase + 1) + ' | Vaulted: $' + totalVaulted);
    log('Peak: $' + peakProfit.toFixed(2) + ' | W/L: ' + wins + '/' + losses + ' (' + (rollsPlayed > 0 ? (wins / rollsPlayed * 100).toFixed(1) : '0') + '%)');
    log('Final balance: $' + balance.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
