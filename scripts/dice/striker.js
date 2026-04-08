// STRIKER v1.0 — Fast Profit Dice Strategy
// 50% chance (+0.98x payout), D'Alembert 2 → Martingale 3x, hard stops.
// Hit +10%, walk away. Hit -10%, cut and retry. ~150 bets per session.
//
// WHY 50%: Each recovery win pays +0.98x (nearly 2x your bet). At 65%,
//   recovery only pays +0.52x. The higher payout MORE than compensates
//   for the lower win rate. D'Alembert absorbed losses are fully covered.
//
// Scorecard ($100, 5k sessions): G=-1.45%, +$10.02 median, 0% bust, 57% win
//   vs MAMBA v3.1: G improved 3.5x (-5.13% → -1.45%)
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat) / STRIKER (Dice)

strategyTitle = "STRIKER";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
chance = 50;
divider = 2000;      // Big bets — $0.65 base on $1300 bank

// D'Alembert → Martingale hybrid
dalCap = 2;          // Linear +1 unit for first 2 losses, then Mart
martIOL = 3.0;

// Bet cap
betCapPct = 15;

// Hard stops — no trail, just grab profit or cut loss
stopProfitPct = 10;  // +10% → stop and walk away
stopLossPct = 10;    // -10% → cut and retry next session

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
stopProfit = startBalance * stopProfitPct / 100;
stopLoss = startBalance * stopLossPct / 100;

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
    "\n================================\n " + chance + "% dice | dal=" + dalCap + " mart=" + martIOL + "x | TP " + stopProfitPct + "% / SL " + stopLossPct + "%"
  );

  phase = inMart ? "MART " + currentMultiplier.toFixed(0) + "x" : "DAL " + dalUnits + "/" + dalCap;
  pctPnL = (profit / startBalance * 100).toFixed(1);
  pctPeak = (peakProfit / startBalance * 100).toFixed(1);

  log("#FF4500", "$" + balance.toFixed(2) + " | Bet: $" + betSize.toFixed(4) + " | " + phase);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " (" + pctPnL + "%) | Peak: $" + peakProfit.toFixed(2) + " (" + pctPeak + "%)");

  // Progress bar toward TP or SL
  if (profit >= 0) {
    pctToTP = Math.min(100, profit / stopProfit * 100).toFixed(0);
    log("#00FF7F", "TP: " + pctToTP + "% → $" + stopProfit.toFixed(2));
  } else {
    pctToSL = Math.min(100, (-profit) / stopLoss * 100).toFixed(0);
    log("#FD6868", "SL: " + pctToSL + "% → -$" + stopLoss.toFixed(2));
  }

  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Bets: " + betsPlayed + " | Wag: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

log("#FF4500", "STRIKER v" + version + " | " + chance + "% dice | $" + baseBet.toFixed(4) + " base");
log("#FF4500", "TP: +$" + stopProfit.toFixed(2) + " (" + stopProfitPct + "%) | SL: -$" + stopLoss.toFixed(2) + " (" + stopLossPct + "%)");
log("#42CAF7", "D'Alembert " + dalCap + " → Mart " + martIOL + "x | Bet cap: " + betCapPct + "%");

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();

  // Hard profit stop
  if (profit >= stopProfit && currentMultiplier <= 1.01) {
    stopped = true;
    playHitSound();
    logSummary("TARGET HIT");
    engine.stop();
    return;
  }

  // Hard stop loss
  if (profit < -stopLoss) {
    stopped = true;
    logSummary("STOP LOSS");
    engine.stop();
    return;
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
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary("MANUAL STOP");
});
