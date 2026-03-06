// === Dice Momentum Rider — Streak Amplifier ===
// 33% chance / 3.0x payout. 0.5% base, escalate 1.8x per consecutive win.
// Losing rolls cost $0.50 (base). A 4-win streak nets ~$12.
// Immediate reset to base on any loss.
// Profit protection: once up 10%, cap bets at 50% of running profit.
//
// Target: +30% bankroll | Stop: -25% bankroll | Max: 200 rolls

// --- Mode ---
var SIM_MODE = true;

if (SIM_MODE) {
    setSimulationBalance(100);
    resetSeed();
    resetStats();
    clearConsole();
}

game = 'dice';

// --- Dice Config ---
chance = 33;
target = chanceToMultiplier(chance);
betHigh = true;

// --- Strategy Config ---
var BASE_PCT = 0.005;         // 0.5% of bankroll
var ESCALATE = 1.8;           // Multiply bet by 1.8x per consecutive win
var MAX_BET_PCT = 0.05;       // Cap at 5% of bankroll
var PROFIT_PROTECT_THRESHOLD = 0.10;  // Activate protection at +10%
var PROFIT_PROTECT_CAP = 0.50;        // Cap bets at 50% of running profit
var TARGET_PCT = 0.30;        // +30% profit target
var STOP_LOSS_PCT = 0.25;     // -25% stop loss
var MAX_ROLLS = 200;

// --- Sim Config ---
var SIM_SAMPLES = 250;        // Number of sessions to simulate

// --- Dynamic bankroll ---
var BANKROLL = SIM_MODE ? 100 : Math.floor(balance * 100) / 100;
var BASE_BET = Math.round(BANKROLL * BASE_PCT * 100) / 100;
if (BASE_BET < 0.01) BASE_BET = 0.01;
var MAX_BET = Math.round(BANKROLL * MAX_BET_PCT * 100) / 100;
var TARGET = BANKROLL * TARGET_PCT;
var STOP_LOSS = BANKROLL * STOP_LOSS_PCT;

// --- Session state ---
var runningProfit = 0;
var sessionRolls = 0;
var stopped = false;
var wins = 0;
var losses = 0;
var consecutiveWins = 0;
var bestStreak = 0;
var exitReason = '';

// --- Sim tracking ---
var currentSample = 0;
var sampleResults = [];
var totalSamples = SIM_MODE ? SIM_SAMPLES : 1;

function resetSession() {
    runningProfit = 0;
    sessionRolls = 0;
    wins = 0;
    losses = 0;
    consecutiveWins = 0;
    bestStreak = 0;
    exitReason = '';
}

function endSession(reason) {
    exitReason = reason;
    currentSample++;
    sampleResults.push({
        profit: runningProfit,
        rolls: sessionRolls,
        exit: reason,
        wins: wins,
        losses: losses,
        bestStreak: bestStreak
    });

    if (SIM_MODE) {
        log('S' + currentSample + '/' + totalSamples + ' ' + reason + ' | P: $' + runningProfit.toFixed(2) + ' | ' + sessionRolls + 'r | ' + wins + 'W/' + losses + 'L | streak: ' + bestStreak);
    }

    if (currentSample >= totalSamples) {
        stopped = true;
        betSize = 0;
        engine.stop();
        return;
    }

    resetSession();
    betSize = BASE_BET;
}

function calcNextBet() {
    var nextBet;
    if (consecutiveWins === 0) {
        nextBet = BASE_BET;
    } else {
        nextBet = BASE_BET * Math.pow(ESCALATE, consecutiveWins);
        nextBet = Math.round(nextBet * 100) / 100;
    }

    if (nextBet > MAX_BET) nextBet = MAX_BET;

    if (runningProfit >= BANKROLL * PROFIT_PROTECT_THRESHOLD) {
        var profitCap = Math.round(runningProfit * PROFIT_PROTECT_CAP * 100) / 100;
        if (profitCap < BASE_BET) profitCap = BASE_BET;
        if (nextBet > profitCap) nextBet = profitCap;
    }

    if (nextBet < 0.01) nextBet = 0.01;
    return nextBet;
}

betSize = BASE_BET;

log((SIM_MODE ? '[SIM x' + totalSamples + '] ' : '[LIVE] ') + 'Momentum Rider | Balance: $' + BANKROLL + ' | Base: $' + BASE_BET + ' | Max: $' + MAX_BET + ' | Target: +$' + TARGET.toFixed(2) + ' | Stop: -$' + STOP_LOSS.toFixed(2));

engine.onBetPlaced(async (lastBet) => {
    if (stopped) {
        betSize = 0;
        return;
    }

    sessionRolls++;

    if (lastBet.win) {
        wins++;
        consecutiveWins++;
        if (consecutiveWins > bestStreak) bestStreak = consecutiveWins;
        var wonAmount = lastBet.payout - lastBet.amount;
        runningProfit += wonAmount;

        if (!SIM_MODE && consecutiveWins >= 2) {
            log('STREAK x' + consecutiveWins + ' +$' + wonAmount.toFixed(2) + ' (bet: $' + lastBet.amount.toFixed(2) + ') | Profit: $' + runningProfit.toFixed(2) + ' | Roll #' + sessionRolls);
        }
    } else {
        losses++;
        runningProfit -= lastBet.amount;

        if (!SIM_MODE && consecutiveWins >= 3) {
            log('STREAK ENDED at x' + consecutiveWins + ' | Profit: $' + runningProfit.toFixed(2));
        }
        consecutiveWins = 0;
    }

    // --- Check exit conditions ---
    if (runningProfit >= TARGET) {
        endSession('TARGET');
        return;
    }

    if (runningProfit <= -STOP_LOSS) {
        endSession('STOP_LOSS');
        return;
    }

    if (sessionRolls >= MAX_ROLLS) {
        endSession('MAX_ROLLS');
        return;
    }

    betSize = calcNextBet();

    if (!SIM_MODE && sessionRolls % 50 === 0) {
        log('--- #' + sessionRolls + ' | P: $' + runningProfit.toFixed(2) + ' | Streak: ' + consecutiveWins + ' | Best: ' + bestStreak + ' | Bet: $' + betSize + ' | W/L: ' + wins + '/' + losses + ' ---');
    }
});

