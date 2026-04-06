// MAMBA TURBO v1.0 — Dice IOL + Capitalize
// 65% chance, IOL 3.0x + 3x bet on win streaks
// Same profit as MAMBA, 2.6x faster sessions, +81% wager/hr
//
// Monte Carlo vs MAMBA (stop=15%, $1000 bank):
//   MAMBA:       +$150 median,  9.6% bust, 7.3 min, $24k wager/hr
//   TURBO:       +$150 median, 14.3% bust, 2.6 min, $43k wager/hr
//
// Capitalize: after capStreak wins, bet capMult*base for capMax bets.
// Loss during cap: enter IOL recovery. Adds wager + speed, not profit.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) / TURBO (Dice+Cap)

strategyTitle = "MAMBA TURBO";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
//
// RISK PRESETS (10k bets, $1000 bank):
//
//   Stop | Median | Bust%  | Win%  | Time  | Wager/hr | Profile
//  ------|--------|--------|-------|-------|----------|----------
//    8%  | +$80   |  8.6%  | 90.1% | ~1.6m | ~$36k   | Fast safe (recommended)
//   10%  | +$100  | 10.5%  | 88.0% | ~1.9m | ~$38k   | Fast moderate
//   15%  | +$150  | 14.3%  | 83.7% | ~2.6m | ~$43k   | Fast aggressive
//   20%  | +$200  | 17.9%  | 79.4% | ~3.3m | ~$43k   | Fast very aggressive
//   30%  | +$300  | 24.3%  | 71.3% | ~4.8m | ~$43k   | Maximum profit per session
//
chance = 65;
divider = 10000;
increaseOnLossPercent = 200; // IOL: 200 = multiply by 3.0x on loss.

// Capitalize: boost bet on win streaks
capStreak = 3;    // consecutive wins to trigger capitalize
capMax = 3;       // max capitalize bets
capMult = 3.0;    // bet multiplier during capitalize (3x base)

// Bet direction: true = over, false = under
betHigh = true;

// Vault-and-continue (% of starting balance). Set 0 to disable.
vaultPct = 0;
stopTotalPct = 8;

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 0;
stopAfterHands = 0;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(1000);
  resetSeed();
  resetStats();
  clearConsole();
}

target = chanceToMultiplier(chance);
startBalance = balance;
iol = 1 + increaseOnLossPercent / 100;
winPayout = 99 / chance - 1; // +0.523x at 65%

baseBet = startBalance / divider;

// Enforce minimum bet ($0.00101 on Shuffle)
minBet = 0.00101;
if (baseBet < minBet) {
  baseBet = minBet;
  log("#FFFF2A", "Min bet enforced: $" + baseBet.toFixed(5));
}

betSize = baseBet;

// Thresholds from percentages
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;

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

// Capitalize state
mode = "strike"; // "strike" or "cap"
capCount = 0;
capActivations = 0;
capWins = 0;
capLosses = 0;
strikeBets = 0;
capBets = 0;

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00FF7F",
    "================================\n MAMBA TURBO v" + version +
    "\n================================\n by " + author + " | Dice " + chance + "% IOL+Cap" +
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

  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(5) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log("#FF6B6B", "LS: " + lossStreak + " | WS: " + winStreak + runwayBar);
  log("#4FFB4F", "ASSETS: $" + totalAssets.toFixed(2) + assetBar + " | P&L: $" + profit.toFixed(2));
  log("#A4FD68", "Peak: $" + peakProfit.toFixed(2) + ddBar + vaultBar + targetBar);
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Rate: $" + profitRate + "/100b | Chance: " + chance + "% (+" + (winPayout * 100).toFixed(1) + "%)");
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);
  modeBar = mode === "cap" ? "CAP " + capCount + "/" + capMax + " (" + capMult + "x)" : "STRIKE";
  log("#FF9500", "Mode: " + modeBar + " | Cap: " + capActivations + " fired, W/L " + capWins + "/" + capLosses + " | Strike: " + strikeBets + " Cap: " + capBets);
  log("#8B949E", "IOL chain: " + recoveries + " recovered | " + (lossStreak > 0 ? "LS " + lossStreak + " at " + currentMultiplier.toFixed(1) + "x" : "base bet"));
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Max LS: " + maxSurvivableLS);
}

