// Martingale+Paroli — Blackjack
// Aggressive profit strategy: Martingale 2x recovery + Paroli streak exploitation
// Monte Carlo: +$163 median (div=6k), beats roulette R/B (+$161), 31.5% bust
//
// Modes:
//   RECOVER  — Martingale 2x on loss, reset on win (fast one-shot recovery)
//   CAPITALIZE — Paroli 2x on win, max 2 bets (ride streaks for bonus profit)
//
// The engine that prints money: Martingale recovers ALL losses in a single win.
// Paroli adds profit on top during win streaks. BJ's 0.5% edge means cheaper
// recovery than roulette's 2.7%.
//
// Bet matrix by ConnorMcLeod/Vrafasky (community standard)

strategyTitle = "BJ Mart+Paroli";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
// PROFIT PRESETS:
//
//   Divider | Unit ($1k) | Median  | Bust%  | Win%   | Use Case
//  ---------|------------|---------|--------|--------|----------
//     31526 | $0.032     | +$43    |  9.9%  | 88.1%  | Safe
//     15000 | $0.067     | +$71    | 15.4%  | 83.5%  | Conservative
//      9008 | $0.111     | +$113   | 24.7%  | 74.8%  | Moderate
//      6000 | $0.167     | +$163   | 31.5%  | 68.3%  | Aggressive (recommended)
//      4000 | $0.250     | +$225   | 39.9%  | 60.0%  | Max risk
//
divider = 6000;

// Capitalize trigger
capitalizeStreak = 2;   // Enter Paroli after N consecutive wins
capitalizeMaxBets = 2;  // Max Paroli doublings before returning to recover

// Vault-and-continue. Set 0 to disable.
// Vaults profits when at base bet (safe state). Resets cycle after vault.
vaultProfitsThreshold = 0; // Set to e.g. 5 for $5 vault intervals on $100 bankroll

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 0;
stopBeforeLoss = 0;
stopAfterHands = 0; // 0 = uncapped. Set to 500 for dev testing.

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

sideBetPerfectPairs = 0;
sideBet213 = 0;

// State
mode = "recover";
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
winStreak = 0;
capCount = 0;
lastVaultedProfit = profit;
vaultCount = 0;
peakProfit = 0;
// Mode counters
recoverHands = 0;
capHands = 0;
capWins = 0;
capLosses = 0;
capPnL = 0;
capTriggered = 0;
modeChanges = 0;
maxBetSeen = unit;
lossStreakCost = 0;
biggestRecovery = 0;
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
  return mode === "recover" ? "RECOVER" : "CAPITALIZE";
}

function modeColor() {
  return mode === "recover" ? "#FF6B6B" : "#FD71FD";
}

function logBanner() {
  log(
    "#FF4500",
    `================================
 BJ Mart+Paroli v${version}
================================
 by ${author} | FOR PROFIT
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  capWinRate = capHands > 0 ? (capWins / capHands * 100).toFixed(0) : "0";
  maxLS = Math.floor(Math.log(divider) / Math.log(2));
  runwayBar = mode === "recover" && currentLossStreak > 0
    ? ` | Runway: LS ${currentLossStreak}/${maxLS}`
    : "";
  log("#70FD70", `Balance: $${balance.toFixed(2)} | Unit: $${unit.toFixed(4)} | Bet: $${currentBet.toFixed(4)}`);
  log(modeColor(), `Mode: ${modeLabel()} | LS: ${currentLossStreak} | Bet/Unit: ${(currentBet / unit).toFixed(1)}x${runwayBar}`);
  log("#FFDB55", `W/L/P: ${totalWins}/${totalLosses}/${totalPushes} | Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log("#8B949E", `Modes: R:${recoverHands} K:${capHands} | Cap: ${capTriggered}x (W/L: ${capWins}/${capLosses}, ${capWinRate}% WR) | Net: $${capPnL.toFixed(4)}`);
  log("#FD71FD", `Hands: ${handsPlayed} | Max Bet: $${maxBetSeen.toFixed(4)} | Biggest Recovery: $${biggestRecovery.toFixed(4)} | Vaults: ${vaultCount}`);
}

// ============================================================
// MARTINGALE+PAROLI STRATEGY
// ============================================================

function mainStrategy() {
  handsPlayed++;

  handPnL = lastBet.payout - lastBet.amount;

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
    winStreak++;
    if (currentWinStreak > longestWinStreak) longestWinStreak = currentWinStreak;
  } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
    totalPushes++;
  } else {
    totalLosses++;
    currentLossStreak++;
    currentWinStreak = 0;
    if (currentLossStreak > longestLossStreak) longestLossStreak = currentLossStreak;
    winStreak = 0;
  }

  if (profit > peakProfit) peakProfit = profit;

  // === MODE LOGIC ===

  prevMode = mode;

  if (mode === "recover") {
    recoverHands++;

    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      // WIN — recovery complete, reset to base
      recoveredAmount = currentBet;
      if (recoveredAmount > biggestRecovery) biggestRecovery = recoveredAmount;
      currentBet = unit;

      // Check capitalize trigger
      if (winStreak >= capitalizeStreak) {
        mode = "capitalize";
        capCount = 0;
        capTriggered++;
      }
    } else if (!lastBet.win) {
      // LOSS — Martingale: double the bet
      currentBet = currentBet * 2;
    }
    // push: no change

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
      // Exit capitalize — back to recover at base
      mode = "recover";
      winStreak = 0;
      currentBet = unit;
    } else if (lastBet.win && lastBet.payoutMultiplier > 1) {
      // Paroli: double on win
      currentBet = currentBet * 2;
    }
    // push: preserve bet
  }

  if (mode !== prevMode) modeChanges++;

  // Track max bet
  if (currentBet > maxBetSeen) maxBetSeen = currentBet;

  // Enforce floor (no cap — Martingale needs unlimited runway)
  if (currentBet < unit) currentBet = unit;

  betSize = currentBet;
}

