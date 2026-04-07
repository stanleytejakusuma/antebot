// COBRA v5.0 — Roulette Profit Strategy + Trailing Stop
// Pure 23-number bets, IOL 3.0x + trailing stop + stop loss
// v5.0: Trailing stop (no multiplier gate) + trail-aware bet cap + stop loss
//   trail 8/60 + SL 15%: +$54 median, 0.1% bust, 71.6% win
//
// Coverage: 23/37 = 62.2% (18 color numbers + 5 extra)
// Win payout: +0.565x total bet (36/23 - 1, equal weight per number)
// Miss: 14/37 = 37.8%

strategyTitle = "COBRA";
version = "5.0.1";
author = "stanz";
scripter = "stanz";

game = "roulette";

// USER CONFIG
// ============================================================
//
// RISK PRESETS (23-number pure bets, 5k spins, $1000 bank, with trailing stop):
//
//   Stop | Trail  | Vault | Median | Bust%  | Win%  | Profile
//  ------|--------|-------|--------|--------|-------|----------
//   15%  | 8/60   | none  | +$54   |  0.1%  | 71.6% | Safe (recommended)
//   15%  | 5/80   | none  | +$42   |  0.1%  | 80.2% | Conservative
//   20%  | 8/60   | none  | +$61   |  0.1%  | 71.6% | Balanced
//   none | 8/60   | 3%    | grind  |  ~25%  | ~61%  | Vault-and-grind
//  Note: trail fires mid-IOL (no multiplier gate). Lock=60% = exit
//  when profit drops to 60% of peak (40% cushion).
//
divider = 10000;
increaseOnLossPercent = 200; // IOL: 200 = multiply by 3.0x on loss.

// Color: "red" or "black"
betColor = "red";

// Extra numbers: 5 numbers NOT covered by your color choice
// If red: pick from black numbers or green
// Black numbers: 2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35
// Pick any 5 — all equivalent due to RNG
extraNumbers = [2, 4, 6, 8, 10];

// Trailing stop config
trailActivatePct = 10;  // activate trailing stop after profit exceeds this %
trailLockPct = 60;     // exit if profit drops below this % of peak (40% cushion)

// Stop loss (% of starting balance). Set 0 to disable.
stopOnLoss = 15;

// Vault-and-continue (% of starting balance). Set 0 to disable.
vaultPct = 0;
stopTotalPct = 15;

// Other stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopAfterHands = 0;

// Reset stats/console on start
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

startBalance = balance;
iol = 1 + increaseOnLossPercent / 100;
totalNumbers = 18 + extraNumbers.length; // 23

// Equal-weight bet calculation
// C = 18.5Y, Total = C + N*Y = (18.5 + N)*Y where N = extraNumbers.length
// Y = totalBet / (18.5 + N), C = 18.5 * Y
baseTotalBet = startBalance / divider;
numBetUnit = baseTotalBet / (18.5 + extraNumbers.length);
colorBetUnit = 18.5 * numBetUnit;

// Enforce minimum bet ($0.00101 on Shuffle)
minBet = 0.00101;
if (numBetUnit < minBet) {
  numBetUnit = minBet;
  colorBetUnit = 18.5 * numBetUnit;
  baseTotalBet = colorBetUnit + extraNumbers.length * numBetUnit;
  log("#FFFF2A", "Min bet enforced: num=$" + numBetUnit.toFixed(5) + ", total=$" + baseTotalBet.toFixed(5));
}

// Win payout fraction: (37 - 2*N) / (37 + 2*N) where N = extra numbers
winFraction = (37 - 2 * extraNumbers.length) / (37 + 2 * extraNumbers.length);

// Thresholds from percentages
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;

// All number bets — equal bet per number for equal payout
// 23 numbers, each gets totalBet/23. Win = 36*(totalBet/23) - totalBet = (36/23 - 1)*totalBet = +0.565x
// This is pure number bets, same as Profit R/B but with 23 numbers equally weighted
redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
blackNumbers = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35];
colorNumbers = betColor === "red" ? redNumbers : blackNumbers;
allCovered = colorNumbers.concat(extraNumbers);
betPerNumber = baseTotalBet / allCovered.length;

// Override winFraction for pure number bets
winFraction = 36 / allCovered.length - 1; // +0.565x for 23 numbers

function buildSelection(multiplier) {
  sel = {};
  betAmt = betPerNumber * multiplier;
  if (betAmt < minBet) betAmt = minBet;
  for (i = 0; i < allCovered.length; i++) {
    sel["number" + allCovered[i]] = betAmt;
  }
  return sel;
}

selection = buildSelection(1);

// Max survivable LS
function calcMaxLS() {
  cumulative = 0;
  bet = baseTotalBet;
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
spinsPlayed = 0;
peakProfit = 0;
totalWagered = 0;
profitAtLastVault = 0;
totalVaulted = 0;
vaultCount = 0;
maxBetSeen = baseTotalBet;
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
    "#FF4500",
    "================================\n COBRA v" + version +
    "\n================================\n by " + author + " | Color+" + extraNumbers.length + " Profit + Trail" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentTotal = baseTotalBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  profitRate = spinsPlayed > 0 ? (profit / spinsPlayed * 100).toFixed(2) : "0.00";
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

  log("#70FD70", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentTotal.toFixed(4) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log("#FF6B6B", "LS: " + lossStreak + " | WS: " + winStreak + runwayBar);
  log("#4FFB4F", "ASSETS: $" + totalAssets.toFixed(2) + assetBar + " | P&L: $" + profit.toFixed(2));
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#A4FD68", vaultBar + targetBar);
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Rate: $" + profitRate + "/100s | Coverage: " + totalNumbers + "/37 (" + betColor + "+" + extraNumbers.length + ")");
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);
  log("#8B949E", "IOL chain: " + recoveries + " recovered | " + (lossStreak > 0 ? "LS " + lossStreak + " at " + currentMultiplier.toFixed(1) + "x" : "base bet"));
  log("#FD71FD", "Spins: " + spinsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(2) + " | Best Recovery: $" + biggestRecovery.toFixed(2) + " | Max LS: " + maxSurvivableLS);
}

