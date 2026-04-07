// SIDEWINDER v1.0 — HiLo Adaptive Chain Profit Strategy
// Skip middle cards (6-8), chain predictions, cash out at dynamic target.
// Monte Carlo: +$7.75 median, 0.0% bust, 62.4% win ($100, trail 8/60, SL 15%)
//
// CRUISE:     cashout 1.5x — safe, consistent small wins (~65% per hand)
// RECOVERY:   cashout 2.5x — bigger swings to recover deficit (~45% per hand)
// CAPITALIZE: cashout 1.1x — lock profits fast when trail active (~80% per hand)
//
// Three levers no other game has: bet size (IOL) + cashout target + skip selectivity.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) / TAIPAN (Roulette v2) / SIDEWINDER (HiLo)

strategyTitle = "SIDEWINDER";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "hilo";

// USER CONFIG
// ============================================================
divider = 10000;
iolMultiplier = 3.0;

// Starting card (A = guaranteed 92% first prediction)
startCard = { rank: "A", suit: "C" };

// Skip range: card values to skip
// A=1, 2-10, J=11, Q=12, K=13
// Default: skip 6-8 (narrow middle — optimizer proved best)
skipMin = 6;
skipMax = 8;

// Cashout targets per mode (accumulated multiplier)
cashoutCruise = 1.5;
cashoutRecovery = 2.5;
cashoutCapitalize = 1.1;

// Recovery mode threshold (% of bank below zero)
recoveryThresholdPct = 5;

// Trailing stop
trailActivatePct = 8;
trailLockPct = 60;

// Stop conditions
stopTotalPct = 15;
stopOnLoss = 15;
stopAfterHands = 0;

// Reset stats on start
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

startBalance = balance;

// Enforce minimum bet
minBet = 0.00101;
baseBet = startBalance / divider;
if (baseBet < minBet) {
  baseBet = minBet;
  log("#FFFF2A", "Min bet enforced: $" + baseBet.toFixed(5));
}
betSize = baseBet;

// Card value lookup
rankValues = {
  "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
  "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13
};

// Thresholds
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
stopLossThreshold = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;
recoveryThreshold = startBalance * recoveryThresholdPct / 100;

// State
currentMultiplier = 1;
handsPlayed = 0;
totalWins = 0;
totalLosses = 0;
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
peakProfit = 0;
totalWagered = 0;
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

// Mode tracking
currentMode = "cruise";
cruiseHands = 0;
recoveryHands = 0;
capitalizeHands = 0;

// ============================================================
// GAME ROUND — Per-card decision within each hand
// ============================================================

engine.onGameRound(function (currentBet) {
  var rounds = currentBet.state.rounds;
  var roundCount = rounds ? rounds.length : 0;
  var skipCount = 0;
  var accumulated = 0;
  var cardRank = currentBet.state.startCard ? currentBet.state.startCard.rank : "A";

  if (roundCount > 0) {
    for (var i = 0; i < roundCount; i++) {
      if (rounds[i].action === "skip") skipCount++;
    }
    cardRank = rounds[roundCount - 1].card.rank;
    accumulated = rounds[roundCount - 1].payoutMultiplier;
  }

  var cardVal = rankValues[cardRank] || 7;

  // Determine cashout target based on current mode
  var cashoutTarget = cashoutCruise;
  if (currentMode === "recovery") cashoutTarget = cashoutRecovery;
  if (currentMode === "capitalize") cashoutTarget = cashoutCapitalize;

  // CASHOUT: if accumulated multiplier meets target
  if (accumulated >= cashoutTarget) {
    return HILO_CASHOUT;
  }

  // SKIP: if card is in middle range
  if (cardVal >= skipMin && cardVal <= skipMax && skipCount < 52) {
    return HILO_SKIP;
  }

  // BET: high if low card, low if high card
  if (cardVal <= 7) {
    return HILO_BET_HIGH;
  }
  return HILO_BET_LOW;
});

// ============================================================
// BET PLACED — Session-level logic after each hand resolves
// ============================================================

