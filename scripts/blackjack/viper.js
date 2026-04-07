// VIPER v4.0 — Blackjack Profit Strategy + PATIENCE + Trail
// Four-phase: ABSORB → STRIKE (Martingale 2x) → COIL (flat brake) → CAPITALIZE (Paroli 2x)
// v4.0: PATIENCE (absorb first loss at flat), div=4000, brake=12, capMax=3
//   Monte Carlo ($100, 5k, trail 10/60): +$8.09 median, 10.4% bust, 89.0% win
//   vs v3.0.1: +5.8% median, -0.4pp bust, +18.7% P90
//
// PATIENCE: Absorb 1st consecutive loss at flat bet — don't Martingale immediately.
//   Most losses are single (self-correct 42.4% of the time). Only genuine streaks
//   (2+ consecutive losses) warrant Martingale escalation. Reduces activations ~50%.
//   Borrowed from BASILISK. Enables aggressive divider (4000) without extra bust.
//
// STRIKE:  Martingale 2x on 2nd+ consecutive loss — fast recovery
// COIL:    Flat bet at brake level — survives deep streaks without geometric blowup
// CAPITALIZE: Paroli 2x on win streaks — rides 3 bets of momentum
//
// Bet matrix by ConnorMcLeod/Vrafasky (community standard)
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat)

strategyTitle = "VIPER";
version = "4.0.0";
author = "stanz";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
// RISK PRESETS ($100 bank, trail=10/60, MC 5k sessions):
//
//   Div  | Brake | PAT | Cap  | Median | Bust% | Win%  | P90     | Profile
//  ------|-------|-----|------|--------|-------|-------|---------|----------
//   4000 |   12  |  1  | 2/3  | +$8.09 | 10.4% | 89.0% | +$17.32 | Recommended (v4.0)
//   4000 |   10  |  1  | 2/2  | +$7.63 | 10.6% | 88.0% | +$14.89 | Conservative
//   5000 |   12  |  1  | 2/2  | +$7.96 | 10.1% | 88.8% | +$16.72 | Balanced
//   6000 |   10  |  0  | 2/2  | +$7.65 | 10.8% | 88.4% | +$14.59 | v3.0.1 baseline
//
divider = 4000;
brakeAt = 12; // Switch from Martingale to flat after this many consecutive losses. 0 = disabled.

// PATIENCE: consecutive losses before Martingale activates (0 = Mart on every loss)
// Absorbs single losses at flat bet. Only escalate on 2+ consecutive losses.
delayThreshold = 1;

// Capitalize trigger
capitalizeStreak = 2;
capitalizeMaxBets = 3;

// Vault-and-continue (% of starting balance). Set 0 to disable.
vaultPct = 0; // Vault at this % profit
stopTotalPct = 15; // Stop at 15% total session profit (including vaulted)

// Stop conditions. Set 0 to disable.
stopOnProfit = 0; // Hard stop on current profit (post-vault). 0 = use % instead.
stopOnLoss = 15;
stopAfterHands = 0;

// Trailing stop config
trailActivatePct = 10;  // activate trailing stop after profit exceeds this %
trailLockPct = 60;     // exit if profit drops below this % of peak (40% cushion)

// Reset stats/console on start
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
unit = startBalance / divider;
if (unit < 0.001) unit = 0.001;

// Calculate thresholds from percentages
vaultProfitsThreshold = vaultPct > 0 ? startBalance * vaultPct / 100 : 0;
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;

sideBetPerfectPairs = 0;
sideBet213 = 0;

