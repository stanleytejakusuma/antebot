strategyTitle = "BJ d'Alembert Perfect Strat";
author = "Swen";
version = "1.0";
scripter = "Vrafasky";

game = "blackjack";

divider = 10000; // define the divider for your unit size.
unit = balance / divider; // unit size. also act as the initial bet size
betSize = unit;

if (casino === "SHUFFLE") {
  sideBetPerfectPairs = 0;
  sideBet213 = 0;
}

// Vaulting & Stop P/L Setup. Set 0 to disable
vaultProfitsThreshold = 0; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

// DO NOT EDIT BELOW
//vault init
lastVaultedProfit = profit;
startProfit = profit;
/* Bet Matrix Converter . Code Snippet  by ConnorMcLeod*/
betMatrixReturns = {
  H: BLACKJACK_HIT,
  S: BLACKJACK_STAND,
  P: BLACKJACK_SPLIT,
  D: BLACKJACK_DOUBLE,
};

const values = {
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

engine.onGameRound((currentBet, playerHandIndex) => {
  const dealerValue =
    currentBet.state.dealer[0].value === 11
      ? "A"
      : currentBet.state.dealer[0].value;
  const player = currentBet.state.player;

  if (
    player.length === 1 &&
    player[0].cards.length === 2 &&
    player[0].cards[0].rank === player[0].cards[1].rank
  ) {
    const betMatrixFix = ["J", "Q", "K"].includes(player[0].cards[0].rank)
      ? "1010"
      : "" + player[0].cards[0].rank + player[0].cards[1].rank;
    return betMatrixReturns[betMatrix.splits[betMatrixFix][dealerValue]];
  }

  const cards = player[playerHandIndex].cards;
  const value = player[playerHandIndex].value;
  const isSoft =
    cards.some((e) => e.rank === "A") &&
    cards.map((e) => values[e.rank]).reduce((a, b) => a + b, 0) < 21;

  if (isSoft) {
    returnValue = betMatrixReturns[betMatrix.soft[value][dealerValue]];
  } else {
    returnValue = betMatrixReturns[betMatrix.hard[value][dealerValue]];
  }

  return (
    ((returnValue !== BLACKJACK_DOUBLE || cards.length === 2) && returnValue) ||
    BLACKJACK_HIT
  );
});

//vault init
lastVaultedProfit = profit;
startProfit = profit;

engine.onBetPlaced(async (lastBet) => {
  stopProfitCheck();
  await vaultHandle();

  prevLoss = lastBet.amount - lastBet.payout;

  if (lastBet.win) {
    if (profit >= highestProfit) {
      betSize = unit;
    } else {
      if (lastBet.payoutMultiplier == 1) {
        betSize = lastBet.amount;
      } else {
        if (betSize > unit) {
          betSize = lastBet.amount - unit;
        } else {
          betSize = unit;
        }
      }
    }
  } else {
    betSize = prevLoss + unit;
  }

  stopLossCheck();
});

//UTILITIES FUNCTION

logBanner();

function logBanner() {
  log(
    "#80EE51",
    `================================
${strategyTitle} v${version} by ${author}
================================
Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`,
  );
}

Number.prototype.dynFixed = function () {
  return this.toFixed(Math.max(-Math.floor(Math.log10(this)), 0) + 2);
};

Number.prototype.toFiatString = function () {
  return (this * getConversionRate()).toLocaleString(0, {
    style: "currency",
    currency: "USD",
  });
};

function checkStopWithLog(
  condition,
  color,
  messagePrefix,
  amount,
  conditionMessage = "",
) {
  if (condition) {
    log(
      color,
      `${messagePrefix} ${amount.dynFixed()} ${currency.toUpperCase()} / ${amount.toFiatString()} ${conditionMessage}`,
    );
    engine.stop();
  }
}

function stopProfitCheck() {
  checkStopWithLog(
    stopOnProfit && profit >= stopOnProfit,
    "#4FFB4F",
    "✅ Stopped on",
    profit,
    "Profit",
  );
}

function stopLossCheck() {
  potentialLoss = -(profit - betSize);

  checkStopWithLog(
    stopOnLoss !== 0 && profit < -Math.abs(stopOnLoss),
    "#FFFF2A",
    "⛔️ Stopped on loss of",
    -profit,
    "Loss",
  );
  checkStopWithLog(
    stopBeforeLoss !== 0 && profit - betSize <= -Math.abs(stopBeforeLoss),
    "#FFFF2A",
    "⛔️ Stopped to prevent a",
    potentialLoss,
    "Loss",
  );
}

async function vaultHandle() {
  if (
    vaultProfitsThreshold > 0 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    let vaultingAmount = profit - lastVaultedProfit;
    await depositToVault(vaultingAmount);
    log(
      `Vaulting ${vaultingAmount.toFixed(Math.max(-Math.floor(Math.log10(vaultingAmount)), 0) + 2)} ${currency}`,
    );
    lastVaultedProfit = profit;
  }
}