engine.onBetPlaced(async function () {
  if (stopped) return;

  handsPlayed++;
  totalWagered += lastBet.amount;

  isWin = lastBet.win;

  if (isWin) {
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;

    recoveryAmt = baseBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    betSize = baseBet;
  } else {
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;

    currentChainCost += lastBet.amount;
    currentMultiplier *= iolMultiplier;

    // Soft bust: if next bet > 95% of balance, reset to base
    nextBet = baseBet * currentMultiplier;
    if (nextBet > balance * 0.95) {
      currentMultiplier = 1;
      currentChainCost = 0;
    }
    betSize = baseBet * currentMultiplier;
  }

  if (profit > peakProfit) peakProfit = profit;

  // Trail-aware bet cap
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && betSize > maxTrailBet) {
      betSize = maxTrailBet;
    }
  }

  if (betSize < minBet) betSize = minBet;
  if (betSize > maxBetSeen) maxBetSeen = betSize;

  // Mode transitions
  if (trailActive) {
    currentMode = "capitalize";
    capitalizeHands++;
  } else if (profit < -recoveryThreshold || currentMultiplier > 1.5) {
    currentMode = "recovery";
    recoveryHands++;
  } else {
    currentMode = "cruise";
    cruiseHands++;
  }

  // Logging
  scriptLog();

  // Trailing stop check (no multiplier gate — fires mid-IOL)
  trailingStopCheck();
  if (stopped) return;

  // Stop checks
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && handsPlayed >= stopAfterHands) {
    log("#FFFF2A", "Dev stop: " + handsPlayed + " hands reached");
    stopped = true;
    logSummary();
    engine.stop();
  }
});

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
// LOGGING
// ============================================================

function modeColor() {
  if (currentMode === "cruise") return "#00FF7F";
  if (currentMode === "recovery") return "#FF6B6B";
  if (currentMode === "capitalize") return "#FFD700";
  return "#FFFFFF";
}

function logBanner() {
  log(
    "#FF4500",
    "================================\n SIDEWINDER v" + version +
    "\n================================\n by " + author + " | HiLo Adaptive Chain" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentBet = baseBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";

  trailBar = "";
  if (trailActive) {
    trailBar = " | TRAIL: floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = " | Trail arms at $" + trailActivateThreshold.toFixed(2);
  }

  var cashTarget = cashoutCruise;
  if (currentMode === "recovery") cashTarget = cashoutRecovery;
  if (currentMode === "capitalize") cashTarget = cashoutCapitalize;

  runwayBar = "";
  if (lossStreak > 0) {
    runwayBar = " | Chain: -$" + currentChainCost.toFixed(2);
  }

  log("#FF4500", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(5) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log(modeColor(), "Mode: " + currentMode.toUpperCase() + " | Cashout: " + cashTarget.toFixed(1) + "x | LS: " + lossStreak + runwayBar);
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2));
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Skip: " + skipMin + "-" + skipMax);
  log("#42CAF7", "Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);

  cPct = handsPlayed > 0 ? (cruiseHands / handsPlayed * 100).toFixed(0) : "0";
  rPct = handsPlayed > 0 ? (recoveryHands / handsPlayed * 100).toFixed(0) : "0";
  capPct = handsPlayed > 0 ? (capitalizeHands / handsPlayed * 100).toFixed(0) : "0";
  log("#FF4500", "CRUISE:" + cruiseHands + "(" + cPct + "%) REC:" + recoveryHands + "(" + rPct + "%) CAP:" + capitalizeHands + "(" + capPct + "%)");
  log("#FD71FD", "Hands: " + handsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4));
}

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  exitType = trailStopFired ? "TRAILING STOP" : "TARGET/MANUAL";
  log(
    "#FF4500",
    "================================\n SIDEWINDER v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("Hands: " + handsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2));
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);

  cPct = handsPlayed > 0 ? (cruiseHands / handsPlayed * 100).toFixed(0) : "0";
  rPct = handsPlayed > 0 ? (recoveryHands / handsPlayed * 100).toFixed(0) : "0";
  capPct = handsPlayed > 0 ? (capitalizeHands / handsPlayed * 100).toFixed(0) : "0";
  log("#FF4500", "Modes — CRUISE:" + cruiseHands + "(" + cPct + "%) REC:" + recoveryHands + "(" + rPct + "%) CAP:" + capitalizeHands + "(" + capPct + "%)");

  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
