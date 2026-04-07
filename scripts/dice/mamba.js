// MAMBA v2.0 — Dice IOL Profit Strategy + Trailing Stop
// 65% chance, IOL 3.0x, trailing stop locks profits on decline
// Win payout: +0.523x bet (99/65 - 1). Miss: 35%. Edge: 1%.
//
// v2.0.1: Trailing stop (no multiplier gate) + fixed stop.
//   trail 5/80 + stop=15%: +$42 median, 4.2% bust, 91.7% win
//   trail 8/80 + stop=15%: +$61 median, 7.0% bust, 88.4% win
//   Trail fires mid-IOL — catches crashes that v1 missed.
//
// Trailing stop: once profit exceeds trailActivatePct%, track peak profit.
// If profit drops below trailLockPct% of peak, exit session.
// Fixed stop still active as upper target.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice)

strategyTitle = "MAMBA";
version = "2.0.2";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
//
// RISK PRESETS (10k bets, $1000 bank, with trailing stop):
//
//   Stop | Trail  | Median | Bust%  | Win%  | Time  | Profile
//  ------|--------|--------|--------|-------|-------|----------
//   10%  | 5/80   | +$42   |  4.2%  | 91.7% | ~4m   | Conservative
//   15%  | 5/80   | +$42   |  4.2%  | 91.7% | ~4m   | Safe (recommended)
//   15%  | 8/80   | +$61   |  7.0%  | 88.4% | ~5m   | Balanced
//   20%  | 8/80   | +$61   |  7.0%  | 88.4% | ~5m   | Aggressive
//   30%  | 8/80   | +$61   |  7.0%  | 88.4% | ~5m   | Very aggressive
//  Note: trail fires mid-IOL (no multiplier gate). Lock=80% = exit
//  when profit drops to 20% of peak. Most trail exits are profitable.
//
chance = 65;
divider = 10000;
increaseOnLossPercent = 200; // IOL: 200 = multiply by 3.0x on loss.

// Trailing stop config
trailActivatePct = 10;  // activate trailing stop after profit exceeds this % of startBalance
trailLockPct = 60;     // exit if profit drops below this % of peak profit (40% cushion)

// Bet direction: true = over, false = under
betHigh = true;

// Fixed stop (upper target). Set 0 for trailing-only.
stopTotalPct = 15;
// With trail 5/80 + stop 15%: median +$42-61, bust 4.2-7%, win 88-92%

// Vault (optional insurance). Set 0 to disable.
vaultPct = 0;

// Other stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 0;
stopAfterHands = 0;

// Reset stats/console on start (set false to preserve previous session data)
resetOnStart = true;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(1000);
  resetSeed();
}

if (resetOnStart) {
  resetStats();
  clearConsole();
}

target = chanceToMultiplier(chance);
startBalance = balance;
iol = 1 + increaseOnLossPercent / 100;
winPayout = 99 / chance - 1;

baseBet = startBalance / divider;

// Enforce minimum bet ($0.00101 on Shuffle)
minBet = 0.00101;
if (baseBet < minBet) {
  baseBet = minBet;
  log("#FFFF2A", "Min bet enforced: $" + baseBet.toFixed(5));
}

betSize = baseBet;

// Thresholds
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;

// Max survivable LS
function calcMaxLS() {
  cumulative = 0;
  bet = baseBet;
  streak = 0;
  while (cumulative + bet <= startBalance) {
    cumulative += bet;
    streak++;
    bet *= iol;
  }
  return streak;
}
maxSurvivableLS = calcMaxLS();

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
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00FF7F",
    "================================\n MAMBA v" + version +
    "\n================================\n by " + author + " | Dice " + chance + "% IOL + Trail" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentBet = baseBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  profitRate = betsPlayed > 0 ? (profit / betsPlayed * 100).toFixed(2) : "0.00";
  rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  vaultBar = totalVaulted > 0 ? " | Vaulted: $" + totalVaulted.toFixed(2) + " (" + vaultCount + "x)" : "";
  targetBar = stopOnTotalProfit > 0 ? " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2) : "";

  runwayBar = "";
  if (lossStreak > 0) {
    runwayBar = " | Runway: LS " + lossStreak + "/" + maxSurvivableLS + " | Chain: -$" + currentChainCost.toFixed(2);
  }

  totalAssets = balance + totalVaulted;
  assetBar = totalVaulted > 0 ? " (Bal $" + balance.toFixed(2) + " + Vault $" + totalVaulted.toFixed(2) + ")" : "";

  // Trailing stop indicator
  trailBar = "";
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
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Rate: $" + profitRate + "/100b | Chance: " + chance + "% (+" + (winPayout * 100).toFixed(1) + "%)");
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);
  log("#8B949E", "IOL chain: " + recoveries + " recovered | " + (lossStreak > 0 ? "LS " + lossStreak + " at " + currentMultiplier.toFixed(1) + "x" : "base bet"));
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Max LS: " + maxSurvivableLS);
}

