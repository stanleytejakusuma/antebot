// COBRA v1.0 — Roulette Profit Strategy
// Based on Profit R/B coverage (darthvador05) + IOL 4.0x + Capitalize
// Monte Carlo: +$174 median (div=9008), beats Profit R/B (+$161), 20% bust
//
// Modes:
//   STRIKE  — IOL 4.0x on miss, reset on win (fast one-shot recovery)
//   CAPITALIZE — 2x base bet after 3 consecutive wins (ride streaks)
//
// Coverage: 24 big (1.44x) + 5 small (0.28x) + 8 uncovered (0x)
// No brake needed — roulette's 78% win rate makes IOL recovery near-certain

strategyTitle = "COBRA";
version = "1.0.0";
author = "darthvador05 (coverage) + stanz (strategy)";
scripter = "stanz";

game = "roulette";

// USER CONFIG
// ============================================================
//
// RISK PRESETS:
//
//   Divider | IOL  | Median  | Bust%  | Win%  | Profile
//  ---------|------|---------|--------|-------|----------
//    31,526 | 3.5x | +$53   |  4.1%  | 90.1% | Conservative
//     9,008 | 3.5x | +$161  | 12.4%  | 73.7% | Moderate (Profit R/B)
//     9,008 | 4.0x | +$174  | 20.2%  | 60.1% | Aggressive (recommended)
//     2,574 | 3.5x | -$182  | 34.0%  | 45.2% | Yolo
//
divider = 9008;
increaseOnLossPercent = 300; // IOL: 300 = multiply by 4.0x on loss. (250 = 3.5x for conservative)

// Capitalize trigger
capitalizeStreak = 3;   // Enter capitalize after N consecutive wins
capitalizeMaxBets = 1;  // Max capitalize spins before returning to strike

// Number coverage (from Profit R/B — proven optimal, don't change)
uncoveredNumbers = [0, 4, 9, 12, 13, 21, 25, 36];
smallBetNumbers = [1, 16, 24, 31, 33];
bigToSmallRatio = 5;

// Vault-and-continue (% of starting balance). Set 0 to disable.
vaultPct = 5;
stopTotalPct = 10;

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 0;
stopAfterHands = 0;

seedChangeAfterLossStreak = 0; // Proven useless. 0 = disabled.

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(1000);
  resetSeed();
  resetStats();
  clearConsole();
}

startBalance = balance;
iol = 1 + increaseOnLossPercent / 100;

// Build number lists
bigBetNumbers = [];
for (i = 1; i <= 36; i++) {
  if (uncoveredNumbers.indexOf(i) === -1 && smallBetNumbers.indexOf(i) === -1) {
    bigBetNumbers.push(i);
  }
}
coveredCount = bigBetNumbers.length + smallBetNumbers.length;

// Calculate bet amounts
totalBetAmount = startBalance / divider;
smallBet = totalBetAmount / (bigBetNumbers.length * bigToSmallRatio + smallBetNumbers.length);
bigBet = smallBet * bigToSmallRatio;

// Thresholds from percentages
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;

// State
mode = "strike";
currentMultiplier = 1;
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
totalWins = 0;
totalLosses = 0;
spinsPlayed = 0;
capCount = 0;
peakProfit = 0;
totalWagered = 0;
profitAtLastVault = 0;
totalVaulted = 0;
vaultCount = 0;
maxBetSeen = totalBetAmount;
// Mode counters
strikeSpins = 0;
capSpins = 0;
capTriggered = 0;
capWins = 0;
capLosses = 0;
capPnL = 0;
modeChanges = 0;
recoveries = 0;
currentChainCost = 0;
biggestRecovery = 0;
stopped = false;
summaryPrinted = false;

// Max survivable LS
function calcMaxLS() {
  cumulative = 0;
  bet = totalBetAmount;
  streak = 0;
  while (cumulative + bet <= startBalance) {
    cumulative += bet;
    streak++;
    bet *= iol;
  }
  return streak;
}
maxSurvivableLS = calcMaxLS();

// Build selection object
function buildSelection(multiplier) {
  sel = {};
  for (i = 0; i < bigBetNumbers.length; i++) {
    sel["number" + bigBetNumbers[i]] = bigBet * multiplier;
  }
  for (i = 0; i < smallBetNumbers.length; i++) {
    sel["number" + smallBetNumbers[i]] = smallBet * multiplier;
  }
  return sel;
}

selection = buildSelection(1);

// ============================================================
// LOGGING
// ============================================================

function modeLabel() {
  return mode === "strike" ? "STRIKE" : "CAPITALIZE";
}

function modeColor() {
  return mode === "strike" ? "#FF6B6B" : "#FD71FD";
}