engine.onBettingStopped(function (isManualStop, lastError) {
    playHitSound();

    if (SIM_MODE && sampleResults.length > 1) {
        var totalProfit = 0;
        var totalRolls = 0;
        var sessionWins = 0;
        var sessionLosses = 0;
        var bestProfit = -Infinity;
        var worstProfit = Infinity;
        var allStreaks = 0;
        var exitCounts = {};
        var profits = [];
        var winProfits = [];
        var lossProfits = [];

        var cumPL = 0;
        var eqPeak = 0;
        var maxDD = 0;
        var peakBal = BANKROLL;
        var troughBal = BANKROLL;

        for (var i = 0; i < sampleResults.length; i++) {
            var s = sampleResults[i];
            totalProfit += s.profit;
            totalRolls += s.rolls;
            profits.push(s.profit);
            if (s.profit > bestProfit) bestProfit = s.profit;
            if (s.profit < worstProfit) worstProfit = s.profit;
            if (s.profit > 0) { sessionWins++; winProfits.push(s.profit); }
            else { sessionLosses++; lossProfits.push(s.profit); }
            if (s.bestStreak > allStreaks) allStreaks = s.bestStreak;
            exitCounts[s.exit] = (exitCounts[s.exit] || 0) + 1;

            cumPL += s.profit;
            if (cumPL > eqPeak) eqPeak = cumPL;
            var dd = eqPeak - cumPL;
            if (dd > maxDD) maxDD = dd;
            var bal = BANKROLL + cumPL;
            if (bal > peakBal) peakBal = bal;
            if (bal < troughBal) troughBal = bal;
        }

        profits.sort(function (a, b) { return a - b; });
        var n = profits.length;
        var median = n % 2 === 1 ? profits[Math.floor(n / 2)] : (profits[n / 2 - 1] + profits[n / 2]) / 2;
        var p10 = profits[Math.floor(n * 0.10)];
        var p25 = profits[Math.floor(n * 0.25)];
        var p75 = profits[Math.floor(n * 0.75)];
        var p90 = profits[Math.floor(n * 0.90)];

        var avgWin = winProfits.length > 0 ? winProfits.reduce(function (a, b) { return a + b; }, 0) / winProfits.length : 0;
        var avgLoss = lossProfits.length > 0 ? lossProfits.reduce(function (a, b) { return a + b; }, 0) / lossProfits.length : 0;
        var avgProfit = totalProfit / n;
        var avgRolls = totalRolls / n;

        log('');
        log('========== MOMENTUM RIDER SIM RESULTS (' + n + ' sessions) ==========');
        log('Win Rate: ' + sessionWins + '/' + n + ' (' + (sessionWins / n * 100).toFixed(1) + '%) | PF: ' + (sessionWins > 0 && sessionLosses > 0 ? (sessionWins / sessionLosses).toFixed(2) : 'N/A'));
        log('Total P&L: $' + totalProfit.toFixed(2) + ' | Avg: $' + avgProfit.toFixed(2) + ' | Median: $' + median.toFixed(2));
        log('Avg Win: +$' + avgWin.toFixed(2) + ' | Avg Loss: $' + avgLoss.toFixed(2) + ' | Ratio: ' + (avgLoss !== 0 ? (avgWin / Math.abs(avgLoss)).toFixed(2) : 'N/A'));
        log('Best: +$' + bestProfit.toFixed(2) + ' | Worst: $' + worstProfit.toFixed(2));
        log('P10: $' + p10.toFixed(2) + ' | P25: $' + p25.toFixed(2) + ' | P75: $' + p75.toFixed(2) + ' | P90: $' + p90.toFixed(2));
        log('Peak Bal: $' + peakBal.toFixed(2) + ' | Trough Bal: $' + troughBal.toFixed(2) + ' | Max Drawdown: $' + maxDD.toFixed(2) + ' (' + (maxDD / BANKROLL * 100).toFixed(1) + '%)');
        log('Avg Rolls: ' + avgRolls.toFixed(0) + ' | Best Streak: ' + allStreaks + ' | Exits: ' + JSON.stringify(exitCounts));
        log('Balance: $' + balance.toFixed(2));
        log('====================================================================');
    } else {
        log('=== SESSION OVER ===');
        log('Mode: ' + (SIM_MODE ? 'SIMULATION' : 'LIVE'));
        log('Exit: ' + (exitReason || (isManualStop ? 'MANUAL' : 'UNKNOWN')));
        log('Rolls: ' + sessionRolls + ' | Profit: $' + runningProfit.toFixed(2) + ' (' + (runningProfit >= 0 ? '+' : '') + (runningProfit / BANKROLL * 100).toFixed(1) + '%)');
        log('W/L: ' + wins + '/' + losses + ' (' + (sessionRolls > 0 ? (wins / sessionRolls * 100).toFixed(1) : '0') + '%) | Best streak: ' + bestStreak);
        log('Balance: $' + balance.toFixed(2));
    }

    if (lastError) log('Error: ' + lastError);
});
