// SURGEWAGER v2.0 — Dual-Phase Wager + Recovery Strategy (Limbo)
// Based on SurgeWager by macvault/Vrafasky. Optimized for 80/20 wager-profit balance.
// Ported from dice to limbo — identical math (1% edge, target=99/chance), no betHigh.
//
// WAGER PHASE: High-frequency betting at 98% chance (1.0102x target).
//   div=100 base bet, +15% on each win, reset every 5-win streak.
//   Generates massive wager throughput (~30x balance per 5K bets).
//
// RECOVERY PHASE: Activates on -2.5% session drawdown.
//   Switches to 2.2x target (45% chance), IOL 88%, div=5000 base.
//   Returns to wager phase when session profit >= 0.
//
// v1.1: Added stopLoss=30% conservative kill switch.
//   Swing analysis shows median recovery swing of $6, P90 $17, P99 $47.
//   SL=30% eliminates 100% of busts, keeps 73% of wager (21.4x vs 29.2x).
//
// v2.0: Ported to limbo. Removed betHigh/over-under toggle (no concept in limbo).
//   All math identical — same house edge, same targets, same EV.
//
//   RISK PRESETS ($100 bank, 5K bets, stopProfit=3%):
//
//     SL   | Wager | Bust% | Win%  | Median | Max Loss | Profile
//    ------|-------|-------|-------|--------|----------|----------
//      0%  | 29.2x | 23.1% | 38.4% | -$1.02 |  -$100  | Aggressive (original)
//     30%  | 21.4x |  0.0% | 29.2% | -$3.13 |   -$30  | Conservative (recommended)
//     50%  | 28.9x |  0.0% | 38.4% | -$1.03 |   -$50  | Balanced
//
// Cost efficiency: ~1.01% per $1 wagered (matches house edge).
// Viable when VIP rakeback/rewards exceed 1.01%.

strategyTitle = "SURGEWAGER";
version = "2.0.0";
author = "stanz";
scripter = "stanz";

game = "limbo";

// USER CONFIG
// ============================================================
//
// WAGER PHASE
wagerDivider = 100;           // base bet = balance / 100 (1% of balance)
wagerTarget = 1.0102;         // 98% chance, +1.02% per win
increaseOnWinPct = 15;        // +15% bet on each consecutive win
resetOnWinStreak = 5;         // reset to base after 5-win streak

// RECOVERY PHASE
recoverDivider = 5000;        // recovery base bet = balance / 5000
recoverTarget = 2.2;          // ~45% chance, +1.2x per win
recoverIOLPct = 88;           // +88% bet on each recovery loss (~1.88x Martingale)
switchToRecoverPct = 2.5;     // enter recovery when session loss >= this % of balance

// SESSION MANAGEMENT
stopProfitPct = 3;            // exit session at +3% profit. THE key optimization.
stopOnLoss = 30;              // hard stop loss (% of balance). 0 = bust allowed. 30 = conservative.

// Reset stats/console on start
resetOnStart = true;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
}

if (resetOnStart) {
  resetStats();
  clearConsole();
}

// Bankroll
startBalance = balance;
wagerBaseBet = startBalance / wagerDivider;
recoverBaseBet = startBalance / recoverDivider;
minBet = 0.00101;

// Initial state
betSize = wagerBaseBet;
target = wagerTarget;
phase = 1;  // 1 = wager, 2 = recovery

// Thresholds
stopProfitAmount = stopProfitPct > 0 ? startBalance * stopProfitPct / 100 : 0;
stopLossAmount = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
switchThreshold = startBalance * switchToRecoverPct / 100;

// Stats
sessionProfit = 0;
totalWagered = 0;
totalWins = 0;
totalLosses = 0;
betsPlayed = 0;
peakProfit = 0;
worstDrawdown = 0;
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
phaseSwitches = 0;
recoveryEntries = 0;
recoveryChainDepth = 0;
maxBetSeen = wagerBaseBet;
stopped = false;
summaryPrinted = false;

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00FF7F",
    "================================\n SURGEWAGER v" + version + " (Limbo)" +
    "\n================================\n by " + author + " | Wager+Recovery | stop=" + stopProfitPct + "%" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  var phaseLabel = phase === 1 ? "WAGER (div=" + wagerDivider + ")" : "RECOVERY (IOL " + recoverIOLPct + "%)";
  var phaseColor = phase === 1 ? "#4FC3F7" : "#FF6B6B";
  var drawdown = peakProfit - sessionProfit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var wagerMult = totalWagered > 0 ? (totalWagered / startBalance).toFixed(1) : "0.0";
  var rtp = totalWagered > 0 ? ((totalWagered + sessionProfit) / totalWagered * 100).toFixed(2) : "100.00";

  log(phaseColor, "Phase: " + phaseLabel + (phase === 2 ? " | Chain: " + recoveryChainDepth + " deep" : ""));
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | Bet: $" + betSize.toFixed(5) + " | Target: " + target.toFixed(4) + "x");
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Peak: $" + peakProfit.toFixed(2) + ddBar);

  var targetBar = stopProfitAmount > 0 ? " | Target: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "WAGER: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | WS: " + winStreak + " | LS: " + lossStreak);
  log("#42CAF7", "RTP: " + rtp + "% | Switches: " + phaseSwitches + " | Recoveries: " + recoveryEntries);
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Worst DD: $" + worstDrawdown.toFixed(2));
}

