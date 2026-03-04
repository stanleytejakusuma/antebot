// === SIEGE v1.3 — Conglomerate Dice Strategy ===
// Two-tier architecture: inner session loop + outer walk-away layer.
// Combines best features from all 4 strategies:
//   - Sniper: 10% chance / 9.9x payout, 1% base, 50-roll sessions
//   - Momentum: 1.8x streak escalation, profit protection
//   - Ladder: trailing profit lock at 50% of peak
//   - Meta walk-away system across sessions
//
// v1.3 changes (from v1.2):
//   - Auto-vault now calls depositToVault() (engine API) instead of just tracking in memory
//   - Vault widget reflects actual deposits
//
// v1.2 changes (from v1.1 sim data — loss asymmetry fix):
//   - Walk-away lowered: +50% -> +30% (take smaller bites more often)
//   - Cumulative stop-loss: NEW at -30% (was only bankrupt before)
//   - Auto-vault: on walk-away, vault profits and reset bankroll
//   - Report total vaulted amount at end
//
// v1.1 changes (from v1.0):
//   - Session target: +20% -> +15%, trailing lock: 60% -> 50%
//   - Cum trailing lock: 60% -> 40%, min +20% before activation
//   - Max sessions: 30 -> 40
//
// Inner session: +15% target, -10% stop, trailing stop, 50 rolls max
// Outer: +30% walk-away (vault), -30% cum stop, cum trailing (40% after +20%), 40 sessions
//
// Each sim sample = one full multi-session run (not a single session).

if (isSimulationMode) {
    setSimulationBalance(100);
    resetSeed();
    resetStats();
    clearConsole();
}

game = 'dice';

// --- Dice Config ---
chance = 10;
target = chanceToMultiplier(chance);
betHigh = true;

// --- Session-Level Config ---
var BASE_PCT = 0.01;                    // 1% of bankroll
var ESCALATE = 1.8;                     // Multiply bet per consecutive win
var MAX_BET_PCT = 0.03;                 // Cap at 3% of bankroll
var PROFIT_PROTECT_THRESHOLD = 0.10;    // Activate at +10% session profit
var PROFIT_PROTECT_CAP = 0.50;          // Cap bets at 50% of running profit
var SESSION_TARGET_PCT = 0.15;          // +15% session target
var SESSION_STOP_PCT = 0.10;            // -10% session stop
var TRAILING_LOCK = 0.50;              // Lock 50% of session peak
var MAX_ROLLS = 50;                     // Short sessions

// --- Meta-Level Config ---
var WALK_AWAY_MULT = 1.30;             // Walk away at +30% cumulative (v1.1: 1.50)
var CUM_STOP_PCT = 0.30;              // Hard stop at -30% cumulative (NEW)
var CUM_TRAILING_LOCK = 0.40;          // Lock 40% of cumulative peak
var CUM_TRAILING_MIN = 0.20;           // Only activate after +20% cum peak
var MAX_SESSIONS = 40;                  // Max sessions per run

// --- Sim Config ---
var SIM_SAMPLES = 250;

// --- Dynamic bankroll ---
var BANKROLL = isSimulationMode ? 100 : Math.floor(balance * 100) / 100;
var BASE_BET = Math.round(BANKROLL * BASE_PCT * 100) / 100;
if (BASE_BET < 0.01) BASE_BET = 0.01;
var MAX_BET = Math.round(BANKROLL * MAX_BET_PCT * 100) / 100;
var SESSION_TARGET = BANKROLL * SESSION_TARGET_PCT;
var SESSION_STOP = BANKROLL * SESSION_STOP_PCT;
var WALK_AWAY_TARGET = BANKROLL * (WALK_AWAY_MULT - 1);
var CUM_STOP = BANKROLL * CUM_STOP_PCT;
var CUM_TRAILING_MIN_AMT = BANKROLL * CUM_TRAILING_MIN;

// --- Session state (reset each session) ---
var runningProfit = 0;
var sessionRolls = 0;
var wins = 0;
var losses = 0;
var consecutiveWins = 0;
var bestStreak = 0;
var peakProfit = 0;
var trailingStop = -SESSION_STOP;
var exitReason = '';

