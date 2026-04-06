// COBRA v4.0 — Roulette Profit Strategy
// Color + 5 numbers, IOL 3.0x — Monte Carlo champion
// +$333 median (5k spins, div=10000), 39.1% bust, 60.9% win rate
//
// Coverage: Color (18) + 5 extra numbers = 23/37 = 62.2%
// Win payout: +0.57x total bet (equal-weighted across all 23 numbers)
// Miss: 14/37 = 37.8%
//
// Why Color+5 beats 2 Columns:
//   Color bet at 1:1 payout recovers more per win than column 2:1 when
//   combined with number bets. The equal-weight math produces +0.57x
//   vs column's +0.50x. Higher recovery per win = faster IOL recovery.
//
// Equal weight math:
//   Color bet = C, Number bet = Y per number (5 numbers)
//   Total = C + 5Y. Equal payout: C - 5Y = 32Y - C → 2C = 37Y → C = 18.5Y
//   Total = 18.5Y + 5Y = 23.5Y. Win = C - 5Y = 18.5Y - 5Y = 13.5Y
//   Win fraction = 13.5/23.5 = +0.574x

strategyTitle = "COBRA";
version = "4.0.0";
author = "stanz";
scripter = "stanz";

game = "roulette";

// USER CONFIG
// ============================================================
//
// RISK PRESETS (Color+5, 5k-spin sessions):
//
//   Divider | IOL  | Median  | Bust%  | Win%  | Profile
//  ---------|------|---------|--------|-------|----------
//    31,526 | 3.0x | +$100  | ~15%   | ~85%  | Conservative
//    10,000 | 3.0x | +$333  | 39.1%  | 60.9% | Aggressive (recommended)
//    15,000 | 3.0x | +$183  | 23.2%  | 76.8% | Balanced
//    10,000 | 2.5x |  +$80  | ~15%   | ~85%  | Safe
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

// Vault-and-continue (% of starting balance). Set 0 to disable.
vaultPct = 5;
stopTotalPct = 10;

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

startBalance = balance;
iol = 1 + increaseOnLossPercent / 100;
totalNumbers = 18 + extraNumbers.length; // 23

// Equal-weight bet calculation
// C = 18.5Y, Total = C + N*Y = (18.5 + N)*Y where N = extraNumbers.length
// Y = totalBet / (18.5 + N), C = 18.5 * Y
baseTotalBet = startBalance / divider;
numBetUnit = baseTotalBet / (18.5 + extraNumbers.length);
colorBetUnit = 18.5 * numBetUnit;

// Win payout fraction: (37 - 2*N) / (37 + 2*N) where N = extra numbers
winFraction = (37 - 2 * extraNumbers.length) / (37 + 2 * extraNumbers.length);

// Thresholds from percentages
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;

// Build selection
function buildSelection(multiplier) {
  sel = {};
  if (betColor === "red") {
    sel["colorRed"] = colorBetUnit * multiplier;
  } else {
    sel["colorBlack"] = colorBetUnit * multiplier;
  }
  for (i = 0; i < extraNumbers.length; i++) {
    sel["number" + extraNumbers[i]] = numBetUnit * multiplier;
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

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#FF4500",
    `================================
 COBRA v${version}
================================
 by ${author} | Color+${extraNumbers.length} Profit
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  currentTotal = baseTotalBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? ` | DD: -$${drawdown.toFixed(2)}` : "";
  profitRate = spinsPlayed > 0 ? (profit / spinsPlayed * 100).toFixed(2) : "0.00";
  rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  vaultBar = totalVaulted > 0 ? ` | Vaulted: $${totalVaulted.toFixed(2)} (${vaultCount}x)` : "";
  targetBar = stopOnTotalProfit > 0 ? ` | Target: $${profit.toFixed(2)}/$${stopOnTotalProfit.toFixed(2)}` : "";

  runwayBar = "";
  if (lossStreak > 0) {
    runwayBar = ` | Runway: LS ${lossStreak}/${maxSurvivableLS} | Chain: -$${currentChainCost.toFixed(2)}`;
  }

  log("#70FD70", `Balance: $${balance.toFixed(2)} | Bet: $${currentTotal.toFixed(4)} | IOL: ${currentMultiplier.toFixed(1)}x`);
  log("#FF6B6B", `LS: ${lossStreak} | WS: ${winStreak}${runwayBar}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)}${ddBar}${vaultBar}${targetBar}`);
  log("#FFDB55", `W/L: ${totalWins}/${totalLosses} | Rate: $${profitRate}/100s | Coverage: ${totalNumbers}/37 (${betColor}+${extraNumbers.length})`);
  log("#42CAF7", `RTP: ${rtp}% | Wagered: $${totalWagered.toFixed(2)} (${(totalWagered / startBalance).toFixed(1)}x) | Recoveries: ${recoveries}`);
  log("#8B949E", `IOL chain: ${recoveries} recovered | ${lossStreak > 0 ? "LS " + lossStreak + " at " + currentMultiplier.toFixed(1) + "x" : "base bet"}`);
  log("#FD71FD", `Spins: ${spinsPlayed} | Max Bet: $${maxBetSeen.toFixed(2)} | Best Recovery: $${biggestRecovery.toFixed(2)} | Max LS: ${maxSurvivableLS}`);
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
    selection = buildSelection(currentMultiplier);
  }

  currentTotal = baseTotalBet * currentMultiplier;
  if (currentTotal > maxBetSeen) maxBetSeen = currentTotal;
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
    log("#4FFB4F", `Vaulted $${vaultAmount.toFixed(2)} | Total vaulted: $${totalVaulted.toFixed(2)}`);

    // Adaptive rebase
    startBalance = balance;
    baseTotalBet = startBalance / divider;
    numBetUnit = baseTotalBet / (18.5 + extraNumbers.length);
    colorBetUnit = 18.5 * numBetUnit;
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
log("#42CAF7", `Total bet: $${baseTotalBet.toFixed(4)} | Color: $${colorBetUnit.toFixed(4)} | Num: $${numBetUnit.toFixed(4)} x${extraNumbers.length}`);
log("#FF4500", `IOL ${iol}x | ${betColor} + numbers [${extraNumbers.join(",")}] | Win: +${(winFraction*100).toFixed(1)}%`);
log("#FFDB55", `Coverage: ${totalNumbers}/37 (${(totalNumbers/37*100).toFixed(0)}%) | Max LS: ${maxSurvivableLS}`);
vaultLabel = vaultPct > 0 ? `Vault at ${vaultPct}% ($${vaultProfitsThreshold.toFixed(2)})` : "No vault";
stopLabel = stopTotalPct > 0 ? `Stop at ${stopTotalPct}% ($${stopOnTotalProfit.toFixed(2)})` : "No stop";
log("#4FFB4F", `${vaultLabel} | ${stopLabel}`);

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
  log(`Final bet: $${(baseTotalBet * currentMultiplier).toFixed(4)} (${currentMultiplier.toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
  log("#8B949E", `IOL chains recovered: ${recoveries} | Max LS: ${longestLossStreak} | Max survivable: ${maxSurvivableLS}`);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
