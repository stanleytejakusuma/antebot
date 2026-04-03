// Oscar's Grind — Blackjack
// Conservative progression: +1u after win only when in deficit, cycle goal = +1u profit
// Monte Carlo tested: 10k sessions, #1 strategy by median (+$27.62), 19.8% bust
//
// Rules:
//   Win + cycle complete (profit >= unit): reset to base bet, new cycle
//   Win + still in deficit: bet += 1 unit (capped to not overshoot +1u goal)
//   Loss: keep same bet (NEVER increase on loss)
//   Push: no change
//
// Bet matrix by ConnorMcLeod/Vrafasky (community standard)

strategyTitle = "BJ Oscar's Grind";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
//  Divider | Base Bet ($1000) | Bust% (2000h) | Median Net
// ---------|------------------|---------------|----------
//     1000 | $1.00            |  ~46%         | -$116
//     2000 | $0.50            | ~19.8%        | +$28
//     5000 | $0.20            |  ~0.3%        | +$12
divider = 2000;

maxBetMultiple = 10;

// Vault-and-continue. Set 0 to disable.
vaultProfitsThreshold = 0;

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 300;
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
lastVaultedProfit = profit;
vaultCount = 0;
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
  A: 11,
  2: 2,
  3: 3,
  4: 4,
  5: 5,
  6: 6,
  7: 7,
  8: 8,
  9: 9,
  10: 10,
  J: 10,
  Q: 10,
  K: 10,
};

