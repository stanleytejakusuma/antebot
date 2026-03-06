// === Dice Mean Reversion — Conditional Contrarian ===
// 25% chance / 3.96x payout. 0.3% base, multiplied by recent-loss window.
// Track last 8 rolls. More recent losses → bigger bets. More wins → smaller.
// Profit protection scales down bets as profit grows.
// Creates fat right tail — big wins when recovering from loss clusters.
//
// Target: +25% bankroll | Stop: -20% bankroll | Max: 300 rolls

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
chance = 25;
target = chanceToMultiplier(chance);
betHigh = true;

// --- Strategy Config ---
var BASE_PCT = 0.003;         // 0.3% of bankroll
var WINDOW_SIZE = 8;          // Look at last 8 rolls
var MIN_MULT = 0.5;           // Minimum multiplier (many recent wins)
var MAX_MULT = 3.5;           // Maximum multiplier (many recent losses)
var TARGET_PCT = 0.25;        // +25% profit target
var STOP_LOSS_PCT = 0.20;     // -20% stop loss
var MAX_ROLLS = 300;

// --- Sim Config ---
var SIM_SAMPLES = 250;        // Number of sessions to simulate

// --- Dynamic bankroll ---
var BANKROLL = SIM_MODE ? 100 : Math.floor(balance * 100) / 100;
var BASE_BET = Math.round(BANKROLL * BASE_PCT * 100) / 100;
if (BASE_BET < 0.01) BASE_BET = 0.01;
var TARGET = BANKROLL * TARGET_PCT;
var STOP_LOSS = BANKROLL * STOP_LOSS_PCT;

// --- Session state ---
var runningProfit = 0;
var sessionRolls = 0;
var stopped = false;
var wins = 0;
var losses = 0;
var recentResults = [];
var peakProfit = 0;
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
    recentResults = [];
    peakProfit = 0;
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
        peak: peakProfit
    });

    if (SIM_MODE) {
        log('S' + currentSample + '/' + totalSamples + ' ' + reason + ' | P: $' + runningProfit.toFixed(2) + ' | Peak: $' + peakProfit.toFixed(2) + ' | ' + sessionRolls + 'r | ' + wins + 'W/' + losses + 'L');
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
    var windowLosses = 0;
    for (var i = 0; i < recentResults.length; i++) {
        if (recentResults[i] === 0) windowLosses++;
    }

    var lossRatio = recentResults.length > 0 ? windowLosses / recentResults.length : 0.75;
    var mult = MIN_MULT + (MAX_MULT - MIN_MULT) * lossRatio;

    if (runningProfit > 0) {
        var profitPct = runningProfit / BANKROLL;
        var profitDamper = 1 - (profitPct * 2);
        if (profitDamper < 0.3) profitDamper = 0.3;
        mult = mult * profitDamper;
    }

    var nextBet = Math.round(BASE_BET * mult * 100) / 100;
    if (nextBet < 0.01) nextBet = 0.01;

    var hardCap = Math.round(BANKROLL * 0.03 * 100) / 100;
    if (nextBet > hardCap) nextBet = hardCap;

    return nextBet;
}

betSize = BASE_BET;

log((SIM_MODE ? '[SIM x' + totalSamples + '] ' : '[LIVE] ') + 'Mean Reversion | Balance: $' + BANKROLL + ' | Base: $' + BASE_BET + ' | Window: ' + WINDOW_SIZE + ' | Target: +$' + TARGET.toFixed(2) + ' | Stop: -$' + STOP_LOSS.toFixed(2));

engine.onBetPlaced(async (lastBet) => {
    if (stopped) {
        betSize = 0;
        return;
    }

    sessionRolls++;

    if (lastBet.win) {
        wins++;
        var wonAmount = lastBet.payout - lastBet.amount;
        runningProfit += wonAmount;
        recentResults.push(1);
        if (!SIM_MODE) {
            log('WIN +$' + wonAmount.toFixed(2) + ' (bet: $' + lastBet.amount.toFixed(2) + ') | Profit: $' + runningProfit.toFixed(2) + ' | Roll #' + sessionRolls);
        }
    } else {
        losses++;
        runningProfit -= lastBet.amount;
        recentResults.push(0);
    }

    while (recentResults.length > WINDOW_SIZE) {
        recentResults.shift();
    }

    if (runningProfit > peakProfit) peakProfit = runningProfit;

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
        var windowLosses = 0;
        for (var j = 0; j < recentResults.length; j++) {
            if (recentResults[j] === 0) windowLosses++;
        }
        log('--- #' + sessionRolls + ' | P: $' + runningProfit.toFixed(2) + ' | Peak: $' + peakProfit.toFixed(2) + ' | Window: ' + windowLosses + 'L/' + recentResults.length + ' | Bet: $' + betSize + ' | W/L: ' + wins + '/' + losses + ' ---');
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
        var bestPeak = 0;
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
            if (s.peak > bestPeak) bestPeak = s.peak;
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
        log('========== MEAN REVERSION SIM RESULTS (' + n + ' sessions) ==========');
        log('Win Rate: ' + sessionWins + '/' + n + ' (' + (sessionWins / n * 100).toFixed(1) + '%) | PF: ' + (sessionWins > 0 && sessionLosses > 0 ? (sessionWins / sessionLosses).toFixed(2) : 'N/A'));
        log('Total P&L: $' + totalProfit.toFixed(2) + ' | Avg: $' + avgProfit.toFixed(2) + ' | Median: $' + median.toFixed(2));
        log('Avg Win: +$' + avgWin.toFixed(2) + ' | Avg Loss: $' + avgLoss.toFixed(2) + ' | Ratio: ' + (avgLoss !== 0 ? (avgWin / Math.abs(avgLoss)).toFixed(2) : 'N/A'));
        log('Best: +$' + bestProfit.toFixed(2) + ' | Worst: $' + worstProfit.toFixed(2));
        log('P10: $' + p10.toFixed(2) + ' | P25: $' + p25.toFixed(2) + ' | P75: $' + p75.toFixed(2) + ' | P90: $' + p90.toFixed(2));
        log('Peak Bal: $' + peakBal.toFixed(2) + ' | Trough Bal: $' + troughBal.toFixed(2) + ' | Max Drawdown: $' + maxDD.toFixed(2) + ' (' + (maxDD / BANKROLL * 100).toFixed(1) + '%)');
        log('Avg Rolls: ' + avgRolls.toFixed(0) + ' | Exits: ' + JSON.stringify(exitCounts));
        log('Balance: $' + balance.toFixed(2));
        log('====================================================================');
    } else {
        log('=== SESSION OVER ===');
        log('Mode: ' + (SIM_MODE ? 'SIMULATION' : 'LIVE'));
        log('Exit: ' + (exitReason || (isManualStop ? 'MANUAL' : 'UNKNOWN')));
        log('Rolls: ' + sessionRolls + ' | Profit: $' + runningProfit.toFixed(2) + ' (' + (runningProfit >= 0 ? '+' : '') + (runningProfit / BANKROLL * 100).toFixed(1) + '%)');
        log('Peak: $' + peakProfit.toFixed(2) + ' | W/L: ' + wins + '/' + losses + ' (' + (sessionRolls > 0 ? (wins / sessionRolls * 100).toFixed(1) : '0') + '%) | Expected: 25%');
        log('Balance: $' + balance.toFixed(2));
    }

    if (lastError) log('Error: ' + lastError);
});
