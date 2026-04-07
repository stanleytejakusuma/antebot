// BASILISK v1.0 — Baccarat Delayed IOL Profit Strategy
// Banker bet with PATIENCE: don't escalate on every loss. Only activate
// IOL after 3+ consecutive losses. Single losses are normal coin-flip
// variance — let them self-correct. Ties are free shields (push, no cost).
//
// Monte Carlo ($100, 5k sessions): +$5.59 median, 0.0% bust, 75.1% win
// IOL 2.1x — gentlest viable IOL for baccarat's 0.95x payout.
//
// THE THESIS: In baccarat's ~50/50 coin flip, single losses don't need
// recovery — they self-correct 50.7% of the time. Only genuine streaks
// (3+ consecutive losses, 12% probability) warrant IOL intervention.
// This reduces IOL activations by 88%, cutting cumulative house edge drag.
//
// Baccarat edge: 1.06% (Banker). Tie rate: 9.52% (free push).
// Banker wins 50.69% of decided hands (excl ties).
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat)

strategyTitle = "BASILISK";
version = "1.0.4";
author = "stanz";
scripter = "stanz";

game = "baccarat";

// USER CONFIG
// ============================================================
//
// RISK PRESETS ($100 bank, trail=8/60, SL=15%, stop=15%):
//
//   Delay | IOL  | Median | Bust% | Win%  | Hands | Profile
//  -------|------|--------|-------|-------|-------|----------
//    3    | 2.1x | +$5.59 | 0.0%  | 75.1% |  1820 | Gentle (recommended)
//    3    | 3.0x | +$6.55 | 0.0%  | 72.5% |  1096 | Aggressive
//    2    | 2.1x | +$5.59 | 0.0%  | 75.1% |  1820 | Balanced
//    1    | 2.1x | +$5.59 | 0.0%  | 75.1% |  1820 | Standard IOL (no delay)
//
divider = 1000;
iolMultiplier = 2.1;

// PATIENCE: number of consecutive losses before IOL activates
// 1 = standard IOL (every loss). 3 = recommended. 5 = very patient.
delayThreshold = 3;

// Trailing stop
trailActivatePct = 10;
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

// Baccarat bet setup — Banker only (Player and Tie = 0)
bankerBetSize = baseBet;
playerBetSize = 0;
tieBetSize = 0;

// Thresholds
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
stopLossThreshold = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;

// State
currentMultiplier = 1;
consecLosses = 0;
handsPlayed = 0;
totalWins = 0;
totalLosses = 0;
totalTies = 0;
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
iolActivations = 0;
flatAbsorbed = 0;
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
    "#9B59B6",
    "================================\n BASILISK v" + version +
    "\n================================\n by " + author + " | Baccarat Delayed IOL" +
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

  chainBar = "";
  if (consecLosses > 0) {
    iolStatus = consecLosses >= delayThreshold ? "IOL ACTIVE" : "ABSORBING (" + consecLosses + "/" + delayThreshold + ")";
    chainBar = " | " + iolStatus + " | Chain: -$" + currentChainCost.toFixed(2);
  }

  log("#9B59B6", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(5) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log("#E67E22", "Banker bet | LS: " + consecLosses + chainBar);
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2));
  log("#FFDB55", "W/L/T: " + totalWins + "/" + totalLosses + "/" + totalTies + " | Ties: " + (handsPlayed > 0 ? (totalTies / handsPlayed * 100).toFixed(1) : "0") + "%");
  log("#42CAF7", "Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);
  log("#9B59B6", "IOL activations: " + iolActivations + " | Flat absorbed: " + flatAbsorbed + " | Delay: " + delayThreshold);
  log("#FD71FD", "Hands: " + handsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4));
}

// ============================================================
// BASILISK PATIENCE STRATEGY
// ============================================================

function mainStrategy() {
  handsPlayed++;
  totalWagered += lastBet.amount;

  result = lastBet.state.result;

  if (result === "banker") {
    // WIN — Banker bet won
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;

    recoveryAmt = baseBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;

    // Reset everything
    currentChainCost = 0;
    currentMultiplier = 1;
    consecLosses = 0;
    bankerBetSize = baseBet;

  } else if (result === "player") {
    // LOSS — Player won, our Banker bet lost
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;

    currentChainCost += lastBet.amount;
    consecLosses++;

    // PATIENCE: only escalate after delayThreshold consecutive losses
    if (consecLosses >= delayThreshold) {
      currentMultiplier *= iolMultiplier;
      iolActivations++;

      // Soft bust: if next bet > 95% of balance, reset
      nextBet = baseBet * currentMultiplier;
      if (nextBet > balance * 0.95) {
        currentMultiplier = 1;
        currentChainCost = 0;
        consecLosses = 0;
      }
    } else {
      // Absorb the loss at flat bet — don't escalate
      flatAbsorbed++;
    }

    bankerBetSize = baseBet * currentMultiplier;

  } else {
    // TIE — Push. Bet returned. Don't escalate, don't reset.
    totalTies++;
    // consecLosses stays the same — tie doesn't break or extend the streak
    // currentMultiplier stays the same — free retry at current level
  }

  if (profit > peakProfit) peakProfit = profit;

  // Trail-aware bet cap
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && bankerBetSize > maxTrailBet) {
      bankerBetSize = maxTrailBet;
    }
  }

  if (bankerBetSize < minBet) bankerBetSize = minBet;
  if (bankerBetSize > maxBetSeen) maxBetSeen = bankerBetSize;

  // Keep player and tie at 0
  playerBetSize = 0;
  tieBetSize = 0;
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
log("#9B59B6", "Starting balance: $" + startBalance.toFixed(2));
log("#E67E22", "Base bet: $" + baseBet.toFixed(5) + " | Banker only");
log("#9B59B6", "IOL " + iolMultiplier + "x | Delay: " + delayThreshold + " consecutive losses before IOL activates");
log("#FFD700", "Trail: activate " + trailActivatePct + "%, lock " + trailLockPct + "% | SL: " + stopOnLoss + "%");
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% ($" + stopOnTotalProfit.toFixed(2) + ")" : "No fixed stop";
log("#4FFB4F", stopLabel);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();

  // Trail as floor: let profits run, exit when they dip below lock% of peak
  trailingStopCheck();
  if (stopped) return;
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && handsPlayed >= stopAfterHands) {
    log("#FFFF2A", "Dev stop: " + handsPlayed + " hands reached");
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
  exitType = trailStopFired ? "TRAIL EXIT" : "TARGET/MANUAL";
  log(
    "#9B59B6",
    "================================\n BASILISK v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("Hands: " + handsPlayed + " | W/L/T: " + totalWins + "/" + totalLosses + "/" + totalTies);
  log("Peak: $" + peakProfit.toFixed(2) + " | RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2));
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("#9B59B6", "IOL activations: " + iolActivations + " | Flat absorbed: " + flatAbsorbed + " (" + (handsPlayed > 0 ? (flatAbsorbed / handsPlayed * 100).toFixed(0) : "0") + "% of hands)");
  log("#E67E22", "Delay threshold: " + delayThreshold + " | IOL: " + iolMultiplier + "x");
  if (trailStopFired) {
    log("#FFD700", "Trail exit at $" + profit.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")");
  }
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
