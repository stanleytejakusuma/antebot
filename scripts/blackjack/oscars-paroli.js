// Oscar's Paroli — Blackjack
// Two-mode hybrid: Oscar's Grind recovery + Paroli streak exploitation
// Monte Carlo champion: +$112 median (x20), 32% bust, 60% win rate
// Beats all 15 tested strategies + all attempted improvements
//
// Modes:
//   GRIND    — Oscar's cycle: +1u after win only in deficit, goal +1u
//   CAPITALIZE — Paroli: 2x on win, max 2 bets, only when cycle is positive
//
// Key: capitalize only fires from profitable cycle state, never during recovery.
// This means Paroli rides streaks while Oscar's handles all deficit recovery.
//
// Bet matrix by ConnorMcLeod/Vrafasky (community standard)

strategyTitle = "BJ Oscar's Paroli";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
// PROFIT PRESETS (pick your risk tolerance):
//
//   Divider | Cap |  Base ($1k) | Median  | Bust%  | Use Case
//  ---------|-----|-------------|---------|--------|----------
//      2000 | x10 | $0.50       | +$37    | 18.3%  | Conservative
//      2000 | x15 | $0.50       | +$84    | 27.9%  | Moderate
//      2000 | x20 | $0.50       | +$112   | 32.2%  | Aggressive (recommended)
//      2000 | x25 | $0.50       | +$127   | 34.3%  | Very aggressive
//      2000 | x30 | $0.50       | +$134   | 35.4%  | Max risk
//
// SCALING: Median profit scales linearly with unit size.
//   $100 bankroll, div=200 → unit=$0.50 → same median as $1000/div=2000
//   $50 bankroll, div=100 → unit=$0.50 → same median as $1000/div=2000
//   Key: keep unit ~= bankroll/2000 for tested risk profile.
//   Lower divider = bigger unit = faster profit + faster bust.
//
divider = 200;
maxBetMultiple = 20;

// Capitalize trigger
capitalizeStreak = 2;   // Enter Paroli after N consecutive wins
capitalizeMaxBets = 2;  // Max Paroli doublings before returning to grind

// Vault-and-continue. Set 0 to disable.
vaultProfitsThreshold = 0;

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 0;
stopBeforeLoss = 0;
stopAfterHands = 500; // Dev mode: stop after N hands. 0 = disabled.

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
mode = "grind";
cycleProfit = 0;
cyclesCompleted = 0;
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
grindHands = 0;
capHands = 0;
capWins = 0;
capLosses = 0;
capPnL = 0;
capTriggered = 0;
modeChanges = 0;
deepestCycle = 0;
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

  // Split check
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

  // Normal hand — soft vs hard
  cards = player[playerHandIndex].cards;
  handValue = player[playerHandIndex].value;
  isSoft = cards.some(function (e) { return e.rank === "A"; })
    && cards.map(function (e) { return values[e.rank]; }).reduce(function (a, b) { return a + b; }, 0) < 21;

  if (isSoft) {
    matrixAction = betMatrix.soft[handValue][dealerValue];
  } else {
    matrixAction = betMatrix.hard[handValue][dealerValue];
  }

  // DS = double or stand
  if (matrixAction === "DS") {
    if (cards.length === 2) {
      nextAction = BLACKJACK_DOUBLE;
    } else {
      nextAction = BLACKJACK_STAND;
    }
  } else {
    nextAction = betMatrixReturns[matrixAction];
  }

  // Can only double on first 2 cards
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
  return mode === "grind" ? "GRIND" : "CAPITALIZE";
}

function modeColor() {
  return mode === "grind" ? "#6BDFFF" : "#FD71FD";
}