// State
mode = "strike";
currentBet = unit;
handsPlayed = 0;
totalWins = 0;
totalLosses = 0;
totalPushes = 0;
totalDoubles = 0;
totalSplits = 0;
totalBlackjacks = 0;
longestWinStreak = 0;
longestLossStreak = 0;
currentWinStreak = 0;
currentLossStreak = 0;
consecLosses = 0;
winStreak = 0;
capCount = 0;
peakProfit = 0;
// PATIENCE tracking
flatAbsorbed = 0;
martActivations = 0;
// Brake state
brakeBet = 0;
coilDeficit = 0;
coilHands = 0;
// Mode counters
strikeHands = 0;
coilHandsTotal = 0;
capHands = 0;
capWins = 0;
capLosses = 0;
capPnL = 0;
capTriggered = 0;
modeChanges = 0;
maxBetSeen = unit;
biggestRecovery = 0;
currentChainCost = 0;
recoveryChains = 0;
totalWagered = 0;
coilActivations = 0;
totalVaulted = 0;
profitAtLastVault = 0;
vaultCount = 0;
stopped = false;
summaryPrinted = false;

// Trailing stop state
trailActive = false;
trailFloor = 0;
trailStopFired = false;
trailActivateThreshold = startBalance * trailActivatePct / 100;

betSize = currentBet;

// ============================================================
// BET MATRIX — Perfect Basic Strategy (ConnorMcLeod/Vrafasky)
// ============================================================

betMatrixReturns = {
  H: BLACKJACK_HIT,
  S: BLACKJACK_STAND,
  P: BLACKJACK_SPLIT,
  D: BLACKJACK_DOUBLE,
};

values = {
  A: 11, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10,
  J: 10, Q: 10, K: 10,
};