betMatrix = {
  hard: {
    4: {
      2: "H",
      3: "H",
      4: "H",
      5: "H",
      6: "H",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    5: {
      2: "H",
      3: "H",
      4: "H",
      5: "H",
      6: "H",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    6: {
      2: "H",
      3: "H",
      4: "H",
      5: "H",
      6: "H",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    7: {
      2: "H",
      3: "H",
      4: "H",
      5: "H",
      6: "H",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    8: {
      2: "H",
      3: "H",
      4: "H",
      5: "H",
      6: "H",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    9: {
      2: "H",
      3: "D",
      4: "D",
      5: "D",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    10: {
      2: "D",
      3: "D",
      4: "D",
      5: "D",
      6: "D",
      7: "D",
      8: "D",
      9: "D",
      10: "H",
      A: "H",
    },
    11: {
      2: "D",
      3: "D",
      4: "D",
      5: "D",
      6: "D",
      7: "D",
      8: "D",
      9: "D",
      10: "D",
      A: "H",
    },
    12: {
      2: "H",
      3: "H",
      4: "S",
      5: "S",
      6: "S",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    13: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    14: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    15: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    16: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    17: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    18: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    19: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    20: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    21: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
  },
  soft: {
    12: {
      2: "H",
      3: "H",
      4: "H",
      5: "D",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    13: {
      2: "H",
      3: "H",
      4: "H",
      5: "H",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    14: {
      2: "H",
      3: "H",
      4: "H",
      5: "D",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    15: {
      2: "H",
      3: "H",
      4: "H",
      5: "D",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    16: {
      2: "H",
      3: "H",
      4: "D",
      5: "D",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    17: {
      2: "H",
      3: "D",
      4: "D",
      5: "D",
      6: "D",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    18: {
      2: "S",
      3: "DS",
      4: "DS",
      5: "DS",
      6: "DS",
      7: "S",
      8: "S",
      9: "H",
      10: "H",
      A: "H",
    },
    19: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    20: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    21: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
  },
  splits: {
    22: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "P",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    33: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "P",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    44: {
      2: "H",
      3: "H",
      4: "H",
      5: "P",
      6: "P",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    55: {
      2: "D",
      3: "D",
      4: "D",
      5: "D",
      6: "D",
      7: "D",
      8: "D",
      9: "D",
      10: "H",
      A: "H",
    },
    66: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "H",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    77: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "P",
      8: "H",
      9: "H",
      10: "H",
      A: "H",
    },
    88: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "P",
      8: "P",
      9: "P",
      10: "P",
      A: "P",
    },
    99: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "S",
      8: "P",
      9: "P",
      10: "S",
      A: "S",
    },
    1010: {
      2: "S",
      3: "S",
      4: "S",
      5: "S",
      6: "S",
      7: "S",
      8: "S",
      9: "S",
      10: "S",
      A: "S",
    },
    AA: {
      2: "P",
      3: "P",
      4: "P",
      5: "P",
      6: "P",
      7: "P",
      8: "P",
      9: "P",
      10: "P",
      A: "P",
    },
  },
};

// ============================================================
// GAME ROUND HANDLER — Manual bet matrix with DS/double fallback
// ============================================================

engine.onGameRound(function (currentBet, playerHandIndex) {
  if (stopped) return BLACKJACK_STAND;

  dealerValue =
    currentBet.state.dealer[0].value === 11
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
  isSoft =
    cards.some(function (e) {
      return e.rank === "A";
    }) &&
    cards
      .map(function (e) {
        return values[e.rank];
      })
      .reduce(function (a, b) {
        return a + b;
      }, 0) < 21;

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

function logBanner() {
  log(
    "#6BDFFF",
    `================================
 BJ Oscar's Grind v${version}
================================
 by ${author}
-------------------------------------------`,
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  cyclePct =
    cycleProfit >= 0
      ? ((cycleProfit / unit) * 100).toFixed(0)
      : ((cycleProfit / unit) * 100).toFixed(0);
  log(
    "#70FD70",
    `Balance: $${balance.toFixed(2)} | Unit: $${unit.toFixed(4)} | Bet: $${currentBet.toFixed(4)}`,
  );
  log(
    "#6BDFFF",
    `Cycle: $${cycleProfit.toFixed(4)} / $${unit.toFixed(4)} (${cyclePct}%) | Cycles: ${cyclesCompleted}`,
  );
  log(
    "#42CAF7",
    `Bet Multiple: ${(currentBet / unit).toFixed(1)}x / ${maxBetMultiple}x cap`,
  );
  log(
    "#FFDB55",
    `W/L/P: ${totalWins}/${totalLosses}/${totalPushes} | Doubles: ${totalDoubles} | Splits: ${totalSplits}`,
  );
  log(
    "#A4FD68",
    `Profit: $${profit.toFixed(2)} | Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`,
  );
  log("#FD71FD", `Hands: ${handsPlayed} | Vaults: ${vaultCount}`);
}

// ============================================================
// OSCAR'S GRIND STRATEGY
// ============================================================

function mainStrategy() {
  handsPlayed++;

  // Hand P&L (naturally accounts for doubles and splits)
  handPnL = lastBet.payout - lastBet.amount;
  cycleProfit += handPnL;

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

  if (lastBet.win && lastBet.payoutMultiplier > 1) {
    // WIN
    totalWins++;
    currentWinStreak++;
    currentLossStreak = 0;
    if (currentWinStreak > longestWinStreak)
      longestWinStreak = currentWinStreak;

    if (cycleProfit >= unit) {
      // Cycle complete — banked +1u, reset
      cyclesCompleted++;
      cycleProfit = 0;
      currentBet = unit;
    } else {
      // Still in deficit — increase by 1u, cap to not overshoot
      needed = unit - cycleProfit;
      currentBet = Math.min(currentBet + unit, needed, maxBet);
      currentBet = Math.max(currentBet, unit);
    }
  } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
    // PUSH — no change
    totalPushes++;
  } else {
    // LOSS — keep same bet (never increase on loss)
    totalLosses++;
    currentLossStreak++;
    currentWinStreak = 0;
    if (currentLossStreak > longestLossStreak)
      longestLossStreak = currentLossStreak;
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
    cycleProfit === 0 &&
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
    worstCase = currentBet * 4;
    if (profit - worstCase <= -Math.abs(stopBeforeLoss)) {
      log(
        "#FD6868",
        `Stopped to prevent potential $${Math.abs(profit - worstCase).toFixed(2)} Loss`,
      );
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
log(
  "#42CAF7",
  `Unit: $${unit.toFixed(4)} | Max bet: $${maxBet.toFixed(4)} (${maxBetMultiple}x cap)`,
);
log(
  "#6BDFFF",
  `Oscar's Grind: +1u after win (only in deficit), cycle goal = +1u profit`,
);
log(
  "#FFDB55",
  `Never increases bet on loss | Cycle resets at +$${unit.toFixed(4)} profit`,
);

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
  log(
    "#6BDFFF",
    `================================
 BJ Oscar's Grind — Session Over
================================`,
  );
  log(
    `Hands: ${handsPlayed} | W/L/P: ${totalWins}/${totalLosses}/${totalPushes}`,
  );
  log(`Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log(
    `Cycles completed: ${cyclesCompleted} | Final cycle P&L: $${cycleProfit.toFixed(4)}`,
  );
  log(`Profit: $${profit.toFixed(2)} | Vaults: ${vaultCount}`);
  log(`Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(
    `Final bet: $${currentBet.toFixed(4)} (${(currentBet / unit).toFixed(1)}x) | Balance: $${balance.toFixed(2)}`,
  );
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
