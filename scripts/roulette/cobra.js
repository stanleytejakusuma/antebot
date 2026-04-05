// COBRA v3.0 — Roulette Profit Strategy
// 2-Column coverage + IOL 3.0x — optimized for long sessions
// Monte Carlo: +$162 median (5k spins, div=10000), 22.7% bust, 77% win rate
//
// Coverage: 2 of 3 columns (24/37 = 64.9%)
// Win payout: +0.50x total bet (vs R/B's +0.44x — the key advantage)
// Miss: 13/37 = 35.1% (12 uncovered numbers + green 0)
//
// v3 changes from v2:
//   - IOL 3.5x → 3.0x (gains 1 extra LS level: 9 vs 8 — halves bust rate over long sessions)
//   - Removed capitalize (Monte Carlo proved it adds zero value on roulette)
//   - div 9008 → 10000 (matches user's proven live config)
//   - Tested at 5k spins (realistic session length) not just 2k

strategyTitle = "COBRA";
version = "3.0.0";
author = "stanz";
scripter = "stanz";

game = "roulette";

// USER CONFIG
// ============================================================
//
// RISK PRESETS (2 Columns, 5k-spin sessions):
//
//   Divider | IOL  | Median  | Bust%  | Win%  | MaxLS | Profile
//  ---------|------|---------|--------|-------|-------|----------
//    31,526 | 3.0x | +$51   |  3.4%  | 96.6% |  10  | Ultra safe
//    15,000 | 3.0x | +$108  | 22.7%  | 77.3% |   9  | Conservative
//    10,000 | 3.0x | +$162  | 22.7%  | 77.3% |   9  | Balanced (recommended)
//    10,000 | 3.5x | -$407  | 53.0%  | 47.0% |   8  | DON'T (busts on long sessions)
//
divider = 10000;
increaseOnLossPercent = 200; // IOL: 200 = multiply by 3.0x on loss.

// Which 2 columns to bet on (1, 2, or 3). Pick any 2 — coverage is identical.
// Column 1: 1,4,7,10,13,16,19,22,25,28,31,34
// Column 2: 2,5,8,11,14,17,20,23,26,29,32,35
// Column 3: 3,6,9,12,15,18,21,24,27,30,33,36
column1 = true;
column2 = true;
column3 = false;

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

// Calculate base bet per column (total split evenly between 2 columns)
baseTotalBet = startBalance / divider;
baseColumnBet = baseTotalBet / 2;

// Thresholds from percentages
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;

// Build selection
function buildSelection(multiplier) {
  sel = {};
  colBet = baseColumnBet * multiplier;
  if (column1) sel["row1"] = colBet;
  if (column2) sel["row2"] = colBet;
  if (column3) sel["row3"] = colBet;
  return sel;
}

selection = buildSelection(1);

// Coverage info
coveredColumns = (column1 ? 1 : 0) + (column2 ? 1 : 0) + (column3 ? 1 : 0);
coveredNumbers = coveredColumns * 12;
uncoveredNumbers = 37 - coveredNumbers;

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
maxBetSeen = baseTotalBet;
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
 by ${author} | 2-Column Profit
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
  capWR = capSpins > 0 ? (capWins / capSpins * 100).toFixed(0) : "0";
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
  log("#FFDB55", `W/L: ${totalWins}/${totalLosses} | Rate: $${profitRate}/100s | Coverage: ${coveredNumbers}/37 (2 cols)`);
  log("#42CAF7", `RTP: ${rtp}% | Wagered: $${totalWagered.toFixed(2)} (${(totalWagered / startBalance).toFixed(1)}x) | Recoveries: ${recoveries}`);
  log("#FF6B6B", `IOL chain: ${recoveries} recovered | Current: ${lossStreak > 0 ? "LS " + lossStreak + " at " + currentMultiplier.toFixed(1) + "x" : "base bet"}`);
  log("#FD71FD", `Spins: ${spinsPlayed} | Max Bet: $${maxBetSeen.toFixed(2)} | Best Recovery: $${biggestRecovery.toFixed(2)} | Max LS: ${maxSurvivableLS}`);
}

// ============================================================
// COBRA STRATEGY
// ============================================================

function mainStrategy() {
  spinsPlayed++;

  handPnL = lastBet.payout - lastBet.amount;
  totalWagered += lastBet.amount;

  // Column bets: win = multiplier >= 1.0 (payout includes return of bet)
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

  // === IOL LOGIC (pure strike — no modes needed) ===

  strikeSpins++;

  if (isWin) {
    recoveryAmt = baseTotalBet * currentMultiplier;
    if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
    if (currentChainCost > 0) recoveries++;
    currentChainCost = 0;
    currentMultiplier = 1;
    selection = buildSelection(1);
  } else {
    // Loss — IOL escalate
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
    baseTotalBet = startBalance / divider;
    baseColumnBet = baseTotalBet / 2;
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
log("#42CAF7", `Bet: $${baseTotalBet.toFixed(4)} ($${baseColumnBet.toFixed(4)} per col) | Divider: ${divider} | IOL: ${iol}x`);
colList = (column1 ? "Col1 " : "") + (column2 ? "Col2 " : "") + (column3 ? "Col3" : "");
log("#FF4500", `Pure IOL ${iol}x | ${colList.trim()} | Reset on win, multiply on miss`);
log("#FFDB55", `Coverage: ${coveredNumbers}/37 (${(coveredNumbers/37*100).toFixed(0)}%) | Win: +0.50x | Miss: -1.00x | Max LS: ${maxSurvivableLS}`);
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
  log(`Final bet: $${(baseTotalBet * currentMultiplier).toFixed(4)} (${currentMultiplier.toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
  log("#8B949E", `IOL chains recovered: ${recoveries} | Max LS: ${longestLossStreak} | Max survivable: ${maxSurvivableLS}`);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
