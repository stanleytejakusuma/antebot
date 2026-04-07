strategyTitle = "HI profit LO losses";
author = " Dandalf ";
version = "4.0.0";
scripter = " Dandalf";

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

game = "hilo";

divider = 25000;
betSize = balance / divider; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;

startCard = {
  rank: "K",
  suit: "C",
};

cashOutAtMultiplier = 3;
increaseOnLoss = 1.3;

// Vaulting & Stop P/L Setup. Set 0 to disable
vaultProfitsThreshold = 0; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

// Define the probabilities first one is the safer second one is the more risky
const probabilities = [
  42.5, // 1. HILO_BET_HIGH
  2, // 2. HILO_BET_HIGH_EQUAL
  42.5, // 3. HILO_BET_LOW
  2, // 4. HILO_BET_LOW_EQUAL
  6, // 5. HILO_SKIP
  5, // 6. HILO_BET_EQUAL
]; // Adjust these probabilities as needed

// END OF USER VARIABLES
// DON'T EDIT BELOW

startBalance = balance;
highestBalance = startBalance;
lastVaultedProfit = profit;
startProfit = profit;

probabilitiesSum = probabilities.reduce((sum, cur) => sum + cur, 0); // compute sum so it won't be a problem if different than 100
probabilities.forEach((e, i) => {
  probabilities[i] = e / probabilitiesSum + (i ? probabilities[i - 1] : 0); // set probs to cumulative ones between 0 and 1
});

const decisions = {
  A: [
    HILO_BET_HIGH,
    HILO_BET_HIGH_EQUAL,
    HILO_BET_LOW,
    HILO_BET_LOW_EQUAL,
    HILO_SKIP,
    HILO_BET_EQUAL,
  ],
  J: [
    HILO_BET_HIGH,
    HILO_BET_HIGH_EQUAL,
    HILO_BET_LOW,
    HILO_BET_LOW_EQUAL,
    HILO_SKIP,
    HILO_BET_EQUAL,
  ],
  Q: [
    HILO_BET_HIGH,
    HILO_BET_HIGH_EQUAL,
    HILO_BET_LOW,
    HILO_BET_LOW_EQUAL,
    HILO_SKIP,
    HILO_BET_EQUAL,
  ],
  K: [
    HILO_BET_HIGH,
    HILO_BET_HIGH_EQUAL,
    HILO_BET_LOW,
    HILO_BET_LOW_EQUAL,
    HILO_SKIP,
    HILO_BET_EQUAL,
  ],
};

const decisionsNames = [
  HILO_BET_HIGH,
  HILO_BET_HIGH_EQUAL,
  HILO_BET_LOW,
  HILO_BET_LOW_EQUAL,
  HILO_SKIP,
  HILO_BET_EQUAL,
];

function calculations() {
  highestBalance = Math.max(balance, highestBalance);
}

function strategy() {
  if (lastBet.win) {
    betSize = initialBetSize;
  } else if (currentStreak % 2 === 0) {
    betSize = lastBet.amount * increaseOnLoss;
  }
}

function probability() {
  // Generate a random number between 0 and 1
  const random = Math.random();
  for (let i = 0; i < probabilities.length; i++) {
    if (random < probabilities[i]) {
      return i;
    }
  }
  return 0;
}

function console() {
  clearConsole();
  logBanner();
  log(
    "#47fa41",
    `starting Balance: ${startBalance.toFixed(6)}  ${currency} current balance: ${balance.toFixed(4)} ${currency} highest balance: ${highestBalance.toFixed(6)} ${currency} `,
  );
  log("-".repeat(100));
}

engine.onBetPlaced(async (lastBet) => {
  stopProfitCheck();
  await vaultHandle();

  calculations();
  // probability(); // need to place this in onGameRound
  strategy();
  console();

  stopLossCheck();
});

engine.onGameRound((currentBet) => {
  // Fetching current card rank, fallback to start card rank, because rounds is an empty array on first game round
  lastRound = currentBet.state.rounds.at(-1);
  currentCardRank =
    lastRound && lastRound.card
      ? lastRound.card.rank
      : currentBet.state.startCard.rank;
  payoutMultiplier = lastRound ? lastRound.payoutMultiplier : 0;
  skippedCards = currentBet.state.rounds.filter(
    (round) => round.action === "skip",
  ).length;

  if (payoutMultiplier >= cashOutAtMultiplier) {
    log(`Outcome: ${HILO_CASHOUT}`);
    return HILO_CASHOUT;
  }

  if (currentCardRank in decisions) {
    let decision = decisionsNames[probability()];
    if (
      decision === HILO_BET_EQUAL &&
      !["A", "K"].includes(currentCardRank) &&
      casino !== "STAKE"
    ) {
      decision = HILO_BET_HIGH;
    }
    log(`Outcome: ${decision}`);
    return decision;
  }

  if (parseInt(currentCardRank) < 7) {
    log(`Outcome: ${HILO_BET_LOW}`);
    return HILO_BET_LOW;
  }

  // You can only skip 52 cards in one Hilo bet!
  if (parseInt(currentCardRank) === 7 && skippedCards <= 52) {
    log(`Outcome: ${HILO_SKIP}`);
    return HILO_SKIP;
  }

  log(`Outcome: ${HILO_BET_HIGH}`);
  return HILO_BET_HIGH;
});

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
