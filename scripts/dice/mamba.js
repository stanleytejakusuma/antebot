// MAMBA v3.0 — Dice Hybrid D'Alembert→Martingale + Trailing Stop
// 65% chance, D'Alembert for first 3 losses then Martingale 3.0x.
// Win payout: +0.523x bet (99/65 - 1). Miss: 35%. Edge: 1%.
//
// v3.0: Hybrid strike replaces pure IOL. Scored by Growth Rate G.
//   Scorecard ($100, 5k, trail 10/60): G=-9.55%, +$7.88 median, 0.1% bust
//   vs v2.0: G improved 85% (-61.2%→-9.6%), bust 8.3%→0.1%, median +$0.60
//
// D'ALEMBERT PHASE: First 3 consecutive losses, bet increases linearly
//   (+1 unit per loss: 1→2→3 units). Chain cost = 6 units. Covers 95.7%
//   of all loss streaks at 65% win rate. Safe — no geometric blowup.
// MARTINGALE PHASE: After 3rd loss, switch to 3.0x geometric escalation.
//   Recovery power for the rare 4.3% of streaks that go deep.
// TRAIL: Locks profits on decline. Trail-aware bet cap prevents breach.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat)

strategyTitle = "MAMBA";
version = "3.1.1";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
//
// RISK PRESETS ($100 bank, trail=10/60, scored by G):
//
//   DalCap | Mart | G(%)    | Median | Bust% | Win%  | Profile
//  --------|------|---------|--------|-------|-------|----------
//      3   | 3.0x | -9.55%  | +$7.88 |  0.1% | 76.6% | Recommended (v3.0)
//      5   | 3.0x | -57.8%  | +$9.12 |  7.0% | 82.9% | Aggressive (more profit, more bust)
//      5   | 2.0x | -15.7%  | +$8.24 |  0.4% | 79.7% | Balanced
//      0   | 3.0x | -61.2%  | +$7.28 |  8.3% | 86.5% | v2.0 (pure IOL)
//
chance = 65;
divider = 3000;

// D'ALEMBERT → MARTINGALE HYBRID
// First dalCap losses: linear +1 unit per loss (D'Alembert phase)
// After dalCap: switch to Martingale at martIOL multiplier (geometric phase)
// Set dalCap=0 for pure Martingale (v2.0 behavior)
dalCap = 3;
martIOL = 3.0;  // Martingale multiplier (3.0 = triple on loss)

// Bet cap: max bet as % of working balance (prevents single-bet catastrophe)
betCapPct = 15;         // 0 = no cap. 15 = max bet is 15% of working balance.

// Trailing stop config
trailActivatePct = 5;   // activate trail after profit exceeds this % of startBalance
trailRangePct = 5;      // exit if profit drops this % of bank below peak
                         // e.g., peak=10%, exit at 5% (range=5%). Fixed cushion, not % of peak.

// Bet direction: true = over, false = under
betHigh = true;

// Fixed stop (upper target). Set 0 for trailing-only.
stopTotalPct = 0;

// Vault: auto-detects platform. Real vault on Shuffle/Stake/Goated, virtual on Thrill/others.
// Virtual vault: profits "locked" internally — script reduces working bankroll, money stays in balance.
vaultPct = 5;
// Platforms with native vault support (add others as confirmed)
vaultMode = (casino === "SHUFFLE" || casino === "STAKE" || casino === "STAKE_US" || casino === "SHUFFLE_US" || casino === "GOATED") ? "real" : "virtual";

// Stop loss (hard floor). ALWAYS have this as backstop.
stopOnLoss = 15;

// Other stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopAfterHands = 0;

// Reset stats/console on start (set false to preserve previous session data)
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

log("#42CAF7", "Detected casino: " + casino + " | Vault mode: " + vaultMode + (vaultMode === "virtual" ? " (soft vault — funds stay in balance)" : " (real vault — depositToVault)"));

target = chanceToMultiplier(chance);
startBalance = balance;
iol = martIOL;
winPayout = 99 / chance - 1;

baseBet = startBalance / divider;

// Enforce minimum bet ($0.00101 on Shuffle)
minBet = 0.00101;
if (baseBet < minBet) {
  baseBet = minBet;
  log("#FFFF2A", "Min bet enforced: $" + baseBet.toFixed(5));
}

betSize = baseBet;

// Thresholds
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;
trailRange = startBalance * trailRangePct / 100; // Fixed cushion in dollars

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
dalUnits = 1;       // Current D'Alembert unit level
inMart = false;     // True when in Martingale phase
consecLosses = 0;   // Consecutive losses (for dalCap threshold)
dalPhaseHands = 0;
martPhaseHands = 0;
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