// --- Meta state (reset each run) ---
var sessionCount = 0;
var cumProfit = 0;
var cumPeakProfit = 0;
var cumTrailingFloor = 0;
var metaExitReason = '';
var sessionResults = [];

// --- Vault state (persists across runs) ---
var totalVaulted = 0;

// --- Sim state ---
var currentSample = 0;
var sampleResults = [];
var totalSamples = isSimulationMode ? SIM_SAMPLES : 1;
var stopped = false;

function resetSession() {
    runningProfit = 0;
    sessionRolls = 0;
    wins = 0;
    losses = 0;
    consecutiveWins = 0;
    bestStreak = 0;
    peakProfit = 0;
    trailingStop = -SESSION_STOP;
    exitReason = '';
}

function resetRun() {
    sessionCount = 0;
    cumProfit = 0;
    cumPeakProfit = 0;
    cumTrailingFloor = 0;
    metaExitReason = '';
    sessionResults = [];
    resetSession();
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

    // Profit protection: cap bets when session is up
    if (runningProfit >= BANKROLL * PROFIT_PROTECT_THRESHOLD) {
        var profitCap = Math.round(runningProfit * PROFIT_PROTECT_CAP * 100) / 100;
        if (profitCap < BASE_BET) profitCap = BASE_BET;
        if (nextBet > profitCap) nextBet = profitCap;
    }

    if (nextBet < 0.01) nextBet = 0.01;
    return nextBet;
}

function endSession(reason) {
    exitReason = reason;
    sessionCount++;
    sessionResults.push({
        profit: runningProfit,
        rolls: sessionRolls,
        exit: reason,
        wins: wins,
        losses: losses,
        bestStreak: bestStreak,
        peak: peakProfit
    });

    // Update cumulative P&L
    cumProfit += runningProfit;

    // Update cumulative trailing stop (only after meaningful peak)
    if (cumProfit > cumPeakProfit) {
        cumPeakProfit = cumProfit;
        if (cumPeakProfit >= CUM_TRAILING_MIN_AMT) {
            var newFloor = cumPeakProfit * CUM_TRAILING_LOCK;
            if (newFloor > cumTrailingFloor) {
                cumTrailingFloor = newFloor;
            }
        }
    }

    if (isSimulationMode) {
        log('  S' + sessionCount + ' ' + reason + ' | P: $' + runningProfit.toFixed(2) + ' | Cum: $' + cumProfit.toFixed(2) + ' | ' + sessionRolls + 'r');
    }

    // --- Check meta exit conditions ---
    // Walk-away target — vault profits
    if (cumProfit >= WALK_AWAY_TARGET) {
        var vaultAmount = Math.round(cumProfit * 100) / 100;
        totalVaulted += vaultAmount;
        depositToVault(vaultAmount);
        if (isSimulationMode) {
            log('  VAULT: +$' + vaultAmount.toFixed(2) + ' (total vaulted: $' + totalVaulted.toFixed(2) + ')');
        } else {
            log('VAULTED $' + vaultAmount.toFixed(2) + ' | Total vaulted: $' + totalVaulted.toFixed(2));
        }
        endRun('WALK_AWAY');
        return;
    }

    // Cumulative stop-loss — hard floor
    if (cumProfit <= -CUM_STOP) {
        endRun('CUM_STOP');
        return;
    }

    // Cumulative trailing stop (only active after minimum peak reached)
    if (cumTrailingFloor > 0 && cumProfit <= cumTrailingFloor) {
        endRun('CUM_TRAILING');
        return;
    }

    // Bankrupt (lost entire bankroll)
    if ((BANKROLL + cumProfit) <= 0) {
        endRun('BANKRUPT');
        return;
    }

    // Max sessions
    if (sessionCount >= MAX_SESSIONS) {
        endRun('MAX_SESSIONS');
        return;
    }

    // Start next session
    resetSession();
    betSize = BASE_BET;
}

