// Momentum Shift — Blackjack
// Three-mode regime betting: Cruise → Recovery → Capitalize
// Monte Carlo tested: 30k sessions × 3 trials, only strategy with positive median (+$10.25)
//
// Modes:
//   Cruise    — flat bet at unit (default, near breakeven)
//   Recovery  — D'Alembert +1 unit on loss, -1 on win (when deficit grows)
//   Capitalize — Paroli 2x on win (on win streaks, rides momentum)
//
// Bet matrix by ConnorMcLeod/Vrafasky (community standard)

strategyTitle = "BJ Momentum Shift";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
//  Divider | Base Bet ($1000) | Bust% (2000h) | Median Net
// ---------|------------------|---------------|----------
//     1000 | $1.00            |  ~25%         |  +$5
//     2000 | $0.50            |  ~9.4%        | +$10
//     5000 | $0.20            |   ~1%         |  +$2
divider = 2000;

maxBetMultiple = 10;

// Mode thresholds (in units)
// Monte Carlo optimized: rec=8/3 → median +$29 at 8.2% bust (vs default 5/2 → +$15 at 9.3%)
recoveryThreshold = 8;    // Enter recovery when deficit > N * unit
recoveryExit = 3;         // Exit recovery when deficit < N * unit
capitalizeStreak = 3;     // Enter capitalize after N consecutive wins
capitalizeMaxBets = 2;    // Max capitalize bets before returning to cruise

// Vault-and-continue. Set 0 to disable.
vaultProfitsThreshold = 0;

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 0; // Disabled for testing. Set to 30% of bankroll for live.
stopBeforeLoss = 0;
stopAfterHands = 0; // Uncapped — runs until manual stop or bust.

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
unit = startBalance / divider;
if (unit < 0.001) unit = 0.001;
maxBet = unit * maxBetMultiple;

sideBetPerfectPairs = 0;
sideBet213 = 0;

// State
mode = "cruise";
deficit = 0;
winStreak = 0;
capCount = 0;
currentBet = unit;
handsPlayed = 0;
totalWins = 0;
totalLosses = 0;
totalPushes = 0;
totalDoubles = 0;
totalSplits = 0;
longestWinStreak = 0;
longestLossStreak = 0;
currentWinStreak = 0;
currentLossStreak = 0;
lastVaultedProfit = profit;
vaultCount = 0;
cruiseHands = 0;
recoveryHands = 0;
capitalizeHands = 0;
modeChanges = 0;
capWins = 0;
capLosses = 0;
peakProfit = 0;
stopped = false;

betSize = currentBet;

// ============================================================
// BET MATRIX — Perfect Basic Strategy (ConnorMcLeod/Vrafasky)
// H=Hit, S=Stand, D=Double or Hit, DS=Double or Stand, P=Split
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
// GAME ROUND HANDLER — Manual bet matrix with DS/double fallback
// ============================================================

engine.onGameRound(function (currentBet, playerHandIndex) {
  if (stopped) return BLACKJACK_STAND;

  dealerValue = currentBet.state.dealer[0].value === 11
    ? "A"
    : currentBet.state.dealer[0].value;
  player = currentBet.state.player;

  // Split check (two identical cards, first hand, 2 cards)
  if (
    player.length === 1 &&
    player[0].cards.length === 2 &&
    player[0].cards[0].rank === player[0].cards[1].rank
  ) {
    splitKey = ["J", "Q", "K"].includes(player[0].cards[0].rank)
      ? "1010"
      : "" + player[0].cards[0].rank + player[0].cards[1].rank;
    nextAction = betMatrixReturns[betMatrix.splits[splitKey][dealerValue]];

    if (nextAction === BLACKJACK_DOUBLE) {
      betSize *= 2;
    }
    return nextAction;
  }

  // Normal hand — check soft vs hard
  cards = player[playerHandIndex].cards;
  handValue = player[playerHandIndex].value;
  isSoft = cards.some(function (e) { return e.rank === "A"; })
    && cards.map(function (e) { return values[e.rank]; }).reduce(function (a, b) { return a + b; }, 0) < 21;

  if (isSoft) {
    matrixAction = betMatrix.soft[handValue][dealerValue];
  } else {
    matrixAction = betMatrix.hard[handValue][dealerValue];
  }

  // DS = double or stand (if can't double on 3+ cards, stand instead)
  if (matrixAction === "DS") {
    if (cards.length === 2) {
      nextAction = BLACKJACK_DOUBLE;
    } else {
      nextAction = BLACKJACK_STAND;
    }
  } else {
    nextAction = betMatrixReturns[matrixAction];
  }

  // Can only double on first 2 cards — fallback to hit
  if (nextAction === BLACKJACK_DOUBLE && cards.length > 2) {
    nextAction = BLACKJACK_HIT;
  }

  if (nextAction === BLACKJACK_DOUBLE) {
    betSize *= 2;
  }

  return nextAction;
});