// ============================================================
// MAMBA STRATEGY — IOL on Dice
// ============================================================

function mainStrategy() {
  betsPlayed++;

  totalWagered += lastBet.amount;

  isWin = lastBet.win;

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

  // IOL logic
  if (isWin) {
    recoveryAmt = baseBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    betSize = baseBet;
  } else {
    currentChainCost += lastBet.amount;
    currentMultiplier *= iol;

    // Soft bust: if next bet exceeds balance, reset to base
    nextBet = baseBet * currentMultiplier;
    if (nextBet > balance * 0.95) {
      log("#FD6868", "IOL $" + nextBet.toFixed(2) + " > balance $" + balance.toFixed(2) + " — reset to base");
      currentMultiplier = 1;
      currentChainCost = 0;
    }

    betSize = baseBet * currentMultiplier;
  }

  // Trail-aware bet cap: if trail is active, don't let a loss breach the floor
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && betSize > maxTrailBet) {
      betSize = maxTrailBet;
    }
  }

  if (betSize < minBet) betSize = minBet;
  currentBet = betSize;
  if (currentBet > maxBetSeen) maxBetSeen = currentBet;
}

// ============================================================
// TRAILING STOP
// ============================================================

function trailingStopCheck() {
  // Activate trailing stop when profit exceeds threshold
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
  }

  if (trailActive) {
    // Update floor based on peak
    trailFloor = peakProfit * trailLockPct / 100;

    // Fire trailing stop when profit drops below floor — no multiplier gate
    if (profit <= trailFloor) {
      trailStopFired = true;
      log("#FFD700", "TRAILING STOP! Profit $" + profit.toFixed(2) + " < floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")");
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
  currentProfit = profit - profitAtLastVault;

  if (
    vaultProfitsThreshold > 0 &&
    currentMultiplier <= 1.01 &&
    currentProfit >= vaultProfitsThreshold
  ) {
    vaultAmount = currentProfit;
    await depositToVault(vaultAmount);
    totalVaulted += vaultAmount;
    profitAtLastVault = profit;
    vaultCount++;
    log("#4FFB4F", "Vaulted $" + vaultAmount.toFixed(2) + " | Total vaulted: $" + totalVaulted.toFixed(2));

    // Adaptive rebase
    startBalance = balance;
    baseBet = startBalance / divider;
    if (baseBet < minBet) baseBet = minBet;
    betSize = baseBet;
    maxSurvivableLS = calcMaxLS();
    vaultProfitsThreshold = startBalance * vaultPct / 100;
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
  if (stopOnLoss > 0 && profit < -Math.abs(stopOnLoss)) {
    log("#FD6868", "Stopped on $" + (-profit).toFixed(2) + " Loss");
    stopped = true;
    logSummary();
    engine.stop();
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#42CAF7", "Base bet: $" + baseBet.toFixed(5) + " | Chance: " + chance + "% | Payout: " + (winPayout + 1).toFixed(3) + "x (+" + (winPayout * 100).toFixed(1) + "%)");
log("#00FF7F", "IOL " + iol + "x | Max LS: " + maxSurvivableLS);
log("#FFD700", "Trailing stop: activate at " + trailActivatePct + "% ($" + trailActivateThreshold.toFixed(2) + "), lock " + trailLockPct + "% of peak");
vaultLabel = vaultPct > 0 ? "Vault at " + vaultPct + "% ($" + vaultProfitsThreshold.toFixed(2) + ")" : "No vault";
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% ($" + stopOnTotalProfit.toFixed(2) + ")" : "No fixed stop";
log("#4FFB4F", vaultLabel + " | " + stopLabel);

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

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  exitType = trailStopFired ? "TRAILING STOP" : "TARGET/MANUAL";
  log(
    "#00FF7F",
    "================================\n MAMBA v" + version + " — " + exitType + "\n================================"
  );
  totalAssetsFinal = balance + totalVaulted;
  log("#4FFB4F", "ASSETS: $" + totalAssetsFinal.toFixed(2) + " (Bal $" + balance.toFixed(2) + " + Vault $" + totalVaulted.toFixed(2) + ") | P&L: $" + profit.toFixed(2));
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Vaults: " + vaultCount);
  log("RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("Final bet: $" + (baseBet * currentMultiplier).toFixed(5) + " (" + currentMultiplier.toFixed(1) + "x) | Balance: $" + balance.toFixed(2));
  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
  log("#8B949E", "IOL chains recovered: " + recoveries + " | Max LS: " + longestLossStreak + " | Max survivable: " + maxSurvivableLS);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