function endRun(reason) {
    metaExitReason = reason;
    var totalRolls = 0;
    var totalWins = 0;
    var runBestStreak = 0;
    for (var i = 0; i < sessionResults.length; i++) {
        totalRolls += sessionResults[i].rolls;
        totalWins += sessionResults[i].wins;
        if (sessionResults[i].bestStreak > runBestStreak) runBestStreak = sessionResults[i].bestStreak;
    }

    currentSample++;
    sampleResults.push({
        profit: cumProfit,
        sessions: sessionCount,
        rolls: totalRolls,
        wins: totalWins,
        metaExit: reason,
        peakCum: cumPeakProfit,
        bestStreak: runBestStreak,
        vaulted: reason === 'WALK_AWAY' ? cumProfit : 0
    });

    if (isSimulationMode) {
        log('RUN ' + currentSample + '/' + totalSamples + ' ' + reason + ' | P: $' + cumProfit.toFixed(2) + ' | Peak: $' + cumPeakProfit.toFixed(2) + ' | ' + sessionCount + ' sessions, ' + totalRolls + ' rolls');
    }

    if (currentSample >= totalSamples) {
        stopped = true;
        betSize = 0;
        engine.stop();
        return;
    }

    // Start next run
    resetRun();
    betSize = BASE_BET;
}

// --- Init ---
betSize = BASE_BET;

log((isSimulationMode ? '[SIM x' + totalSamples + '] ' : '[LIVE] ') + 'SIEGE v1.3 | Bal: $' + BANKROLL + ' | Base: $' + BASE_BET + ' | 10%/9.9x | Session: +$' + SESSION_TARGET.toFixed(0) + '/-$' + SESSION_STOP.toFixed(0) + ' | Walk: +$' + WALK_AWAY_TARGET.toFixed(0) + ' | CumStop: -$' + CUM_STOP.toFixed(0));

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

        if (!isSimulationMode && consecutiveWins >= 2) {
            log('STREAK x' + consecutiveWins + ' +$' + wonAmount.toFixed(2) + ' | Session: $' + runningProfit.toFixed(2) + ' | Cum: $' + (cumProfit + runningProfit).toFixed(2));
        }
    } else {
        losses++;
        runningProfit -= lastBet.amount;

        if (!isSimulationMode && consecutiveWins >= 3) {
            log('STREAK ENDED at x' + consecutiveWins + ' | Session: $' + runningProfit.toFixed(2));
        }
        consecutiveWins = 0;
    }

    // Update session peak and trailing stop
    if (runningProfit > peakProfit) {
        peakProfit = runningProfit;
        var newTrail = peakProfit * TRAILING_LOCK;
        if (newTrail > trailingStop) {
            trailingStop = newTrail;
            if (!isSimulationMode && trailingStop > 0) {
                log('TRAIL: Floor $' + trailingStop.toFixed(2) + ' (peak: $' + peakProfit.toFixed(2) + ')');
            }
        }
    }

    // --- Check session exit conditions ---
    if (runningProfit >= SESSION_TARGET) {
        endSession('TARGET');
        return;
    }

    if (runningProfit <= trailingStop) {
        if (trailingStop > 0) {
            endSession('TRAILING_STOP');
        } else {
            endSession('STOP_LOSS');
        }
        return;
    }

    if (sessionRolls >= MAX_ROLLS) {
        endSession('MAX_ROLLS');
        return;
    }

    betSize = calcNextBet();
});