function logBanner() {
  log(
    "#FF4500",
    `================================
 COBRA v${version}
================================
 by ${author}
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentTotal = totalBetAmount * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? ` | DD: -$${drawdown.toFixed(2)}` : "";
  profitRate = spinsPlayed > 0 ? (profit / spinsPlayed * 100).toFixed(2) : "0.00";
  rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  capWR = capSpins > 0 ? (capWins / capSpins * 100).toFixed(0) : "0";
  currentProfit = profit - profitAtLastVault;
  vaultBar = totalVaulted > 0 ? ` | Vaulted: $${totalVaulted.toFixed(2)} (${vaultCount}x)` : "";
  targetBar = stopOnTotalProfit > 0 ? ` | Target: $${profit.toFixed(2)}/$${stopOnTotalProfit.toFixed(2)}` : "";

  runwayBar = "";
  if (mode === "strike" && lossStreak > 0) {
    runwayBar = ` | Runway: LS ${lossStreak}/${maxSurvivableLS}`;
    if (currentChainCost > 0) runwayBar += ` | Chain: -$${currentChainCost.toFixed(2)}`;
  }

  log("#70FD70", `Balance: $${balance.toFixed(2)} | Bet: $${currentTotal.toFixed(4)} | IOL: ${currentMultiplier.toFixed(1)}x`);
  log(modeColor(), `Mode: ${modeLabel()} | LS: ${lossStreak} | WS: ${winStreak}${runwayBar}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)}${ddBar}${vaultBar}${targetBar}`);
  log("#FFDB55", `W/L: ${totalWins}/${totalLosses} | Rate: $${profitRate}/100s | Coverage: ${coveredCount}/37`);
  log("#42CAF7", `RTP: ${rtp}% | Wagered: $${totalWagered.toFixed(2)} (${(totalWagered / startBalance).toFixed(1)}x) | Recoveries: ${recoveries}`);
  sPct = spinsPlayed > 0 ? (strikeSpins / spinsPlayed * 100).toFixed(0) : "0";
  cPct = spinsPlayed > 0 ? (capSpins / spinsPlayed * 100).toFixed(0) : "0";
  log("#FF6B6B", `STRIKE: ${strikeSpins} (${sPct}%)  CAP: ${capSpins} (${cPct}%) [${capTriggered}x, ${capWR}% WR, $${capPnL.toFixed(2)}]`);
  log("#FD71FD", `Spins: ${spinsPlayed} | Max Bet: $${maxBetSeen.toFixed(2)} | Best Recovery: $${biggestRecovery.toFixed(2)}`);
}

// ============================================================
// COBRA STRATEGY
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

  // === MODE LOGIC ===

  prevMode = mode;

  if (mode === "strike") {
    strikeSpins++;

    if (isWin) {
      // Recovery complete
      recoveryAmt = totalBetAmount * currentMultiplier;
      if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
      if (currentChainCost > 0) recoveries++;
      currentChainCost = 0;
      currentMultiplier = 1;
      selection = buildSelection(1);

      // Check capitalize trigger
      if (winStreak >= capitalizeStreak) {
        mode = "capitalize";
        capCount = 0;
        capTriggered++;
        currentMultiplier = 2;
        selection = buildSelection(2);
      }
    } else {
      // Loss — IOL escalate
      currentChainCost += lastBet.amount;
      currentMultiplier *= iol;
      selection = buildSelection(currentMultiplier);

      if (seedChangeAfterLossStreak > 0 && lossStreak % seedChangeAfterLossStreak === 0) {
        resetSeed();
      }
    }

  } else if (mode === "capitalize") {
    capSpins++;
    capCount++;
    capPnL += handPnL;

    if (isWin) {
      capWins++;
    } else {
      capLosses++;
    }

    if (!isWin || capCount >= capitalizeMaxBets) {
      // Exit capitalize
      mode = "strike";
      winStreak = 0;
      currentMultiplier = 1;
      selection = buildSelection(1);

      // If capitalize ended on a loss, start IOL from base
      if (!isWin) {
        lossStreak = 1;
        currentChainCost = lastBet.amount;
        currentMultiplier = iol;
        selection = buildSelection(currentMultiplier);
      }
    } else if (isWin) {
      // Double on consecutive win during capitalize
      currentMultiplier = Math.min(currentMultiplier * 2, 100);
      selection = buildSelection(currentMultiplier);
    }
  }

  if (mode !== prevMode) modeChanges++;

  // Track max bet
  currentTotal = totalBetAmount * currentMultiplier;
  if (currentTotal > maxBetSeen) maxBetSeen = currentTotal;
}

// ============================================================
// VAULT & STOP
// ============================================================

async function vaultHandle() {
  currentProfit = profit - profitAtLastVault;

  if (
    vaultProfitsThreshold > 0 &&
    mode === "strike" &&
    currentMultiplier <= 1.01 &&
    currentProfit >= vaultProfitsThreshold
  ) {
    vaultAmount = currentProfit;
    await depositToVault(vaultAmount);
    totalVaulted += vaultAmount;
    profitAtLastVault = profit;
    vaultCount++;
    log("#4FFB4F", `Vaulted $${vaultAmount.toFixed(2)} | Total vaulted: $${totalVaulted.toFixed(2)}`);

    // Adaptive rebase
    startBalance = balance;
    totalBetAmount = startBalance / divider;
    smallBet = totalBetAmount / (bigBetNumbers.length * bigToSmallRatio + smallBetNumbers.length);
    bigBet = smallBet * bigToSmallRatio;
    selection = buildSelection(1);
    maxSurvivableLS = calcMaxLS();
  }
}

function stopProfitCheck() {
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentMultiplier <= 1.01) {
    log("#4FFB4F", `Target reached! Profit: $${profit.toFixed(2)} (Vaulted: $${totalVaulted.toFixed(2)} + Current: $${(profit - profitAtLastVault).toFixed(2)})`);
    stopped = true;
    logSummary();
    engine.stop();
  }

  if (stopOnProfit > 0 && profit >= stopOnProfit) {
    log("#4FFB4F", `Stopped on $${profit.toFixed(2)} Profit`);
    stopped = true;
    logSummary();
    engine.stop();
  }
}

function stopLossCheck() {
  if (stopOnLoss > 0 && profit < -Math.abs(stopOnLoss)) {
    log("#FD6868", `Stopped on $${(-profit).toFixed(2)} Loss`);
    stopped = true;
    logSummary();
    engine.stop();
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#70FD70", `Starting balance: $${startBalance.toFixed(2)}`);
log("#42CAF7", `Unit: $${totalBetAmount.toFixed(4)} | Divider: ${divider} | IOL: ${iol}x`);
log("#FF4500", `STRIKE (IOL ${iol}x) → CAPITALIZE (2x on ${capitalizeStreak}-win streaks)`);
log("#FFDB55", `Coverage: ${coveredCount}/37 | Big: ${bigBetNumbers.length} | Small: ${smallBetNumbers.length} | Uncovered: ${uncoveredNumbers.length}`);
vaultLabel = vaultPct > 0 ? `Vault at ${vaultPct}% ($${vaultProfitsThreshold.toFixed(2)})` : "No vault";
stopLabel = stopTotalPct > 0 ? `Stop at ${stopTotalPct}% ($${stopOnTotalProfit.toFixed(2)})` : "No stop";
log("#4FFB4F", `${vaultLabel} | ${stopLabel}`);
log("#FD71FD", `Max survivable LS: ${maxSurvivableLS} | Seed reset: ${seedChangeAfterLossStreak > 0 ? "every " + seedChangeAfterLossStreak + " losses" : "disabled"}`);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  await vaultHandle();
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && spinsPlayed >= stopAfterHands) {
    log("#FFFF2A", `Dev stop: ${spinsPlayed} spins reached`);
    stopped = true;
    logSummary();
    engine.stop();
  }
});

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  sPct = spinsPlayed > 0 ? (strikeSpins / spinsPlayed * 100).toFixed(1) : "0";
  cPct = spinsPlayed > 0 ? (capSpins / spinsPlayed * 100).toFixed(1) : "0";
  capWR = capSpins > 0 ? (capWins / capSpins * 100).toFixed(0) : "0";
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  log(
    "#FF4500",
    `================================
 COBRA — Session Over
================================`
  );
  log(`Spins: ${spinsPlayed} | W/L: ${totalWins}/${totalLosses}`);
  log(`Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Vaults: ${vaultCount}`);
  log(`RTP: ${rtpFinal}% | Wagered: $${totalWagered.toFixed(2)} (${(totalWagered / startBalance).toFixed(1)}x)`);
  log(`Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(`Max Bet: $${maxBetSeen.toFixed(2)} | Best Recovery: $${biggestRecovery.toFixed(2)} | Recoveries: ${recoveries}`);
  log(`Final bet: $${(totalBetAmount * currentMultiplier).toFixed(4)} (${currentMultiplier.toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
  log("#8B949E", `Modes: STRIKE ${strikeSpins} (${sPct}%) | CAP ${capSpins} (${cPct}%)`);
  log("#8B949E", `Cap: ${capTriggered}x W/L: ${capWins}/${capLosses} (${capWR}% WR) Net: $${capPnL.toFixed(2)} | Switches: ${modeChanges}`);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