// Trailing stop state
trailActive = false;
trailFloor = 0;
trailStopFired = false;

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00FF7F",
    "================================\n MAMBA v" + version +
    "\n================================\n by " + author + " | Dice " + chance + "% IOL + Trail" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();
  log("#42CAF7", casino + " | " + vaultMode + " vault | SL " + stopOnLoss + "%");

  currentBet = baseBet * currentMultiplier;
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  profitRate = betsPlayed > 0 ? (profit / betsPlayed * 100).toFixed(2) : "0.00";
  rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  vaultTag = vaultMode === "virtual" ? "Soft-Vault" : "Vault";
  vaultBar = totalVaulted > 0 ? " | " + vaultTag + ": $" + totalVaulted.toFixed(2) + " (" + vaultCount + "x)" : "";
  targetBar = stopOnTotalProfit > 0 ? " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2) : "";

  runwayBar = "";
  if (lossStreak > 0) {
    phase = inMart ? "MART " + currentMultiplier.toFixed(1) + "x" : "DAL " + dalUnits + "/" + dalCap + "u";
    runwayBar = " | " + phase + " | LS " + lossStreak + " | Chain: -$" + currentChainCost.toFixed(2);
  }

  totalAssets = vaultMode === "virtual" ? balance : balance + totalVaulted;
  workBal = vaultMode === "virtual" ? balance - totalVaulted : balance;
  assetBar = totalVaulted > 0 ? " (Work $" + workBal.toFixed(2) + " + " + vaultTag + " $" + totalVaulted.toFixed(2) + ")" : "";

  // Trailing stop indicator
  trailBar = "";
  if (trailActive) {
    trailBar = " | TRAIL: floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = " | Trail arms at $" + trailActivateThreshold.toFixed(2);
  }

  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | Bet: $" + currentBet.toFixed(5) + " | IOL: " + currentMultiplier.toFixed(1) + "x");
  log("#FF6B6B", "LS: " + lossStreak + " | WS: " + winStreak + runwayBar);
  log("#4FFB4F", "ASSETS: $" + totalAssets.toFixed(2) + assetBar + " | P&L: $" + profit.toFixed(2));
  log("#FFD700", "Peak: $" + peakProfit.toFixed(2) + ddBar + trailBar);
  log("#A4FD68", vaultBar + targetBar);
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Rate: $" + profitRate + "/100b | Chance: " + chance + "% (+" + (winPayout * 100).toFixed(1) + "%)");
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveries);
  log("#8B949E", "IOL chain: " + recoveries + " recovered | " + (lossStreak > 0 ? "LS " + lossStreak + " at " + currentMultiplier.toFixed(1) + "x" : "base bet"));
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Max LS: " + maxSurvivableLS);
}

// ============================================================
// MAMBA STRATEGY — IOL on Dice
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

  // Hybrid D'Alembert → Martingale logic
  if (isWin) {
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
    currentChainCost += lastBet.amount;
    consecLosses++;

    if (dalCap > 0 && !inMart && consecLosses < dalCap) {
      // D'ALEMBERT PHASE: linear +1 unit per loss
      dalUnits++;
      currentMultiplier = dalUnits;
      dalPhaseHands++;
    } else {
      // MARTINGALE PHASE: geometric escalation
      if (!inMart) {
        // First entry into Mart: stay at D'Alembert level (no jump)
        // Martingale multiplies on NEXT loss, not this one
        inMart = true;
        currentMultiplier = dalUnits;
      } else {
        currentMultiplier *= iol;
      }
      martPhaseHands++;
    }

    // Soft bust: if next bet exceeds working balance, reset to base
    nextBet = baseBet * currentMultiplier;
    workBal = vaultMode === "virtual" ? balance - totalVaulted : balance;
    if (nextBet > workBal * 0.95) {
      log("#FD6868", "Soft bust: $" + nextBet.toFixed(2) + " > 95% of $" + workBal.toFixed(2) + " — reset");
      currentMultiplier = 1;
      dalUnits = 1;
      inMart = false;
      consecLosses = 0;
      currentChainCost = 0;
    }

    betSize = baseBet * currentMultiplier;
  }

  // Hard bet cap: max bet as % of working balance
  if (betCapPct > 0) {
    workBal = vaultMode === "virtual" ? balance - totalVaulted : balance;
    maxBetAllowed = workBal * betCapPct / 100;
    if (betSize > maxBetAllowed) betSize = maxBetAllowed;
  }

  // Trail-aware bet cap: if trail is active, don't let a loss breach the floor
  if (trailActive) {
    trailFloor = peakProfit - trailRange;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && betSize > maxTrailBet) {
      betSize = maxTrailBet;
    }
  }

  if (betSize < minBet) betSize = minBet;
  currentBet = betSize;
  if (currentBet > maxBetSeen) maxBetSeen = currentBet;
}

