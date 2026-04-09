// SAPPER v1.0 — Mines Profit Strategy + Trailing Stop
// Config: mines=3, fields=4, IOL 3.0x on loss, reset on win.
// Win: 57.8% | Net payout: +0.712x | House edge: 1%
//
// Monte Carlo ($100, 5k, trail 8/60): +$5.97 median, 0% bust, 76.5% win
//   Beats MAMBA (+$5.56) and COBRA (+$5.44) — 1% edge = cheapest IOL recovery.
//
// IOL recovery surplus: 3.0 x 0.712 = 2.14 (>1.0 = can recover deficit + profit)
//
// Mines math (5x5 grid, 1% house edge):
//   win_prob = (22/25)(21/24)(20/23)(19/22) = 57.8%
//   gross_payout = 0.99 / 0.578 = 1.712x
//   net_payout = +0.712x per win
//
// Configuration equivalence (proven in Monte Carlo):
//   m=3 f=4 and m=4 f=3 produce identical results.
//   Only the resulting probability matters, not how you construct it.

strategyTitle = "SAPPER";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "mines";

// USER CONFIG
// ============================================================
//
// RISK PRESETS ($100 bank, trail=8/60, MC 5k sessions):
//
//   Mines | Fields | IOL  | Div   | Median | Bust% | Win%  | Profile
//  -------|--------|------|-------|--------|-------|-------|----------
//     3   |    4   | 3.0x | 10000 | +$5.97 |  0.0% | 76.5% | Recommended
//     2   |    6   | 3.0x | 10000 | +$6.03 |  0.0% | 76.1% | Max median
//     3   |    3   | 3.0x | 10000 | +$5.52 |  0.0% | 74.6% | Conservative
//     5   |    2   | 3.0x | 10000 | +$5.61 |  0.0% | 75.8% | Yoanium-like
//    10   |    1   | 3.0x | 10000 | +$5.78 |  0.0% | 75.1% | Simple (1 pick)
//
mineCount = 3;
fieldCount = 4;
divider = 10000;

// IOL: multiply bet on loss, reset on win
iol = 3.0;

// Bet cap: max bet as % of working balance
betCapPct = 15;         // 0 = disabled

// Trailing stop
trailActivatePct = 8;   // activate after profit >= this % of startBalance
trailLockPct = 60;      // exit when profit <= peak * lockPct / 100

// Stop loss (hard floor, % of startBalance)
stopOnLoss = 15;

// Stop profit (% of startBalance). Set 0 for trail-only.
stopTotalPct = 15;

// Vault: auto-detect platform
vaultPct = 5;           // vault profits at this % of startBalance. 0 = disabled.
vaultMode = (casino === "SHUFFLE" || casino === "STAKE" || casino === "STAKE_US" || casino === "SHUFFLE_US" || casino === "GOATED") ? "real" : "virtual";

// Other stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopAfterHands = 0;

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

log("#42CAF7", "Detected casino: " + casino + " | Vault mode: " + vaultMode + (vaultMode === "virtual" ? " (soft vault)" : " (real vault)"));

// Mines setup
mines = mineCount;
fields = randomFields(fieldCount);

// Bankroll
startBalance = balance;
baseBet = Math.max(startBalance / divider, 0.00101);
betSize = baseBet;
minBet = 0.00101;

// Precompute win probability and net payout for logging
winProb = 1;
for (var i = 0; i < fieldCount; i++) {
  winProb *= (25 - mineCount - i) / (25 - i);
}
netPayout = 0.99 / winProb - 1;

// Thresholds
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;
stopLossAmount = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;

// State
currentMultiplier = 1;
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
totalWins = 0;
totalLosses = 0;
betsPlayed = 0;
peakProfit = 0;
totalWagered = 0;
profitAtLastVault = 0;
totalVaulted = 0;
vaultCount = 0;
maxBetSeen = baseBet;
recoveries = 0;
currentChainCost = 0;
biggestRecovery = 0;
stopped = false;
summaryPrinted = false;

// Trailing stop state
trailActive = false;
trailFloor = 0;
trailStopFired = false;

// ============================================================
// HELPERS
// ============================================================

function randomFields(count) {
  var allFields = Array.from(Array(25).keys());
  return shuffle(allFields).slice(0, count);
}