// ============================================================
// LOGGING
// ============================================================

function modeLabel() {
  if (mode === "cruise") return "CRUISE";
  if (mode === "recovery") return "RECOVERY";
  if (mode === "capitalize") return "CAPITALIZE";
  return mode;
}

function modeColor() {
  if (mode === "cruise") return "#70FD70";
  if (mode === "recovery") return "#FFDB55";
  if (mode === "capitalize") return "#FD71FD";
  return "#FFFFFF";
}

function logBanner() {
  log(
    "#FF9933",
    `================================
 BJ Momentum Shift v${version}
================================
 by ${author}
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  log("#70FD70", `Balance: $${balance.toFixed(2)} | Unit: $${unit.toFixed(4)} | Bet: $${currentBet.toFixed(4)}`);
  log(modeColor(), `Mode: ${modeLabel()} | Deficit: $${deficit.toFixed(2)} (${(deficit / unit).toFixed(1)}u) | WS: ${winStreak}`);
  log("#42CAF7", `Bet Multiple: ${(currentBet / unit).toFixed(1)}x / ${maxBetMultiple}x cap`);
  log("#FFDB55", `W/L/P: ${totalWins}/${totalLosses}/${totalPushes} | Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log("#8B949E", `Modes: C:${cruiseHands} R:${recoveryHands} K:${capitalizeHands} | Switches: ${modeChanges} | Cap W/L: ${capWins}/${capLosses}`);
  log("#FD71FD", `Hands: ${handsPlayed} | Vaults: ${vaultCount}`);
}

// ============================================================
// MOMENTUM SHIFT STRATEGY
// ============================================================

function mainStrategy() {
  handsPlayed++;

  // Hand P&L (lastBet.amount includes doubled/split totals)
  handPnL = lastBet.payout - lastBet.amount;

  // Track doubles/splits for stats
  playerHands = lastBet.state.player;
  if (playerHands.length > 1) totalSplits++;
  for (i = 0; i < playerHands.length; i++) {
    handActions = playerHands[i].actions;
    for (j = 0; j < handActions.length; j++) {
      if (handActions[j] === "double") {
        totalDoubles++;
        break;
      }
    }
  }

  // === RESULT PROCESSING ===

  if (lastBet.win && lastBet.payoutMultiplier > 1) {
    // WIN
    totalWins++;
    currentWinStreak++;
    currentLossStreak = 0;
    winStreak++;
    if (currentWinStreak > longestWinStreak) longestWinStreak = currentWinStreak;
    deficit = Math.max(0, deficit - Math.abs(handPnL));

  } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
    // PUSH — neutral, preserves win streak
    totalPushes++;

  } else {
    // LOSS
    totalLosses++;
    currentLossStreak++;
    currentWinStreak = 0;
    if (currentLossStreak > longestLossStreak) longestLossStreak = currentLossStreak;
    winStreak = 0;
    deficit += Math.abs(handPnL);
  }

  // === MODE TRACKING ===

  if (mode === "cruise") cruiseHands++;
  else if (mode === "recovery") recoveryHands++;
  else if (mode === "capitalize") capitalizeHands++;

  // Track capitalize performance
  if (mode === "capitalize") {
    if (lastBet.win && lastBet.payoutMultiplier > 1) capWins++;
    else if (!lastBet.win) capLosses++;
  }

  if (profit > peakProfit) peakProfit = profit;

  // === MODE TRANSITIONS ===

  prevMode = mode;

  if (mode === "cruise") {
    if (deficit > recoveryThreshold * unit) {
      mode = "recovery";
    } else if (winStreak >= capitalizeStreak) {
      mode = "capitalize";
      capCount = 0;
    }
  } else if (mode === "recovery") {
    if (deficit < recoveryExit * unit) {
      mode = "cruise";
    }
  } else if (mode === "capitalize") {
    capCount++;
    if (!lastBet.win || capCount >= capitalizeMaxBets) {
      mode = "cruise";
      winStreak = 0;
    }
  }

  if (mode !== prevMode) modeChanges++;

  // === BET SIZING ===

  if (mode === "cruise") {
    currentBet = unit;
  } else if (mode === "recovery") {
    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      currentBet -= unit;
    } else if (!lastBet.win) {
      currentBet += unit;
    }
    // push: no change
  } else if (mode === "capitalize") {
    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      currentBet = currentBet * 2;
    } else if (!lastBet.win) {
      currentBet = unit;
    }
    // push: preserve current bet for next capitalize hand
  }

  // Enforce bounds
  if (currentBet < unit) currentBet = unit;
  if (currentBet > maxBet) currentBet = maxBet;

  betSize = currentBet;
}

