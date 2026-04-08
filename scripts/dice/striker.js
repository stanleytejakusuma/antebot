// STRIKER v3.0 — Fast Profit Dice Strategy
// 50% chance (+0.98x payout), flat absorb → Martingale 3x, trail-from-start.
// ~120 bets per session. Tight exits, clean recovery.
//
// WHY 50%: Each recovery win pays +0.98x (nearly 2x your bet). At 65%,
//   recovery only pays +0.52x. The higher payout MORE than compensates
//   for the lower win rate.
//
// v3.0 FIX: dalCap=1 eliminates LS=2 structural leak. Old dalCap=2
//   created unrecoverable 2-loss chains (cost 3u, recovery 2u = -1u every time).
//   dalCap=1: flat absorb 1st loss, Mart 3x on 2nd. LS=2 now recovers +0.94u.
//   Range tightened 5%→3% for less house edge exposure (ED 0.31%→0.15%).
//
// Scorecard ($100, 5k sessions): G=-0.23%, Grade A+, HL=298, 0% bust
//   vs v2.0.1: G improved 2.3x (-0.52% → -0.23%)
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat) / STRIKER (Dice)

strategyTitle = "STRIKER";
version = "3.0.0";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
chance = 50;
divider = 2500;      // $0.80 base on $2000 bank — tighter control

// Flat absorb → Martingale hybrid
dalCap = 1;          // Absorb 1st loss at flat, then Mart 3x. Fixes LS=2 leak.
martIOL = 3.0;

// Bet cap
betCapPct = 10;

// Trail from start — active from bet 1, no SL needed
trailActivatePct = 0;  // 0 = trail active immediately (no activation threshold)
trailRangePct = 3;     // Exit if profit drops 3% of bank below peak. Grade: A+, G=-0.23%

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(1000);
  resetSeed();
}

resetStats();
clearConsole();

target = chanceToMultiplier(chance);
startBalance = balance;
baseBet = startBalance / divider;
if (baseBet < 0.00101) baseBet = 0.00101;

betSize = baseBet;
betHigh = true;
winPayout = 99 / chance - 1;

// Thresholds
trailActivateThreshold = trailActivatePct > 0 ? startBalance * trailActivatePct / 100 : 0;
trailRange = startBalance * trailRangePct / 100;

// State
currentMultiplier = 1;
dalUnits = 1;
inMart = false;
consecLosses = 0;
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
totalWins = 0;
totalLosses = 0;
betsPlayed = 0;
peakProfit = 0;
totalWagered = 0;
maxBetSeen = baseBet;
recoveries = 0;
currentChainCost = 0;
biggestRecovery = 0;
dalPhaseHands = 0;
martPhaseHands = 0;
trailActive = trailActivatePct === 0 ? true : false;
trailFloor = 0;
trailStopFired = false;
stopped = false;
summaryPrinted = false;

// ============================================================
// STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  if (lastBet.win) {
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;

    recoveryAmt = betSize;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    dalUnits = 1;
    inMart = false;
    consecLosses = 0;
    betSize = baseBet;
  } else {
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;

    currentChainCost += lastBet.amount;
    consecLosses++;

    if (dalCap > 0 && !inMart && consecLosses < dalCap) {
      dalUnits++;
      currentMultiplier = dalUnits;
      dalPhaseHands++;
    } else {
      if (!inMart) {
        inMart = true;
        currentMultiplier = dalUnits;
      } else {
        currentMultiplier *= martIOL;
      }
      martPhaseHands++;
    }

    // Soft bust
    nextBet = baseBet * currentMultiplier;
    if (nextBet > balance * 0.95) {
      currentMultiplier = 1;
      dalUnits = 1;
      inMart = false;
      consecLosses = 0;
      currentChainCost = 0;
    }

    betSize = baseBet * currentMultiplier;
  }

  // Bet cap
  if (betCapPct > 0) {
    maxBetAllowed = balance * betCapPct / 100;
    if (betSize > maxBetAllowed) betSize = maxBetAllowed;
  }

  // Trail-aware bet cap
  if (trailActive) {
    trailFloor = peakProfit - trailRange;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && betSize > maxTrailBet) betSize = maxTrailBet;
  }

  if (betSize < 0.00101) betSize = 0.00101;
  if (betSize > maxBetSeen) maxBetSeen = betSize;
  if (profit > peakProfit) peakProfit = profit;
}

// ============================================================
// LOGGING — compact, no clearConsole spam
// ============================================================

function scriptLog() {
  clearConsole();
  log(
    "#FF4500",
    "================================\n STRIKER v" + version +
    "\n================================\n " + chance + "% dice | dal=" + dalCap + " mart=" + martIOL + "x | trail-from-start range=" + trailRangePct + "%"
  );

  phase = inMart ? "MART " + currentMultiplier.toFixed(0) + "x" : "FLAT";
  pctPnL = (profit / startBalance * 100).toFixed(1);
  pctPeak = (peakProfit / startBalance * 100).toFixed(1);

  log("#FF4500", "$" + balance.toFixed(2) + " | Bet: $" + betSize.toFixed(4) + " | " + phase);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " (" + pctPnL + "%) | Peak: $" + peakProfit.toFixed(2) + " (" + pctPeak + "%)");

  // Trail / SL status
  if (trailActive) {
    trailFloor = peakProfit - trailRange;
    cushion = profit - trailFloor;
    log("#FFD700", "TRAIL: floor $" + trailFloor.toFixed(2) + " | cushion $" + cushion.toFixed(2) + " | peak $" + peakProfit.toFixed(2));
  } else {
    log("#FFDB55", "Ranging... floor $" + (peak - trailRange).toFixed(2));
  }

  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Bets: " + betsPlayed + " | Wag: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

log("#FF4500", "STRIKER v" + version + " | " + chance + "% dice | $" + baseBet.toFixed(4) + " base");
log("#FF4500", "Trail from start | Range: " + trailRangePct + "% ($" + trailRange.toFixed(2) + ") | Grade: A+");
log("#42CAF7", "Flat absorb " + dalCap + " → Mart " + martIOL + "x | Bet cap: " + betCapPct + "%");

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();

  // Trail activation
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
  }

  // Trail fire
  if (trailActive) {
    trailFloor = peakProfit - trailRange;
    if (profit <= trailFloor) {
      trailStopFired = true;
      stopped = true;
      playHitSound();
      logSummary("TRAIL EXIT");
      engine.stop();
      return;
    }
  }

});

function logSummary(exitType) {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  clearConsole();
  pctPnL = (profit / startBalance * 100).toFixed(1);
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  log(
    "#FF4500",
    "================================\n STRIKER v" + version + " — " + exitType +
    "\n================================"
  );
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " (" + pctPnL + "%) | Balance: $" + balance.toFixed(2));
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | RTP: " + rtpFinal + "%");
  log("Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Max LS: " + longestLossStreak + " | Max WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("#8B949E", "Hybrid: DAL=" + dalPhaseHands + " | MART=" + martPhaseHands + " | dal=" + dalCap + " mart=" + martIOL + "x");
  if (trailStopFired) {
    log("#FFD700", "Trail: exited at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary("MANUAL STOP");
});
