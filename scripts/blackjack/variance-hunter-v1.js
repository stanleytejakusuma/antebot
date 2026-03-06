// === Blackjack Variance Hunter v1.1 ===
// Perfect strategy + capped martingale + aggressive vaulting
// Only stops on 30% drawdown from initial capital. Otherwise: keep grinding.

// resetStats();
// resetSeed();

game = 'blackjack';

// --- Config ---
const INITIAL_BET = 1;           // $1 base bet
const MAX_BET = 16;              // Cap martingale at $16 (4 doublings)
const BANKROLL = 163;            // Starting capital
const STOP_LOSS_PCT = 0.30;      // Stop if down 30% of initial capital
const STOP_LOSS = BANKROLL * STOP_LOSS_PCT;  // $48.90
const VAULT_EVERY = 10;          // Vault every $10 profit

betSize = INITIAL_BET;
sideBetPerfectPairs = 0;
sideBet213 = 0;

// --- State ---
var lossStreak = 0;
var runningProfit = 0;
var totalVaulted = 0;
var handsPlayed = 0;
var peakProfit = 0;

engine.onBetPlaced(async (lastBet) => {
    handsPlayed++;

    if (lastBet.win) {
        if (lastBet.payoutMultiplier > 1) {
            // Real win - book profit and reset
            runningProfit += lastBet.payout - lastBet.amount;
            lossStreak = 0;
            betSize = INITIAL_BET;
        }
        // Push (1x) - do nothing, keep current bet
    } else {
        runningProfit -= lastBet.amount;
        lossStreak++;

        // Martingale up, but capped
        betSize = Math.min(betSize * 2, MAX_BET);
    }

    // Track peak
    if (runningProfit > peakProfit) {
        peakProfit = runningProfit;
    }

    // --- Vault profits ---
    if (runningProfit - totalVaulted >= VAULT_EVERY) {
        var toVault = Math.floor((runningProfit - totalVaulted) / VAULT_EVERY) * VAULT_EVERY;
        totalVaulted += toVault;
        log('VAULTED $' + toVault + ' | Total vaulted: $' + totalVaulted + ' | Hand #' + handsPlayed);
    }

    // --- Only stop on 30% drawdown from initial capital ---
    if (runningProfit <= -STOP_LOSS) {
        log('STOP LOSS 30%: Down $' + Math.abs(runningProfit).toFixed(2) + ' after ' + handsPlayed + ' hands. Vaulted: $' + totalVaulted + ' | Peak: $' + peakProfit.toFixed(2));
        stop();
        return;
    }

    // Status log every 25 hands
    if (handsPlayed % 25 === 0) {
        log('--- #' + handsPlayed + ' | Profit: $' + runningProfit.toFixed(2) + ' | Vaulted: $' + totalVaulted + ' | Peak: $' + peakProfit.toFixed(2) + ' | Bet: $' + betSize + ' ---');
    } else {
        log('#' + handsPlayed + ' | ' + (lastBet.win ? 'WIN' : 'LOSS') + ' | Streak: ' + lossStreak + ' | P: $' + runningProfit.toFixed(2) + ' | Next: $' + betSize);
    }
});

engine.onGameRound((currentBet, playerHandIndex) => {
    var nextAction = blackJackPerfectNextAction(currentBet, playerHandIndex, 'advanced', 'any');

    if (nextAction === BLACKJACK_DOUBLE) {
        betSize *= 2;
    }

    return nextAction;
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log('=== SESSION OVER ===');
    log('Hands: ' + handsPlayed + ' | Profit: $' + runningProfit.toFixed(2) + ' | Vaulted: $' + totalVaulted + ' | Peak: $' + peakProfit.toFixed(2));
    if (lastError) log('Error: ' + lastError);
});