betMatrix = {
  hard: {
    4:  { 2:"H", 3:"H", 4:"H", 5:"H", 6:"H", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    5:  { 2:"H", 3:"H", 4:"H", 5:"H", 6:"H", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    6:  { 2:"H", 3:"H", 4:"H", 5:"H", 6:"H", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    7:  { 2:"H", 3:"H", 4:"H", 5:"H", 6:"H", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    8:  { 2:"H", 3:"H", 4:"H", 5:"H", 6:"H", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    9:  { 2:"H", 3:"D", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    10: { 2:"D", 3:"D", 4:"D", 5:"D", 6:"D", 7:"D", 8:"D", 9:"D", 10:"H", A:"H" },
    11: { 2:"D", 3:"D", 4:"D", 5:"D", 6:"D", 7:"D", 8:"D", 9:"D", 10:"D", A:"H" },
    12: { 2:"H", 3:"H", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    13: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    14: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    15: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    16: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    17: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    18: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    19: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    20: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    21: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
  },
  soft: {
    12: { 2:"H", 3:"H", 4:"H", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    13: { 2:"H", 3:"H", 4:"H", 5:"H", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    14: { 2:"H", 3:"H", 4:"H", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    15: { 2:"H", 3:"H", 4:"H", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    16: { 2:"H", 3:"H", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    17: { 2:"H", 3:"D", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    18: { 2:"S", 3:"DS", 4:"DS", 5:"DS", 6:"DS", 7:"S", 8:"S", 9:"H", 10:"H", A:"H" },
    19: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    20: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    21: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
  },
  splits: {
    22:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"P", 8:"H", 9:"H", 10:"H", A:"H" },
    33:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"P", 8:"H", 9:"H", 10:"H", A:"H" },
    44:   { 2:"H", 3:"H", 4:"H", 5:"P", 6:"P", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    55:   { 2:"D", 3:"D", 4:"D", 5:"D", 6:"D", 7:"D", 8:"D", 9:"D", 10:"H", A:"H" },
    66:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"H", 8:"H", 9:"H", 10:"H", A:"H" },
    77:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"P", 8:"H", 9:"H", 10:"H", A:"H" },
    88:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"P", 8:"P", 9:"P", 10:"P", A:"P" },
    99:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"S", 8:"P", 9:"P", 10:"S", A:"S" },
    1010: { 2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"S", 8:"S", 9:"S", 10:"S", A:"S" },
    AA:   { 2:"P", 3:"P", 4:"P", 5:"P", 6:"P", 7:"P", 8:"P", 9:"P", 10:"P", A:"P" },
  },
};

// ============================================================
// GAME ROUND HANDLER
// ============================================================

engine.onGameRound(function (currentBet, playerHandIndex) {
  if (stopped) return BLACKJACK_STAND;

  dealerValue = currentBet.state.dealer[0].value === 11
    ? "A"
    : currentBet.state.dealer[0].value;
  player = currentBet.state.player;

  if (
    player.length === 1 &&
    player[0].cards.length === 2 &&
    player[0].cards[0].rank === player[0].cards[1].rank
  ) {
    splitKey = ["J", "Q", "K"].includes(player[0].cards[0].rank)
      ? "1010"
      : "" + player[0].cards[0].rank + player[0].cards[1].rank;
    nextAction = betMatrixReturns[betMatrix.splits[splitKey][dealerValue]];
    if (nextAction === BLACKJACK_DOUBLE) betSize *= 2;
    return nextAction;
  }

  cards = player[playerHandIndex].cards;
  handValue = player[playerHandIndex].value;
  isSoft = cards.some(function (e) { return e.rank === "A"; })
    && cards.map(function (e) { return values[e.rank]; }).reduce(function (a, b) { return a + b; }, 0) < 21;

  if (isSoft) {
    matrixAction = betMatrix.soft[handValue][dealerValue];
  } else {
    matrixAction = betMatrix.hard[handValue][dealerValue];
  }

  if (matrixAction === "DS") {
    nextAction = cards.length === 2 ? BLACKJACK_DOUBLE : BLACKJACK_STAND;
  } else {
    nextAction = betMatrixReturns[matrixAction];
  }

  if (nextAction === BLACKJACK_DOUBLE && cards.length > 2) nextAction = BLACKJACK_HIT;
  if (nextAction === BLACKJACK_DOUBLE) betSize *= 2;

  return nextAction;
});

// ============================================================
// LOGGING
// ============================================================

function modeLabel() {
  if (mode === "strike") return "STRIKE";
  if (mode === "coil") return "COIL";
  if (mode === "capitalize") return "CAPITALIZE";
  return mode;
}

function modeColor() {
  if (mode === "strike") return "#FF6B6B";
  if (mode === "coil") return "#FFDB55";
  if (mode === "capitalize") return "#FD71FD";
  return "#FFFFFF";
}

function logBanner() {
  log(
    "#FF4500",
    "================================\n VIPER v" + version +
    "\n================================\n by " + author + " | FOR PROFIT" +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  capWinRate = capHands > 0 ? (capWins / capHands * 100).toFixed(0) : "0";
  maxLS = brakeAt > 0 ? brakeAt : Math.floor(Math.log(divider) / Math.log(2));
  drawdown = peakProfit - profit;
  ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  profitRate = handsPlayed > 0 ? (profit / handsPlayed * 100).toFixed(2) : "0.00";
  rtp = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";

  // Mode-specific status
  if (mode === "strike" && currentLossStreak > 0) {
    patStatus = consecLosses <= delayThreshold ? "ABSORBING (" + consecLosses + "/" + delayThreshold + ")" : "MART ACTIVE";
    modeStatus = " | " + patStatus + " | LS " + currentLossStreak + "/" + maxLS;
    if (currentChainCost > 0) modeStatus += " | Chain: -$" + currentChainCost.toFixed(2);
  } else if (mode === "coil") {
    modeStatus = " | Coil: $" + coilDeficit.toFixed(2) + " deficit | Hand " + coilHands;
  } else {
    modeStatus = "";
  }

  // Trailing stop indicator
  trailBar = "";
  if (trailActive) {
    trailBar = " | TRAIL: floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = " | Trail arms at $" + trailActivateThreshold.toFixed(2);
  }

  log("#70FD70", "Balance: $" + balance.toFixed(2) + " | Unit: $" + unit.toFixed(4) + " | Bet: $" + currentBet.toFixed(4));
  log(modeColor(), "Mode: " + modeLabel() + " | LS: " + currentLossStreak + " | " + (currentBet / unit).toFixed(1) + "x" + modeStatus);
  sessionTotal = profit;
  currentProfit = profit - profitAtLastVault;
  vaultBar = totalVaulted > 0 ? " | Vaulted: $" + totalVaulted.toFixed(2) + " (" + vaultCount + "x)" : "";
  targetBar = stopOnTotalProfit > 0 ? " | Target: $" + profit.toFixed(2) + "/$" + stopOnTotalProfit.toFixed(2) : "";
  log("#A4FD68", "Profit: $" + profit.toFixed(2) + " | Peak: $" + peakProfit.toFixed(2) + ddBar + vaultBar + targetBar);
  log("#FFD700", trailBar);
  log("#FFDB55", "W/L/P: " + totalWins + "/" + totalLosses + "/" + totalPushes + " | BJ: " + totalBlackjacks + " | Dbl: " + totalDoubles + " | Spl: " + totalSplits);
  log("#42CAF7", "RTP: " + rtp + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveryChains);
  sPct = handsPlayed > 0 ? (strikeHands / handsPlayed * 100).toFixed(0) : "0";
  coPct = handsPlayed > 0 ? (coilHandsTotal / handsPlayed * 100).toFixed(0) : "0";
  caPct = handsPlayed > 0 ? (capHands / handsPlayed * 100).toFixed(0) : "0";
  log("#FF6B6B", "STRIKE: " + strikeHands + " (" + sPct + "%)  COIL: " + coilHandsTotal + " (" + coPct + "%)  CAP: " + capHands + " (" + caPct + "%) [" + capTriggered + "x, " + capWinRate + "% WR, $" + capPnL.toFixed(2) + "]");
  log("#FD71FD", "Hands: " + handsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(2) + " | Best Recovery: $" + biggestRecovery.toFixed(2) + " | Coil Activations: " + coilActivations);
}

// ============================================================
// VIPER STRATEGY — STRIKE + COIL + CAPITALIZE
// ============================================================

function mainStrategy() {
  handsPlayed++;

  handPnL = lastBet.payout - lastBet.amount;
  totalWagered += lastBet.amount;

  // BJ detection
  if (lastBet.payoutMultiplier >= 2.4 && lastBet.state.player[0].cards.length === 2) {
    totalBlackjacks++;
  }

  // Track doubles/splits
  playerHands = lastBet.state.player;
  if (playerHands.length > 1) totalSplits++;
  for (i = 0; i < playerHands.length; i++) {
    handActions = playerHands[i].actions;
    for (j = 0; j < handActions.length; j++) {
      if (handActions[j] === "double") { totalDoubles++; break; }
    }
  }

  // Result tracking
  if (lastBet.win && lastBet.payoutMultiplier > 1) {
    totalWins++;
    currentWinStreak++;
    currentLossStreak = 0;
    consecLosses = 0;
    winStreak++;
    if (currentWinStreak > longestWinStreak) longestWinStreak = currentWinStreak;
  } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
    // PUSH: neutral event — does NOT reset consecLosses or currentLossStreak.
    // Same as BASILISK tie handling: pushes don't break a loss streak.
    totalPushes++;
  } else {
    totalLosses++;
    currentLossStreak++;
    consecLosses++;
    currentWinStreak = 0;
    if (currentLossStreak > longestLossStreak) longestLossStreak = currentLossStreak;
    winStreak = 0;
  }

  if (profit > peakProfit) peakProfit = profit;

  // === MODE LOGIC ===

  prevMode = mode;

  if (mode === "strike") {
    strikeHands++;

    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      // WIN — recovery complete
      recoveredAmount = currentBet;
      if (recoveredAmount > biggestRecovery) biggestRecovery = recoveredAmount;
      if (currentChainCost > 0) recoveryChains++;
      currentChainCost = 0;
      currentBet = unit;

      // Check capitalize
      if (winStreak >= capitalizeStreak) {
        mode = "capitalize";
        capCount = 0;
        capTriggered++;
      }
    } else if (!lastBet.win) {
      // LOSS
      currentChainCost += lastBet.amount;

      // Check brake
      if (brakeAt > 0 && currentLossStreak >= brakeAt) {
        // BRAKE — switch to coil
        brakeBet = currentBet;
        coilDeficit = 0;
        coilHands = 0;
        coilActivations++;
        mode = "coil";
        // Don't double — hold at current bet
      } else if (delayThreshold > 0 && consecLosses <= delayThreshold) {
        // PATIENCE: absorb early losses at flat bet — don't Martingale yet
        flatAbsorbed++;
      } else {
        // Martingale: double the bet
        currentBet = currentBet * 2;
        martActivations++;
      }
    }

  } else if (mode === "coil") {
    coilHandsTotal++;
    coilHands++;
    coilDeficit += handPnL;

    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      // Win during coil — check if recovered
      if (coilDeficit >= 0) {
        // Recovered! Back to strike at base
        mode = "strike";
        currentBet = unit;
        currentChainCost = 0;
        consecLosses = 0;
        recoveryChains++;

        if (winStreak >= capitalizeStreak) {
          mode = "capitalize";
          capCount = 0;
          capTriggered++;
        }
      }
      // Otherwise stay in coil at same bet (flat)
    }
    // Loss/push in coil: stay at same bet (flat at brake level)


  } else if (mode === "capitalize") {
    capHands++;
    capCount++;
    capPnL += handPnL;

    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      capWins++;
    } else if (!lastBet.win) {
      capLosses++;
    }

    if (!lastBet.win || capCount >= capitalizeMaxBets) {
      mode = "strike";
      winStreak = 0;
      currentBet = unit;
    } else if (lastBet.win && lastBet.payoutMultiplier > 1) {
      currentBet = currentBet * 2;
    }
  }

  if (mode !== prevMode) modeChanges++;

  // Track max bet
  if (currentBet > maxBetSeen) maxBetSeen = currentBet;

  // Trail-aware bet cap: if trail active, cap bet so loss can't breach floor
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    maxTrailBet = profit - trailFloor;
    if (maxTrailBet > 0 && currentBet > maxTrailBet) {
      currentBet = maxTrailBet;
    }
  }

  if (currentBet < unit) currentBet = unit;

  betSize = currentBet;
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

async function vaultHandle() {
  // profit is Antebot's cumulative session P&L (never resets)
  // currentProfit = profit since last vault
  currentProfit = profit - profitAtLastVault;

  if (
    vaultProfitsThreshold > 0 &&
    mode === "strike" &&
    currentBet <= unit * 1.01 &&
    currentProfit >= vaultProfitsThreshold
  ) {
    vaultAmount = currentProfit;
    await depositToVault(vaultAmount);
    totalVaulted += vaultAmount;
    profitAtLastVault = profit; // Mark this profit level as vaulted
    vaultCount++;
    log("#4FFB4F", "Vaulted $" + vaultAmount.toFixed(2) + " | Total vaulted: $" + totalVaulted.toFixed(2));

    // Adaptive unit from remaining balance
    unit = balance / divider;
    if (unit < 0.001) unit = 0.001;
    currentBet = unit;
    betSize = currentBet;

  }
}

function stopProfitCheck() {
  // profit = Antebot's cumulative session P&L (already includes vaulted)
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit && currentBet <= unit * 1.01) {
    log("#4FFB4F", "Target reached! Profit: $" + profit.toFixed(2) + " (Vaulted: $" + totalVaulted.toFixed(2) + " + Current: $" + (profit - profitAtLastVault).toFixed(2) + ")");
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
log("#70FD70", "Starting balance: $" + startBalance.toFixed(2));
log("#42CAF7", "Unit: $" + unit.toFixed(4) + " | Divider: " + divider);
brakeLabel = brakeAt > 0 ? "Brake at LS " + brakeAt + " (" + Math.pow(2, brakeAt).toFixed(0) + "x cap)" : "NO BRAKE (pure Martingale)";
delayLabel = delayThreshold > 0 ? "PATIENCE=" + delayThreshold + " (absorb first " + delayThreshold + " loss)" : "No delay";
log("#FF4500", "ABSORB -> STRIKE (Mart 2x) -> COIL (flat brake) -> CAPITALIZE (Paroli 2x)");
vaultLabel = vaultPct > 0 ? "Vault at " + vaultPct + "% ($" + vaultProfitsThreshold.toFixed(2) + ")" : "No vault";
stopLabel = stopTotalPct > 0 ? "Stop at " + stopTotalPct + "% total ($" + stopOnTotalProfit.toFixed(2) + ")" : "No stop";
log("#FFDB55", brakeLabel + " | " + delayLabel + " | Cap at " + capitalizeStreak + " wins x " + capitalizeMaxBets + " bets");
log("#4FFB4F", vaultLabel + " | " + stopLabel);
log("#FFD700", "Trailing stop: activate at " + trailActivatePct + "% ($" + trailActivateThreshold.toFixed(2) + "), lock " + trailLockPct + "% of peak");

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  trailingStopCheck();
  if (stopped) return;
  await vaultHandle();
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
  strikePct = handsPlayed > 0 ? (strikeHands / handsPlayed * 100).toFixed(1) : "0";
  coilPct = handsPlayed > 0 ? (coilHandsTotal / handsPlayed * 100).toFixed(1) : "0";
  capPct = handsPlayed > 0 ? (capHands / handsPlayed * 100).toFixed(1) : "0";
  capWR = capHands > 0 ? (capWins / capHands * 100).toFixed(0) : "0";
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  exitType = trailStopFired ? "TRAILING STOP" : "TARGET/MANUAL";
  log(
    "#FF4500",
    "================================\n VIPER v" + version + " — " + exitType +
    "\n================================"
  );
  if (trailStopFired) {
    log("#FFD700", "Trail stopped at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + " from peak $" + peakProfit.toFixed(2) + ")");
  }
  log("Hands: " + handsPlayed + " | W/L/P: " + totalWins + "/" + totalLosses + "/" + totalPushes);
  log("BJ: " + totalBlackjacks + " | Doubles: " + totalDoubles + " | Splits: " + totalSplits);
  log("Profit: $" + profit.toFixed(2) + " | Peak: $" + peakProfit.toFixed(2));
  log("RTP: " + rtpFinal + "% | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Longest LS: " + longestLossStreak + " | Longest WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(2) + " | Best Recovery: $" + biggestRecovery.toFixed(2) + " | Recoveries: " + recoveryChains);
  log("Final bet: $" + currentBet.toFixed(2) + " (" + (currentBet / unit).toFixed(1) + "x) | Balance: $" + balance.toFixed(2));
  log("#8B949E", "Modes: STRIKE " + strikeHands + " (" + strikePct + "%) | COIL " + coilHandsTotal + " (" + coilPct + "%) | CAP " + capHands + " (" + capPct + "%)");
  log("#8B949E", "Cap: " + capTriggered + "x W/L: " + capWins + "/" + capLosses + " (" + capWR + "% WR) Net: $" + capPnL.toFixed(4) + " | Coil activations: " + coilActivations);
  log("#9B59B6", "PATIENCE: absorbed=" + flatAbsorbed + " (" + (handsPlayed > 0 ? (flatAbsorbed / handsPlayed * 100).toFixed(0) : "0") + "%) | Mart activations=" + martActivations + " | Delay=" + delayThreshold);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