function logBanner() {
  log(
    "#FFD700",
    `================================
 BJ Oscar's Paroli v${version}
================================
 by ${author}
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  cyclePctLabel = cycleProfit >= 0
    ? `+${(cycleProfit / unit * 100).toFixed(0)}%`
    : `${(cycleProfit / unit * 100).toFixed(0)}%`;
  log("#70FD70", `Balance: $${balance.toFixed(2)} | Unit: $${unit.toFixed(4)} | Bet: $${currentBet.toFixed(4)}`);
  log(modeColor(), `Mode: ${modeLabel()} | Cycle: $${cycleProfit.toFixed(4)} (${cyclePctLabel}) | Cycles: ${cyclesCompleted}`);
  log("#42CAF7", `Bet Multiple: ${(currentBet / unit).toFixed(1)}x / ${maxBetMultiple}x cap`);
  log("#FFDB55", `W/L/P: ${totalWins}/${totalLosses}/${totalPushes} | Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  capWinRate = capHands > 0 ? (capWins / capHands * 100).toFixed(0) : "0";
  log("#8B949E", `Modes: G:${grindHands} K:${capHands} | Cap: ${capTriggered}x (W/L: ${capWins}/${capLosses}, ${capWinRate}% WR) | Net: $${capPnL.toFixed(4)}`);
  log("#FD71FD", `Hands: ${handsPlayed} | Deepest Cycle: $${deepestCycle.toFixed(4)} | Switches: ${modeChanges} | Vaults: ${vaultCount}`);
}

// ============================================================
// OSCAR'S PAROLI STRATEGY
// ============================================================

function mainStrategy() {
  handsPlayed++;

  // Hand P&L
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

  // === MODE-SPECIFIC LOGIC ===

  prevMode = mode;

  if (mode === "grind") {
    grindHands++;
    cycleProfit += handPnL;

    // Track deepest cycle
    if (cycleProfit < -deepestCycle) deepestCycle = -cycleProfit;

    if (lastBet.win && lastBet.payoutMultiplier > 1) {
      if (cycleProfit >= unit) {
        // Cycle complete
        cyclesCompleted++;
        cycleProfit = 0;
        currentBet = unit;
      } else {
        // Still in deficit — raise by 1u, cap to not overshoot
        needed = unit - cycleProfit;
        currentBet = Math.min(currentBet + unit, needed, maxBet);
        currentBet = Math.max(currentBet, unit);
      }
    }
    // loss/push: keep same bet (Oscar's never raises on loss)

    // Check capitalize trigger: win streak + cycle is positive
    if (winStreak >= capitalizeStreak && cycleProfit >= 0) {
      mode = "capitalize";
      capCount = 0;
      capTriggered++;
    }

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
      // Exit capitalize
      mode = "grind";
      winStreak = 0;
      currentBet = unit;
      cycleProfit = 0; // Fresh cycle after capitalize
    } else if (lastBet.win && lastBet.payoutMultiplier > 1) {
      // Paroli: double on win
      currentBet = currentBet * 2;
    }
    // push in capitalize: preserve bet
  }

  if (mode !== prevMode) modeChanges++;

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
    mode === "grind" &&
    cycleProfit >= 0 &&
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
    maxBet = unit * maxBetMultiple;

    // Reset cycle
    cycleProfit = 0;
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
log("#42CAF7", `Unit: $${unit.toFixed(4)} | Max bet: $${maxBet.toFixed(4)} (${maxBetMultiple}x cap)`);
log("#FFD700", `Oscar's Paroli: GRIND (Oscar +1u cycle) + CAPITALIZE (Paroli 2x on streaks)`);
log("#FFDB55", `Capitalize at ${capitalizeStreak} win streak | Max ${capitalizeMaxBets} Paroli bets`);

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
  grindPct = handsPlayed > 0 ? (grindHands / handsPlayed * 100).toFixed(1) : "0";
  capPct = handsPlayed > 0 ? (capHands / handsPlayed * 100).toFixed(1) : "0";
  log(
    "#FFD700",
    `================================
 BJ Oscar's Paroli — Session Over
================================`
  );
  log(`Hands: ${handsPlayed} | W/L/P: ${totalWins}/${totalLosses}/${totalPushes}`);
  log(`Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log(`Cycles completed: ${cyclesCompleted} | Deepest cycle: $${deepestCycle.toFixed(4)}`);
  log(`Profit: $${profit.toFixed(2)} | Peak: $${peakProfit.toFixed(2)} | Vaults: ${vaultCount}`);
  log(`Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(`Final bet: $${currentBet.toFixed(4)} (${(currentBet / unit).toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
  log("#8B949E", `Mode Split: GRIND ${grindHands} (${grindPct}%) | CAPITALIZE ${capHands} (${capPct}%)`);
  capWinRateFinal = capHands > 0 ? (capWins / capHands * 100).toFixed(0) : "0";
  log("#8B949E", `Cap Triggers: ${capTriggered} | Cap W/L: ${capWins}/${capLosses} (${capWinRateFinal}% WR) | Cap Net: $${capPnL.toFixed(4)} | Switches: ${modeChanges}`);
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
