// Action-Weighted D'Alembert for Blackjack
// Source: https://forum.antebot.com/t/perfect-bj-d-alembert-new-approach/887
// Concept by swenmustwatchgames0, bet matrix by ConnorMcLeod/Vrafasky
//
// Uses manual bet matrix (community standard) instead of built-in function.
// D'Alembert with action-weighted units: doubles/splits adjust by 2-4 units.
// Monte Carlo tested: div=2000, cap=10x → 10% bust rate, -$15/session on $1000.

strategyTitle = "BJ D'Alembert AW";
version = "1.1.0";
author = "swenmustwatchgames0";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
//  Divider | Base Bet ($1000) | Bust% (2000 hands) | Mean Net
// ---------|------------------|---------------------|----------
//      500 | $2.00            | ~70%                | -$65
//     1000 | $1.00            | ~45%                | -$60
//     2000 | $0.50            | ~10%                | -$15
//     5000 | $0.20            |  ~0%                | -$14
divider = 2000;

maxBetMultiple = 10;

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 300;
stopBeforeLoss = 0;

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

if (casino === "SHUFFLE" || casino === "SHUFFLE_US") {
  sideBetPerfectPairs = 0;
  sideBet213 = 0;
}

// State
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
// GAME ROUND HANDLER — Manual bet matrix with edge case handling
// ============================================================

engine.onGameRound(function (currentBet, playerHandIndex) {
  if (stopped) return BLACKJACK_STAND;

  dealerValue = currentBet.state.dealer[0].value === 11
    ? "A"
    : currentBet.state.dealer[0].value;
  player = currentBet.state.player;

  // Check for split opportunity (two identical cards, first hand, 2 cards)
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

  // Handle DS (double or stand) — if can't double (3+ cards), stand instead
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

function logBanner() {
  log(
    "#2AFFCA",
    `================================
 🃏 ${strategyTitle} v${version}
================================
 by ${author} | scripted by ${scripter}
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  log("#70FD70", `Balance: $${balance.toFixed(2)} | Unit: $${unit.toFixed(4)} | Bet: $${currentBet.toFixed(4)}`);
  log("#42CAF7", `Bet Multiple: ${(currentBet / unit).toFixed(1)}x / ${maxBetMultiple}x cap`);
  log("#FFDB55", `W/L/P: ${totalWins}/${totalLosses}/${totalPushes} | Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Win Streak: ${currentWinStreak} | Longest LS: ${longestLossStreak}`);
  log("#FD71FD", `Hands: ${handsPlayed} | Balance: $${balance.toFixed(2)}`);
}

// ============================================================
// D'ALEMBERT PROGRESSION — Action-Weighted
// ============================================================

function getUnitWeight() {
  hands = lastBet.state.player;
  totalUnits = 0;

  for (i = 0; i < hands.length; i++) {
    actions = hands[i].actions;
    hadDouble = false;

    for (j = 0; j < actions.length; j++) {
      if (actions[j] === "double") {
        hadDouble = true;
        break;
      }
    }

    totalUnits += hadDouble ? 2 : 1;
  }

  return totalUnits;
}

function mainStrategy() {
  handsPlayed++;

  if (lastBet.win && lastBet.payoutMultiplier > 1) {
    // WIN
    totalWins++;
    currentWinStreak++;
    currentLossStreak = 0;
    if (currentWinStreak > longestWinStreak) longestWinStreak = currentWinStreak;

    weight = getUnitWeight();
    if (lastBet.state.player.length > 1) totalSplits++;
    if (weight >= 2 && lastBet.state.player.length === 1) totalDoubles++;

    // Reset to base if at new profit peak (classic D'Alembert reset)
    if (profit >= highestProfit) {
      currentBet = unit;
    } else {
      // Decrease by weighted units
      currentBet -= weight * unit;
    }
  } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
    // PUSH — keep same bet
    totalPushes++;
  } else {
    // LOSS
    totalLosses++;
    currentLossStreak++;
    currentWinStreak = 0;
    if (currentLossStreak > longestLossStreak) longestLossStreak = currentLossStreak;

    weight = getUnitWeight();
    if (lastBet.state.player.length > 1) totalSplits++;
    if (weight >= 2 && lastBet.state.player.length === 1) totalDoubles++;

    // Increase by weighted units
    currentBet += weight * unit;
  }

  // Enforce bounds
  if (currentBet < unit) currentBet = unit;
  if (currentBet > maxBet) currentBet = maxBet;

  betSize = currentBet;
}

// ============================================================
// STOP CHECKS
// ============================================================

function stopProfitCheck() {
  if (stopOnProfit > 0 && profit >= stopOnProfit) {
    log("#4FFB4F", `✅ Stopped on $${profit.toFixed(2)} Profit`);
    stopped = true;
    engine.stop();
  }
}

function stopLossCheck() {
  if (stopOnLoss > 0 && profit < -Math.abs(stopOnLoss)) {
    log("#FD6868", `⛔ Stopped on $${(-profit).toFixed(2)} Loss`);
    stopped = true;
    engine.stop();
  }

  if (stopBeforeLoss > 0) {
    worstCase = currentBet * 4;
    if (profit - worstCase <= -Math.abs(stopBeforeLoss)) {
      log("#FD6868", `⛔ Stopped to prevent potential $${Math.abs(profit - worstCase).toFixed(2)} Loss`);
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
log("#FD71FD", `D'Alembert AW: +N units on loss, -N units on win (N = 1 normal, 2 double/split, 4 split+double)`);
log("#FFDB55", `Reset to base at profit peak | Manual bet matrix (perfect basic strategy)`);

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  stopProfitCheck();
  stopLossCheck();
});

engine.onBettingStopped(function () {
  playHitSound();
  log(
    "#2AFFCA",
    `================================
 🃏 ${strategyTitle} — Session Over
================================`
  );
  log(`Hands: ${handsPlayed} | W/L/P: ${totalWins}/${totalLosses}/${totalPushes}`);
  log(`Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log(`Profit: $${profit.toFixed(2)} | Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(`Final bet: $${currentBet.toFixed(4)} (${(currentBet / unit).toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
});
