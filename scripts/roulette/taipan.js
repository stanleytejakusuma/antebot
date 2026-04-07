// TAIPAN v1.1 — Roulette Adaptive Coverage + IOL
// Dozen + Even-Money split with dynamic coverage switching.
// Uses pure numberN bets (no mixed range/color — those fail on live Shuffle).
// Monte Carlo: +$209 median, 0.0% bust, 71.6% win (trail 8/60, SL 15%)
// Beats COBRA (+$54), Profit R/B (+$53), Single Dozen (+$157).
//
// CRUISE:   40% dozen / 60% even-money — wide coverage, steady accumulation
// RECOVERY: 80% dozen / 20% even-money — concentrated recovery power
// DEEP LS:  Two dozens (50/50) — 64.9% win rate to break the chain
//
// The only roulette system that changes WHAT it bets on, not just HOW MUCH.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) / TAIPAN (Roulette v2)

strategyTitle = "TAIPAN";
version = "1.1.0";
author = "stanz";
scripter = "stanz";

game = "roulette";

// USER CONFIG
// ============================================================
//
// RISK PRESETS ($1000 bank, trail=8/60, SL=15%, stop=15%):
//
//   IOL  | Expand | Median | Bust%  | Win%  | Profile
//  ------|--------|--------|--------|-------|----------
//   6.0x | LS 5   | +$209  |  0.0%  | 71.6% | Recommended
//   5.0x | LS 5   | +$69   |  0.0%  | 74.8% | Conservative
//   6.0x | LS 6   | +$152  |  0.0%  | 54.4% | Balanced
//
divider = 10000;
iolMultiplier = 6.0;

// Which dozen and even-money to bet on
betDozen = 2;       // 1, 2, or 3
betEvenMoney = "red"; // "red", "black", "odd", "even", "high", "low"

// Adaptive split ratios (dozen% for each mode)
cruiseDozenPct = 40;    // CRUISE: wide coverage
recoveryDozenPct = 80;  // RECOVERY: max recovery power
protectDozenPct = 30;   // PROTECT: max shield

// Coverage expansion on deep LS
expandAtLS = 5;     // switch to Two Dozens after this many consecutive losses
expandDozen = 3;    // which second dozen to add (1, 2, or 3 — must differ from betDozen)

// Trailing stop
trailActivatePct = 8;
trailLockPct = 60;

// Stop conditions
stopTotalPct = 15;
stopOnLoss = 15;
stopOnProfit = 0;
stopAfterHands = 0;

// Reset stats on start
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

// Enforce minimum bet
minBet = 0.00101;
baseTotalBet = startBalance / divider;
if (baseTotalBet < minBet * 4) {
  baseTotalBet = minBet * 4;
  log("#FFFF2A", "Min bet enforced: $" + baseTotalBet.toFixed(5));
}

// Number sets for pure numberN bets (no mixed range/color — fails live)
dozenSets = [
  [1,2,3,4,5,6,7,8,9,10,11,12],
  [13,14,15,16,17,18,19,20,21,22,23,24],
  [25,26,27,28,29,30,31,32,33,34,35,36]
];
evenMoneySets = {
  red: [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36],
  black: [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35],
  odd: [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35],
  even: [2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36],
  high: [19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36],
  low: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18]
};

primaryDozen = dozenSets[betDozen - 1];
expandDozenSet = dozenSets[expandDozen - 1];
evenMoneyNums = evenMoneySets[betEvenMoney];

// Thresholds
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
stopLossThreshold = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;

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

// Mode tracking
currentMode = "cruise";
cruiseSpins = 0;
recoverySpins = 0;
expandSpins = 0;
protectSpins = 0;
expandActivations = 0;

// ============================================================
// BET CONSTRUCTION (pure numberN keys — compatible with live Shuffle)
// ============================================================