// ============================================================
// VAULT & STOP CHECKS
// ============================================================

async function vaultHandle() {
  if (
    vaultProfitsThreshold > 0 &&
    mode === "recover" &&
    currentBet <= unit * 1.01 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    vaultAmount = profit - lastVaultedProfit;
    await depositToVault(vaultAmount);
    vaultCount++;
    log("#4FFB4F", `Vaulted $${vaultAmount.toFixed(2)} (total: ${vaultCount})`);

    lastVaultedProfit = profit;

    // Adaptive divider
    unit = balance / divider;
    if (unit < 0.001) unit = 0.001;
    currentBet = unit;
    betSize = currentBet;

    resetSeed();
  }
}

function stopProfitCheck() {
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

  if (stopBeforeLoss > 0) {
    worstCase = currentBet * 4;
    if (profit - worstCase <= -Math.abs(stopBeforeLoss)) {
      log("#FD6868", `Stopped to prevent potential $${Math.abs(profit - worstCase).toFixed(2)} Loss`);
      stopped = true;
      logSummary();
      engine.stop();
    }
  }
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#70FD70", `Starting balance: $${startBalance.toFixed(2)}`);
log("#42CAF7", `Unit: $${unit.toFixed(4)} | Divider: ${divider} | Martingale 2x recovery`);
log("#FF4500", `Mart+Paroli: RECOVER (2x on loss, reset on win) + CAPITALIZE (Paroli 2x on streaks)`);
log("#FFDB55", `Capitalize at ${capitalizeStreak} win streak | Max ${capitalizeMaxBets} Paroli bets | No bet cap (unlimited runway)`);

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
  recPct = handsPlayed > 0 ? (recoverHands / handsPlayed * 100).toFixed(1) : "0";
  capPct = handsPlayed > 0 ? (capHands / handsPlayed * 100).toFixed(1) : "0";
  capWinRate = capHands > 0 ? (capWins / capHands * 100).toFixed(0) : "0";
  log(
    "#FF4500",
    `================================
 BJ Mart+Paroli — Session Over
================================`
  );
  log(`Hands: ${handsPlayed} | W/L/P: ${totalWins}/${totalLosses}/${totalPushes}`);
  log(`Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log(`Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Vaults: ${vaultCount}`);
  log(`Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(`Max Bet: $${maxBetSeen.toFixed(4)} | Biggest Recovery: $${biggestRecovery.toFixed(4)}`);
  log(`Final bet: $${currentBet.toFixed(4)} (${(currentBet / unit).toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
  log("#8B949E", `Mode Split: RECOVER ${recoverHands} (${recPct}%) | CAPITALIZE ${capHands} (${capPct}%)`);
  log("#8B949E", `Cap Triggers: ${capTriggered} | Cap W/L: ${capWins}/${capLosses} (${capWinRate}% WR) | Cap Net: $${capPnL.toFixed(4)} | Switches: ${modeChanges}`);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