// ============================================================
// MAMBA TURBO — IOL + Capitalize
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

  // STRIKE mode: IOL on loss, check for capitalize trigger on win
  if (mode === "strike") {
    strikeBets++;
    if (isWin) {
      recoveryAmt = baseBet * currentMultiplier;
      if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
      if (currentChainCost > 0) recoveries++;
      currentChainCost = 0;
      currentMultiplier = 1;
      betSize = baseBet;

      // Check capitalize trigger
      if (winStreak >= capStreak) {
        mode = "cap";
        capCount = 0;
        capActivations++;
        betSize = baseBet * capMult;
      }
    } else {
      currentChainCost += lastBet.amount;
      currentMultiplier *= iol;

      // Soft bust
      nextBet = baseBet * currentMultiplier;
      if (nextBet > balance * 0.95) {
        log("#FD6868", "IOL $" + nextBet.toFixed(2) + " > balance $" + balance.toFixed(2) + " — reset");
        currentMultiplier = 1;
        currentChainCost = 0;
      }

      betSize = baseBet * currentMultiplier;
    }

  // CAP mode: ride the streak with boosted bets
  } else if (mode === "cap") {
    capBets++;
    capCount++;

    if (isWin) {
      capWins++;
      if (capCount >= capMax) {
        // Cap complete — back to strike
        mode = "strike";
        winStreak = 0;
        currentMultiplier = 1;
        currentChainCost = 0;
        betSize = baseBet;
      } else {
        // Keep capitalizing — scale up
        betSize = Math.min(betSize * capMult, baseBet * 50);
      }
    } else {
      capLosses++;
      // Loss during cap — enter IOL recovery
      mode = "strike";
      winStreak = 0;
      currentChainCost = lastBet.amount;
      currentMultiplier = iol;

      // Soft bust
      nextBet = baseBet * currentMultiplier;
      if (nextBet > balance * 0.95) {
        currentMultiplier = 1;
        currentChainCost = 0;
      }

      betSize = baseBet * currentMultiplier;
    }
  }

  if (betSize < minBet) betSize = minBet;
  currentBet = betSize;
  if (currentBet > maxBetSeen) maxBetSeen = currentBet;
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
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && mode === "strike" && currentMultiplier <= 1.01) {
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
log("#FF9500", "Capitalize: " + capMult + "x bet after " + capStreak + " wins, max " + capMax + " bets");
vaultLabel = vaultPct > 0 ? "Vault at " + vaultPct + "% ($" + vaultProfitsThreshold.toFixed(2) + ")" : "No vault";
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% ($" + stopOnTotalProfit.toFixed(2) + ")" : "No stop";
log("#4FFB4F", vaultLabel + " | " + stopLabel);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
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
  log(
    "#00FF7F",
    "================================\n MAMBA TURBO — Session Over\n================================"
  );
  totalAssetsFinal = balance + totalVaulted;
  log("#4FFB4F", "ASSETS: $" + totalAssetsFinal.toFixed(2) + " (Bal $" + balance.toFixed(2) + " + Vault $" + totalVaulted.toFixed(2) + ") | P&L: $" + profit.toFixed(2));
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Vaults: " + vaultCount);
  log("RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("Final bet: $" + (baseBet * currentMultiplier).toFixed(5) + " (" + currentMultiplier.toFixed(1) + "x) | Balance: $" + balance.toFixed(2));
  log("#FF9500", "Capitalize: " + capActivations + " fired | Cap W/L: " + capWins + "/" + capLosses + " | Strike: " + strikeBets + " Cap: " + capBets);
  log("#8B949E", "IOL chains recovered: " + recoveries + " | Max LS: " + longestLossStreak + " | Max survivable: " + maxSurvivableLS);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