function calcMaxLS() {
  var cum = 0;
  var bet = baseBet;
  var streak = 0;
  while (cum + bet <= startBalance) {
    cum += bet;
    streak++;
    bet *= iol;
  }
  return streak;
}
maxSurvivableLS = calcMaxLS();

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00FF7F",
    "================================\n SAPPER v" + version +
    "\n================================\n by " + author + " | Mines " + mineCount + "x" + fieldCount +
    " IOL " + iol + "x + Trail" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();
  log("#42CAF7", casino + " | " + vaultMode + " vault | SL " + stopOnLoss + "%");

  var currentBet = baseBet * currentMultiplier;
  var drawdown = peakProfit - profit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  var vaultTag = vaultMode === "virtual" ? "Soft-Vault" : "Vault";
  var vaultBar = totalVaulted > 0 ? " | " + vaultTag + ": $" + totalVaulted.toFixed(2) + " (" + vaultCount + "x)" : "";
  var targetBar = stopOnTotalProfit > 0 ? " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2) : "";

  var runwayBar = "";
  if (lossStreak > 0) {
    runwayBar = " | IOL " + currentMultiplier.toFixed(1) + "x | LS " + lossStreak + " | Chain: -$" + currentChainCost.toFixed(2);
  }

  var totalAssets = vaultMode === "virtual" ? balance : balance + totalVaulted;
  var workBal = vaultMode === "virtual" ? balance - totalVaulted : balance;
  var assetBar = totalVaulted > 0 ? " (Work $" + workBal.toFixed(2) + " + " + vaultTag + " $" + totalVaulted.toFixed(2) + ")" : "";

  var trailBar = "";
  if (trailActive) {
    trailBar = " | TRAIL: floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = " | Trail arms at $" + trailActivateThreshold.toFixed(2);
  }

  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(5) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log("#FF6B6B", "LS: " + lossStreak + " | WS: " + winStreak + runwayBar);
  log("#4FFB4F", "ASSETS: $" + totalAssets.toFixed(2) + assetBar + " | P&L: $" + profit.toFixed(2));
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#A4FD68", vaultBar + targetBar);
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Mines: " + mineCount + " | Fields: " + fieldCount + " (win " + (winProb * 100).toFixed(1) + "% +" + (netPayout * 100).toFixed(1) + "%)");
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Max LS: " + maxSurvivableLS);
}

// ============================================================
// SAPPER STRATEGY — IOL on Mines
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  var isWin = lastBet.win;

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

  if (profit > peakProfit) peakProfit = profit;

  // --- IOL logic ---
  if (isWin) {
    var recoveryAmt = lastBet.amount;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    betSize = baseBet;
  } else {
    currentChainCost += lastBet.amount;
    currentMultiplier *= iol;

    // Soft bust: next bet exceeds 95% of working balance — reset IOL
    var nextBet = baseBet * currentMultiplier;
    var workBal = vaultMode === "virtual" ? balance - totalVaulted : balance;
    if (nextBet > workBal * 0.95) {
      log("#FD6868", "Soft bust: $" + nextBet.toFixed(2) + " > 95% of $" + workBal.toFixed(2) + " — reset");
      currentMultiplier = 1;
      currentChainCost = 0;
    }

    betSize = baseBet * currentMultiplier;
  }

  // --- Bet caps ---

  // Hard bet cap: max bet as % of working balance
  if (betCapPct > 0) {
    var workBal2 = vaultMode === "virtual" ? balance - totalVaulted : balance;
    var maxBetAllowed = workBal2 * betCapPct / 100;
    if (betSize > maxBetAllowed) betSize = maxBetAllowed;
  }

  // Trail-aware bet cap: don't let a loss breach the trail floor
  if (trailActive) {
    var maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && betSize > maxTrailBet) {
      betSize = maxTrailBet;
    }
  }

  // SL-aware bet cap: prevent single bet from overshooting stop loss
  if (stopOnLoss > 0) {
    var workProfit = vaultMode === "virtual" ? profit - totalVaulted : profit;
    var slCushion = workProfit + stopLossAmount;
    if (slCushion >= 0 && betSize > slCushion) {
      betSize = slCushion;
    }
  }

  // Floor
  if (betSize < minBet) betSize = minBet;
  if (betSize > maxBetSeen) maxBetSeen = betSize;

  // Randomize fields for next round
  fields = randomFields(fieldCount);
}

// ============================================================
// TRAILING STOP
// ============================================================

function trailingStopCheck() {
  // Activate when profit exceeds threshold
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
    peakProfit = profit;
    trailFloor = peakProfit * trailLockPct / 100;
    log("#FFD700", "TRAIL ACTIVE! Peak $" + peakProfit.toFixed(2) + " | Floor $" + trailFloor.toFixed(2));
  }

  if (trailActive) {
    // Update peak and floor
    if (profit > peakProfit) {
      peakProfit = profit;
      trailFloor = peakProfit * trailLockPct / 100;
    }

    // Fire when profit drops below floor — no multiplier gate
    if (profit <= trailFloor) {
      trailStopFired = true;
      log("#FFD700", "TRAILING STOP! Profit $" + profit.toFixed(2) + " <= floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")");
      stopped = true;
      logSummary();
      engine.stop();
    }
  }
}

// ============================================================
// VAULT & STOP
// ============================================================