// ============================================================
// COBRA STRATEGY — Pure IOL
// ============================================================

function mainStrategy() {
  spinsPlayed++;

  handPnL = lastBet.payout - lastBet.amount;
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
    recoveryAmt = baseTotalBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    selection = buildSelection(1);
  } else {
    currentChainCost += lastBet.amount;
    currentMultiplier *= iol;

    // Soft bust check: if IOL bet exceeds balance, reset to base
    nextTotal = baseTotalBet * currentMultiplier;
    if (nextTotal > balance * 0.95) {
      log("#FD6868", "IOL bet $" + nextTotal.toFixed(2) + " exceeds balance $" + balance.toFixed(2) + " — resetting to base");
      currentMultiplier = 1;
      currentChainCost = 0;
    }

    // Trail-aware bet cap
    if (trailActive) {
      trailFloor = peakProfit * trailLockPct / 100;
      maxTrailBet = profit - trailFloor;
      nextTotal = baseTotalBet * currentMultiplier;
      if (maxTrailBet > 0 && nextTotal > maxTrailBet) {
        currentMultiplier = maxTrailBet / baseTotalBet;
        if (currentMultiplier < 1) currentMultiplier = 1;
      }
    }

    selection = buildSelection(currentMultiplier);
  }

  currentTotal = baseTotalBet * currentMultiplier;
  if (currentTotal > maxBetSeen) maxBetSeen = currentTotal;
}

// ============================================================
// TRAILING STOP
// ============================================================

function trailingStopCheck() {
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
  }

  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;

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
    baseTotalBet = startBalance / divider;
    betPerNumber = baseTotalBet / allCovered.length;
    selection = buildSelection(1);
    maxSurvivableLS = calcMaxLS();
  }
}

function stopProfitCheck() {
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentMultiplier <= 1.01) {
    log("#4FFB4F", "Target reached! Profit: $" + profit.toFixed(2) + " (Vaulted: $" + totalVaulted.toFixed(2) + " + Current: $" + (profit - profitAtLastVault).toFixed(2) + ")");
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
  stopLossThreshold = startBalance * stopOnLoss / 100;
  if (stopOnLoss > 0 && profit < -stopLossThreshold) {
    log("#FD6868", "STOP LOSS! Lost $" + (-profit).toFixed(2) + " (>" + stopOnLoss + "% of $" + startBalance.toFixed(2) + ")");
    stopped = true;
    logSummary();
    engine.stop();
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#70FD70", "Starting balance: $" + startBalance.toFixed(2));
log("#42CAF7", "Total bet: $" + baseTotalBet.toFixed(4) + " | Per number: $" + betPerNumber.toFixed(5) + " x" + allCovered.length);
log("#FF4500", "IOL " + iol + "x | " + betColor + " + numbers [" + extraNumbers.join(",") + "] | Win: +" + (winFraction * 100).toFixed(1) + "%");
log("#FFDB55", "Coverage: " + totalNumbers + "/37 (" + (totalNumbers / 37 * 100).toFixed(0) + "%) | Max LS: " + maxSurvivableLS);
log("#FFD700", "Trailing stop: activate at " + trailActivatePct + "% ($" + trailActivateThreshold.toFixed(2) + "), lock " + trailLockPct + "% of peak");
vaultLabel = vaultPct > 0 ? "Vault at " + vaultPct + "% ($" + vaultProfitsThreshold.toFixed(2) + ")" : "No vault";
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% ($" + stopOnTotalProfit.toFixed(2) + ")" : "No fixed stop";
slLabel = stopOnLoss > 0 ? " | SL at " + stopOnLoss + "%" : "";
log("#4FFB4F", vaultLabel + " | " + stopLabel + slLabel);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  trailingStopCheck();
  if (stopped) return;
  await vaultHandle();
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && spinsPlayed >= stopAfterHands) {
    log("#FFFF2A", "Dev stop: " + spinsPlayed + " spins reached");
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
    "#FF4500",
    "================================\n COBRA v" + version + " — " + exitType + "\n================================"
  );
  totalAssetsFinal = balance + totalVaulted;
  log("#4FFB4F", "ASSETS: $" + totalAssetsFinal.toFixed(2) + " (Bal $" + balance.toFixed(2) + " + Vault $" + totalVaulted.toFixed(2) + ") | P&L: $" + profit.toFixed(2));
  log("Spins: " + spinsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Vaults: " + vaultCount);
  log("RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(2) + " | Best Recovery: $" + biggestRecovery.toFixed(2) + " | Recoveries: " + recoveries);
  log("Final bet: $" + (baseTotalBet * currentMultiplier).toFixed(4) + " (" + currentMultiplier.toFixed(1) + "x) | Balance: $" + balance.toFixed(2));
  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
  log("#8B949E", "IOL chains recovered: " + recoveries + " | Max LS: " + longestLossStreak + " | Max survivable: " + maxSurvivableLS);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