engine.onBettingStopped(function (isManualStop, lastError) {
    playHitSound();

    if (isSimulationMode && sampleResults.length > 1) {
        var totalProfit = 0;
        var totalRolls = 0;
        var totalSessions = 0;
        var runWins = 0;
        var runLosses = 0;
        var bestProfit = -Infinity;
        var worstProfit = Infinity;
        var allStreaks = 0;
        var metaExitCounts = {};
        var profits = [];
        var winProfits = [];
        var lossProfits = [];
        var simVaulted = 0;

        // Equity curve
        var cumPL = 0;
        var eqPeak = 0;
        var maxDD = 0;
        var peakBal = BANKROLL;
        var troughBal = BANKROLL;

        for (var i = 0; i < sampleResults.length; i++) {
            var s = sampleResults[i];
            totalProfit += s.profit;
            totalRolls += s.rolls;
            totalSessions += s.sessions;
            profits.push(s.profit);
            simVaulted += s.vaulted;
            if (s.profit > bestProfit) bestProfit = s.profit;
            if (s.profit < worstProfit) worstProfit = s.profit;
            if (s.profit > 0) { runWins++; winProfits.push(s.profit); }
            else { runLosses++; lossProfits.push(s.profit); }
            if (s.bestStreak > allStreaks) allStreaks = s.bestStreak;
            metaExitCounts[s.metaExit] = (metaExitCounts[s.metaExit] || 0) + 1;

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
        var avgSessions = totalSessions / n;

        // Walk-away hit rate
        var walkAwayCount = metaExitCounts['WALK_AWAY'] || 0;
        var walkAwayRate = (walkAwayCount / n * 100).toFixed(1);

        // Net P&L accounting for vault
        var totalLost = totalProfit - simVaulted;

        log('');
        log('========== SIEGE v1.3 SIM RESULTS (' + n + ' runs) ==========');
        log('Run Win Rate: ' + runWins + '/' + n + ' (' + (runWins / n * 100).toFixed(1) + '%) | PF: ' + (runWins > 0 && runLosses > 0 ? (runWins / runLosses).toFixed(2) : 'N/A'));
        log('Walk-Away Rate: ' + walkAwayCount + '/' + n + ' (' + walkAwayRate + '%)');
        log('');
        log('--- Vault ---');
        log('Total Vaulted: $' + simVaulted.toFixed(2) + ' (' + walkAwayCount + ' deposits)');
        log('Total Lost (non-vault runs): $' + totalLost.toFixed(2));
        log('Net P&L (vault - losses): $' + (simVaulted + totalLost).toFixed(2));
        log('');
        log('--- Per-Run Stats ---');
        log('Total P&L: $' + totalProfit.toFixed(2) + ' | Avg: $' + avgProfit.toFixed(2) + ' | Median: $' + median.toFixed(2));
        log('Avg Win: +$' + avgWin.toFixed(2) + ' | Avg Loss: $' + avgLoss.toFixed(2) + ' | Ratio: ' + (avgLoss !== 0 ? (avgWin / Math.abs(avgLoss)).toFixed(2) : 'N/A'));
        log('Best: +$' + bestProfit.toFixed(2) + ' | Worst: $' + worstProfit.toFixed(2));
        log('P10: $' + p10.toFixed(2) + ' | P25: $' + p25.toFixed(2) + ' | P75: $' + p75.toFixed(2) + ' | P90: $' + p90.toFixed(2));
        log('Peak Bal: $' + peakBal.toFixed(2) + ' | Trough Bal: $' + troughBal.toFixed(2) + ' | Max Drawdown: $' + maxDD.toFixed(2) + ' (' + (maxDD / BANKROLL * 100).toFixed(1) + '%)');
        log('Avg Sessions/Run: ' + avgSessions.toFixed(1) + ' | Avg Rolls/Run: ' + avgRolls.toFixed(0) + ' | Best Streak: ' + allStreaks);
        log('Meta Exits: ' + JSON.stringify(metaExitCounts));
        log('Balance: $' + balance.toFixed(2));
        log('====================================================================');
    } else {
        log('=== RUN OVER ===');
        log('Mode: ' + (isSimulationMode ? 'SIMULATION' : 'LIVE'));
        log('Meta Exit: ' + (metaExitReason || (isManualStop ? 'MANUAL' : 'UNKNOWN')));
        log('Sessions: ' + sessionCount + ' | Cum P&L: $' + cumProfit.toFixed(2) + ' (' + (cumProfit >= 0 ? '+' : '') + (cumProfit / BANKROLL * 100).toFixed(1) + '%)');
        log('Cum Peak: $' + cumPeakProfit.toFixed(2) + ' | Cum Floor: $' + cumTrailingFloor.toFixed(2));
        log('Total Vaulted: $' + totalVaulted.toFixed(2));
        log('Balance: $' + balance.toFixed(2));
    }

    if (lastError) log('Error: ' + lastError);
});