async function vaultHandle() {
  var currentProfit = profit - profitAtLastVault;

  if (
    vaultProfitsThreshold > 0 &&
    currentMultiplier <= 1.01 &&
    currentProfit >= vaultProfitsThreshold
  ) {
    var vaultAmount = currentProfit;

    if (vaultMode === "real") {
      await depositToVault(vaultAmount);
    }

    totalVaulted += vaultAmount;
    profitAtLastVault = profit;
    vaultCount++;
    var vaultLabel = vaultMode === "virtual" ? "SOFT-VAULTED" : "VAULTED";
    log("#4FFB4F", vaultLabel + " $" + vaultAmount.toFixed(2) + " | Total: $" + totalVaulted.toFixed(2));

    // Adaptive rebase — use working balance (exclude vaulted)
    var workingBalance = balance - totalVaulted;
    if (vaultMode === "real") workingBalance = balance;
    startBalance = workingBalance;
    baseBet = Math.max(startBalance / divider, minBet);
    betSize = baseBet;
    maxSurvivableLS = calcMaxLS();
    vaultProfitsThreshold = startBalance * vaultPct / 100;
    trailActivateThreshold = startBalance * trailActivatePct / 100;
    stopLossAmount = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
  }
}

function stopProfitCheck() {
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentMultiplier <= 1.01) {
    log("#4FFB4F", "Target reached! P&L: $" + profit.toFixed(2) + " (Vaulted: $" + totalVaulted.toFixed(2) + ")");
    stopped = true;
    logSummary();
    engine.stop();
  }

  if (stopOnProfit > 0 && profit >= stopOnProfit) {
    log("#4FFB4F", "Stopped on $" + profit.toFixed(2) + " Profit");
    stopped = true;
    logSummary();
    engine.stop();
  }
}

function stopLossCheck() {
  var workProfit = vaultMode === "virtual" ? profit - totalVaulted : profit;
  if (stopOnLoss > 0 && workProfit <= -stopLossAmount) {
    log("#FD6868", "Stop loss! Working P&L $" + workProfit.toFixed(2) + " (-" + stopOnLoss + "% of $" + startBalance.toFixed(2) + ") | Vault safe: $" + totalVaulted.toFixed(2));
    stopped = true;
    logSummary();
    engine.stop();
  }
}

// ============================================================
// SUMMARY
// ============================================================

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  var rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  var exitType = trailStopFired ? "TRAILING STOP" : "TARGET/MANUAL";
  log(
    "#00FF7F",
    "================================\n SAPPER v" + version + " — " + exitType + "\n================================"
  );
  var totalAssetsFinal = vaultMode === "virtual" ? balance : balance + totalVaulted;
  var workBalFinal = vaultMode === "virtual" ? balance - totalVaulted : balance;
  var vaultTagFinal = vaultMode === "virtual" ? "Soft-Vault" : "Vault";
  log("#4FFB4F", "ASSETS: $" + totalAssetsFinal.toFixed(2) + " (Work $" + workBalFinal.toFixed(2) + " + " + vaultTagFinal + " $" + totalVaulted.toFixed(2) + ") | P&L: $" + profit.toFixed(2));
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Vaults: " + vaultCount);
  log("RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("Mines: " + mineCount + " | Fields: " + fieldCount + " | Win: " + (winProb * 100).toFixed(1) + "% | Payout: +" + (netPayout * 100).toFixed(1) + "%");
  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#42CAF7", "Base bet: $" + baseBet.toFixed(5) + " | Mines: " + mineCount + " | Fields: " + fieldCount);
log("#42CAF7", "Win: " + (winProb * 100).toFixed(1) + "% | Payout: " + (netPayout + 1).toFixed(3) + "x (+" + (netPayout * 100).toFixed(1) + "%) | IOL: " + iol + "x");
log("#42CAF7", "Recovery check: " + iol + " x " + netPayout.toFixed(3) + " = " + (iol * netPayout).toFixed(2) + " (>1.0 = OK)");
log("#FFD700", "Trail: arm at " + trailActivatePct + "% ($" + trailActivateThreshold.toFixed(2) + "), lock at " + trailLockPct + "% of peak");
var vaultModeLabel = vaultMode === "virtual" ? " [SOFT]" : "";
var vaultLabel = vaultPct > 0 ? "Vault" + vaultModeLabel + " at " + vaultPct + "%" : "No vault";
var stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "%" : "No fixed stop";
var slLabel = stopOnLoss > 0 ? "SL at " + stopOnLoss + "%" : "No SL";
log("#4FFB4F", vaultLabel + " | " + stopLabel + " | " + slLabel);
log("#00FF7F", "Max survivable LS: " + maxSurvivableLS);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  trailingStopCheck();
  if (stopped) return;
  await vaultHandle();
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && betsPlayed >= stopAfterHands) {
    log("#FFFF2A", "Dev stop: " + betsPlayed + " bets reached");
    stopped = true;
    logSummary();
    engine.stop();
  }
});

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