// ============================================================
// SURGE STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  var isWin = lastBet.win;

  // Track streaks
  if (isWin) {
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;
  } else {
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;
  }

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  // --- PHASE 1: WAGER ---
  if (phase === 1) {
    if (isWin) {
      betSize *= (1 + increaseOnWinPct / 100);
      if (winStreak > 0 && winStreak % resetOnWinStreak === 0) {
        betSize = wagerBaseBet;
      }
    } else {
      betSize = wagerBaseBet;
      // Check: switch to recovery?
      if (sessionProfit <= -switchThreshold) {
        phase = 2;
        target = recoverTarget;
        betSize = recoverBaseBet;
        recoveryChainDepth = 0;
        phaseSwitches++;
        recoveryEntries++;
        log("#FF6B6B", "RECOVERY MODE — session loss $" + sessionProfit.toFixed(2) + " hit -" + switchToRecoverPct + "% threshold");
      }
    }
  }

  // --- PHASE 2: RECOVERY ---
  if (phase === 2) {
    if (isWin) {
      betSize = recoverBaseBet;
      recoveryChainDepth = 0;
      // Check: recovered? Return to wager
      if (sessionProfit >= 0) {
        phase = 1;
        betSize = wagerBaseBet;
        target = wagerTarget;
        phaseSwitches++;
        log("#4FFB4F", "RECOVERED — back to wager phase");
      }
    } else {
      recoveryChainDepth++;
      betSize *= (1 + recoverIOLPct / 100);
    }
  }

  // Bet safety
  if (betSize > balance * 0.95) betSize = balance * 0.95;
  if (betSize < minBet) betSize = minBet;
  if (betSize > maxBetSeen) maxBetSeen = betSize;
}

// ============================================================
// STOP CONDITIONS
// ============================================================

function checkStops() {
  // Stop profit
  if (stopProfitAmount > 0 && sessionProfit >= stopProfitAmount) {
    log("#4FFB4F", "STOP PROFIT! +$" + sessionProfit.toFixed(2) + " (" + stopProfitPct + "% target reached)");
    stopped = true;
    logSummary();
    engine.stop();
    return;
  }

  // Stop loss
  if (stopLossAmount > 0 && -sessionProfit >= stopLossAmount) {
    log("#FD6868", "STOP LOSS! -$" + (-sessionProfit).toFixed(2));
    stopped = true;
    logSummary();
    engine.stop();
    return;
  }
}

// ============================================================
// SUMMARY
// ============================================================

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  var wagerMult = (totalWagered / startBalance).toFixed(1);
  var rtp = totalWagered > 0 ? ((totalWagered + sessionProfit) / totalWagered * 100).toFixed(2) : "100.00";
  var exitType = sessionProfit >= 0 ? "PROFIT" : "LOSS";
  log(
    "#00FF7F",
    "================================\n SURGEWAGER v" + version + " (Limbo) — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "WAGER: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("RTP: " + rtp + "% | Longest WS: " + longestWinStreak + " | Longest LS: " + longestLossStreak);
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Switches: " + phaseSwitches + " | Recovery entries: " + recoveryEntries);
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#42CAF7", "Wager: div=" + wagerDivider + " ($" + wagerBaseBet.toFixed(4) + ") | Target: " + wagerTarget + "x | +15%/win, reset@" + resetOnWinStreak + "streak");
log("#FF6B6B", "Recovery: div=" + recoverDivider + " ($" + recoverBaseBet.toFixed(4) + ") | Target: " + recoverTarget + "x | IOL=" + recoverIOLPct + "% | trigger=-" + switchToRecoverPct + "%");
log("#FFD700", "Stop profit: " + stopProfitPct + "% ($" + stopProfitAmount.toFixed(2) + ")" + (stopOnLoss > 0 ? " | Stop loss: " + stopOnLoss + "%" : " | No stop loss"));

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  checkStops();
});

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