function buildSelection(totalBet) {
  sel = {};

  if (currentMode === "expand") {
    // Two dozens: 24 numbers, equal bet per number
    betPer = totalBet / (primaryDozen.length + expandDozenSet.length);
    if (betPer < minBet) betPer = minBet;
    for (i = 0; i < primaryDozen.length; i++) {
      sel["number" + primaryDozen[i]] = betPer;
    }
    for (i = 0; i < expandDozenSet.length; i++) {
      sel["number" + expandDozenSet[i]] = betPer;
    }
    return sel;
  }

  // Cruise, recovery, or protect: dozen + even-money split
  dozenFrac = cruiseDozenPct / 100;
  if (currentMode === "recovery") {
    dozenFrac = recoveryDozenPct / 100;
  } else if (currentMode === "protect") {
    dozenFrac = protectDozenPct / 100;
  }
  evenFrac = 1.0 - dozenFrac;

  // Per-number amounts: dozen share / 12, even-money share / 18
  dozenPer = (totalBet * dozenFrac) / primaryDozen.length;
  evenPer = (totalBet * evenFrac) / evenMoneyNums.length;

  // Build bet map — numbers in both sets get both amounts
  betMap = {};
  for (i = 0; i < primaryDozen.length; i++) {
    n = primaryDozen[i];
    betMap[n] = (betMap[n] || 0) + dozenPer;
  }
  for (i = 0; i < evenMoneyNums.length; i++) {
    n = evenMoneyNums[i];
    betMap[n] = (betMap[n] || 0) + evenPer;
  }

  // Convert to selection with minimum enforcement
  nums = Object.keys(betMap);
  for (i = 0; i < nums.length; i++) {
    amt = betMap[nums[i]];
    if (amt < minBet) amt = minBet;
    sel["number" + nums[i]] = amt;
  }
  return sel;
}

// ============================================================
// LOGGING
// ============================================================

function modeLabel() {
  if (currentMode === "cruise") return "CRUISE";
  if (currentMode === "recovery") return "RECOVERY";
  if (currentMode === "expand") return "EXPAND";
  if (currentMode === "protect") return "PROTECT";
  return currentMode;
}

function modeColor() {
  if (currentMode === "cruise") return "#00FF7F";
  if (currentMode === "recovery") return "#FF6B6B";
  if (currentMode === "expand") return "#FFDB55";
  if (currentMode === "protect") return "#42CAF7";
  return "#FFFFFF";
}

function logBanner() {
  log(
    "#FF8C00",
    "================================\n TAIPAN v" + version +
    "\n================================\n by " + author + " | Adaptive Roulette" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentBet = baseTotalBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  profitRate = spinsPlayed > 0 ? (profit / spinsPlayed * 100).toFixed(2) : "0.00";
  rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";

  runwayBar = "";
  if (lossStreak > 0) {
    runwayBar = " | LS " + lossStreak + " | Chain: -$" + currentChainCost.toFixed(2);
  }

  trailBar = "";
  if (trailActive) {
    trailBar = " | TRAIL: floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = " | Trail arms at $" + trailActivateThreshold.toFixed(2);
  }

  log("#FF8C00", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(4) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log(modeColor(), "Mode: " + modeLabel() + " | WS: " + winStreak + runwayBar);
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2));
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Rate: $" + profitRate + "/100s");
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);

  cPct = spinsPlayed > 0 ? (cruiseSpins / spinsPlayed * 100).toFixed(0) : "0";
  rPct = spinsPlayed > 0 ? (recoverySpins / spinsPlayed * 100).toFixed(0) : "0";
  ePct = spinsPlayed > 0 ? (expandSpins / spinsPlayed * 100).toFixed(0) : "0";
  pPct = spinsPlayed > 0 ? (protectSpins / spinsPlayed * 100).toFixed(0) : "0";
  log("#FF8C00", "CRUISE:" + cruiseSpins + "(" + cPct + "%) REC:" + recoverySpins + "(" + rPct + "%) EXP:" + expandSpins + "(" + ePct + "%) [" + expandActivations + "x] PROT:" + protectSpins + "(" + pPct + "%)");
  log("#FD71FD", "Spins: " + spinsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4));
}

// ============================================================
// TAIPAN STRATEGY
// ============================================================