// ============================================================
// VAULT & STOP CHECKS
// ============================================================

async function vaultHandle() {
  if (
    vaultProfitsThreshold > 0 &&
    mode === "cruise" &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    vaultAmount = profit - lastVaultedProfit;
    await depositToVault(vaultAmount);
    vaultCount++;
    log("#4FFB4F", `Vaulted $${vaultAmount.toFixed(2)} (total: ${vaultCount})`);

    lastVaultedProfit = profit;

    // Adaptive divider — recalculate from current balance
    unit = balance / divider;
    if (unit < 0.001) unit = 0.001;
    maxBet = unit * maxBetMultiple;

    // Reset cycle
    mode = "cruise";
    deficit = 0;
    winStreak = 0;
    capCount = 0;
    currentBet = unit;
    betSize = currentBet;

    resetSeed();
  }
}

function stopProfitCheck() {
  if (stopOnProfit > 0 && profit >= stopOnProfit) {
    log("#4FFB4F", `Stopped on $${profit.toFixed(2)} Profit`);
    stopped = true;
    engine.stop();
  }
}

function stopLossCheck() {
  if (stopOnLoss > 0 && profit < -Math.abs(stopOnLoss)) {
    log("#FD6868", `Stopped on $${(-profit).toFixed(2)} Loss`);
    stopped = true;
    engine.stop();
  }

  if (stopBeforeLoss > 0) {
    worstCase = currentBet * 4; // worst case: split + double both hands
    if (profit - worstCase <= -Math.abs(stopBeforeLoss)) {
      log("#FD6868", `Stopped to prevent potential $${Math.abs(profit - worstCase).toFixed(2)} Loss`);
      stopped = true;
      engine.stop();
    }
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#70FD70", `Starting balance: $${startBalance.toFixed(2)}`);
log("#42CAF7", `Unit: $${unit.toFixed(4)} | Max bet: $${maxBet.toFixed(4)} (${maxBetMultiple}x cap)`);
log("#FF9933", `Modes: CRUISE (flat) | RECOVERY (D'Alembert) | CAPITALIZE (Paroli 2x)`);
log("#FFDB55", `Recovery at ${recoveryThreshold}u deficit | Capitalize at ${capitalizeStreak} win streak`);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  await vaultHandle();
  stopProfitCheck();
  stopLossCheck();

  if (stopAfterHands > 0 && handsPlayed >= stopAfterHands) {
    log("#FFFF2A", `Dev stop: ${handsPlayed} hands reached`);
    stopped = true;
    logSummary();
    engine.stop();
  }
});

function logSummary() {
  playHitSound();
  cruisePct = handsPlayed > 0 ? (cruiseHands / handsPlayed * 100).toFixed(1) : "0";
  recoveryPct = handsPlayed > 0 ? (recoveryHands / handsPlayed * 100).toFixed(1) : "0";
  capitalizePct = handsPlayed > 0 ? (capitalizeHands / handsPlayed * 100).toFixed(1) : "0";
  log(
    "#FF9933",
    `================================
 BJ Momentum Shift — Session Over
================================`
  );
  log(`Hands: ${handsPlayed} | W/L/P: ${totalWins}/${totalLosses}/${totalPushes}`);
  log(`Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log(`Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Vaults: ${vaultCount}`);
  log(`Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(`Final Mode: ${modeLabel()} | Deficit: $${deficit.toFixed(2)}`);
  log(`Final bet: $${currentBet.toFixed(4)} (${(currentBet / unit).toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
  log("#8B949E", `Mode Split: CRUISE ${cruiseHands} (${cruisePct}%) | RECOVERY ${recoveryHands} (${recoveryPct}%) | CAPITALIZE ${capitalizeHands} (${capitalizePct}%)`);
  log("#8B949E", `Mode Switches: ${modeChanges} | Capitalize W/L: ${capWins}/${capLosses}`);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