// ============================================================
// TRAILING STOP
// ============================================================

function trailingStopCheck() {
  // Activate trailing stop when profit exceeds threshold
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
  }

  if (trailActive) {
    // Update floor based on peak
    trailFloor = peakProfit - trailRange;

    // Fire trailing stop when profit drops below floor — no multiplier gate
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

    if (vaultMode === "real") {
      // Real vault: move money to casino vault widget
      await depositToVault(vaultAmount);
    }
    // Virtual vault: money stays in balance but script treats it as locked

    totalVaulted += vaultAmount;
    profitAtLastVault = profit;
    vaultCount++;
    vaultLabel = vaultMode === "virtual" ? "SOFT-VAULTED" : "VAULTED";
    log("#4FFB4F", vaultLabel + " $" + vaultAmount.toFixed(2) + " | Total: $" + totalVaulted.toFixed(2));

    // Adaptive rebase — use WORKING balance (exclude vaulted)
    workingBalance = balance - totalVaulted;
    if (vaultMode === "real") workingBalance = balance; // Real vault already moved funds
    startBalance = workingBalance;
    baseBet = startBalance / divider;
    if (baseBet < minBet) baseBet = minBet;
    betSize = baseBet;
    maxSurvivableLS = calcMaxLS();
    vaultProfitsThreshold = startBalance * vaultPct / 100;
    trailActivateThreshold = startBalance * trailActivatePct / 100;
    trailRange = startBalance * trailRangePct / 100;
  }
}

function stopProfitCheck() {
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentMultiplier <= 1.01) {
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
  stopLossAmount = startBalance * stopOnLoss / 100;
  workProfit = vaultMode === "virtual" ? profit - totalVaulted : profit;
  if (stopOnLoss > 0 && workProfit < -stopLossAmount) {
    log("#FD6868", "Stop loss! Working P&L $" + workProfit.toFixed(2) + " (-" + stopOnLoss + "% of $" + startBalance.toFixed(2) + ") | Vault safe: $" + totalVaulted.toFixed(2));
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
hybridLabel = dalCap > 0 ? "D'Alembert " + dalCap + " -> Mart " + iol + "x" : "Pure IOL " + iol + "x";
log("#00FF7F", hybridLabel + " | Max LS: " + maxSurvivableLS);
log("#FFD700", "Trail: arm at " + trailActivatePct + "% ($" + trailActivateThreshold.toFixed(2) + "), range " + trailRangePct + "% ($" + trailRange.toFixed(2) + " cushion from peak)");
vaultModeLabel = vaultMode === "virtual" ? " [SOFT]" : "";
vaultLabel = vaultPct > 0 ? "Vault" + vaultModeLabel + " at " + vaultPct + "% ($" + vaultProfitsThreshold.toFixed(2) + ")" : "No vault";
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% ($" + stopOnTotalProfit.toFixed(2) + ")" : "No fixed stop";
slLabel = stopOnLoss > 0 ? "SL at " + stopOnLoss + "%" : "No SL";
log("#4FFB4F", vaultLabel + " | " + stopLabel + " | " + slLabel);
log("#42CAF7", "Casino: " + casino + " | Vault mode: " + vaultMode);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  trailingStopCheck();
  if (stopped) return;
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
  exitType = trailStopFired ? "TRAILING STOP" : "TARGET/MANUAL";
  log(
    "#00FF7F",
    "================================\n MAMBA v" + version + " — " + exitType + "\n================================"
  );
  totalAssetsFinal = vaultMode === "virtual" ? balance : balance + totalVaulted;
  workBalFinal = vaultMode === "virtual" ? balance - totalVaulted : balance;
  vaultTagFinal = vaultMode === "virtual" ? "Soft-Vault" : "Vault";
  log("#4FFB4F", "ASSETS: $" + totalAssetsFinal.toFixed(2) + " (Work $" + workBalFinal.toFixed(2) + " + " + vaultTagFinal + " $" + totalVaulted.toFixed(2) + ") | P&L: $" + profit.toFixed(2));
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Vaults: " + vaultCount);
  log("RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("Final bet: $" + (baseBet * currentMultiplier).toFixed(5) + " (" + currentMultiplier.toFixed(1) + "x) | Balance: $" + balance.toFixed(2));
  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
  log("#8B949E", "Hybrid: DAL=" + dalPhaseHands + " | MART=" + martPhaseHands + " | dalCap=" + dalCap + " | mart=" + iol + "x");
  log("#8B949E", "Chains recovered: " + recoveries + " | Max LS: " + longestLossStreak + " | Max survivable: " + maxSurvivableLS);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