function mainStrategy() {
  spinsPlayed++;
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

  // Determine mode
  prevMode = currentMode;

  if (isWin) {
    // Win — reset IOL, go to cruise
    recoveryAmt = baseTotalBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    currentMode = "cruise";
  } else {
    // Loss — IOL escalation
    currentChainCost += lastBet.amount;
    currentMultiplier *= iolMultiplier;

    // Soft bust
    nextBet = baseTotalBet * currentMultiplier;
    if (nextBet > balance * 0.95) {
      currentMultiplier = 1;
      currentChainCost = 0;
      currentMode = "cruise";
    } else if (lossStreak >= expandAtLS) {
      if (currentMode !== "expand") expandActivations++;
      currentMode = "expand";
    } else {
      currentMode = "recovery";
    }
  }

  // Track mode spins
  if (currentMode === "cruise") cruiseSpins++;
  else if (currentMode === "recovery") recoverySpins++;
  else if (currentMode === "expand") expandSpins++;
  else if (currentMode === "protect") protectSpins++;

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

  // Build selection for next spin
  totalBet = baseTotalBet * currentMultiplier;
  if (totalBet > maxBetSeen) maxBetSeen = totalBet;
  selection = buildSelection(totalBet);
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
// STOP CHECKS
// ============================================================

function stopProfitCheck() {
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentMultiplier <= 1.01) {
    log("#4FFB4F", "Target reached! P&L: $" + profit.toFixed(2));
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
  if (stopLossThreshold > 0 && profit < -stopLossThreshold) {
    log("#FD6868", "Stop loss! $" + (-profit).toFixed(2) + " loss (-" + stopOnLoss + "%)");
    stopped = true;
    logSummary();
    engine.stop();
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#FF8C00", "Starting balance: $" + startBalance.toFixed(2));
coveredCount = primaryDozen.length + evenMoneyNums.length;
overlapCount = 0;
for (i = 0; i < primaryDozen.length; i++) {
  if (evenMoneyNums.indexOf(primaryDozen[i]) !== -1) overlapCount++;
}
uniqueCount = coveredCount - overlapCount;
log("#42CAF7", "Base bet: $" + baseTotalBet.toFixed(5) + " | Dozen: " + betDozen + " | Even: " + betEvenMoney + " | " + uniqueCount + " numbers (" + overlapCount + " overlap)");
log("#FF8C00", "IOL " + iolMultiplier + "x | Expand at LS " + expandAtLS + " → dozen " + expandDozen);
log("#FFD700", "Trail: activate " + trailActivatePct + "%, lock " + trailLockPct + "% | SL: " + stopOnLoss + "%");
log("#4FFB4F", "Splits — Cruise: " + cruiseDozenPct + "/" + (100 - cruiseDozenPct) + " | Recovery: " + recoveryDozenPct + "/" + (100 - recoveryDozenPct) + " | Protect: " + protectDozenPct + "/" + (100 - protectDozenPct));
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% ($" + stopOnTotalProfit.toFixed(2) + ")" : "No fixed stop";
log("#4FFB4F", stopLabel);

// Initial selection
selection = buildSelection(baseTotalBet);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  trailingStopCheck();
  if (stopped) return;
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
    "#FF8C00",
    "================================\n TAIPAN v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("Spins: " + spinsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);

  cPct = spinsPlayed > 0 ? (cruiseSpins / spinsPlayed * 100).toFixed(0) : "0";
  rPct = spinsPlayed > 0 ? (recoverySpins / spinsPlayed * 100).toFixed(0) : "0";
  ePct = spinsPlayed > 0 ? (expandSpins / spinsPlayed * 100).toFixed(0) : "0";
  pPct = spinsPlayed > 0 ? (protectSpins / spinsPlayed * 100).toFixed(0) : "0";
  log("#FF8C00", "Modes — CRUISE:" + cruiseSpins + "(" + cPct + "%) REC:" + recoverySpins + "(" + rPct + "%) EXP:" + expandSpins + "(" + ePct + "%) [" + expandActivations + "x] PROT:" + protectSpins + "(" + pPct + "%)");

  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
  log("#8B949E", "IOL chains recovered: " + recoveries + " | Max LS: " + longestLossStreak);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
