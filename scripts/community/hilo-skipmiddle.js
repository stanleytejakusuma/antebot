strategyTitle = "Hilo Skip Middle";
author = "vb033";
version = "1.0";
scripter = "Vrafasky";

game = "hilo";

// User Settings
divider = 20000; //balance divider to set base bet size
increaseOnLossPercent = 100; // Increase bet size by this percent on loss
skipBetOnLossStreak = 2; // Skip bet and use min bet size if loss streak is equal or greater than this value
cashoutMultiplier = 2.0; //cashout when this multiplier is reached

// Vaulting & Stop P/L Setup. Set 0 to disable
vaultProfitsThreshold = 0; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(Number(divider));
  resetSeed();
  resetStats();
  clearConsole();
}

// DO NOT EDIT BELOW THIS LINE
baseBet = balance / divider; //base bet size
betSize = initialBetSize = baseBet; // Initial bet size
//vault init
lastVaultedProfit = profit;
startProfit = profit;

// Initial startCard
startCard = { rank: "A", suit: "C" };

logBanner();
engine.onBetPlaced(async (lastBet) => {
  stopProfitCheck();
  await vaultHandle();

  if (lastBet.win) {
    if (lastBet.amount > minBetSize) {
      baseBet = initialBetSize;
    } else {
      baseBet *= 1 + increaseOnLossPercent / 100;
    }
    betSize = baseBet;
  } else {
    if (currentStreak > -skipBetOnLossStreak) {
      baseBet *= 1 + increaseOnLossPercent / 100;
      betSize = baseBet;
    } else {
      betSize = minBetSize;
    }
  }
  stopLossCheck();
});

engine.onGameRound((currentBet) => {
  // Fetching current card rank, fallback to start card rank, because rounds is an empty array on first game round
  lastRound = currentBet.state.rounds.at(-1);
  currentCardRank =
    lastRound && lastRound.card
      ? lastRound.card.rank
      : currentBet.state.startCard.rank;
  //fetch current round payout multiplier
  currentPayoutMultiplier = lastRound ? lastRound.payoutMultiplier : 0;
  skippedCards = currentBet.state.rounds.filter(
    (round) => round.action === "skip",
  ).length;

  // CASHOUT LOGIC
  if (currentPayoutMultiplier >= cashoutMultiplier || skippedCards == 52) {
    return HILO_CASHOUT;
  }
  if (["J", "Q", "K"].includes(currentCardRank)) {
    return HILO_BET_LOW;
  } else if (["A", "2", "3"].includes(currentCardRank)) {
    return HILO_BET_HIGH;
  } else if (["4", "5", "6", "7", "8", "9", "10"].includes(currentCardRank)) {
    return HILO_SKIP;
  }
});

Number.prototype.dynFixed = function () {
  return this.toFixed(Math.max(-Math.floor(Math.log10(this)), 0) + 2);
};

Number.prototype.toFiatString = function () {
  return (this / getConversionRate(currency, fiatCurrency)).toLocaleString(0, {
    style: "currency",
    currency: fiatCurrency,
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
      `${messagePrefix} ${amount.dynFixed()} ${currency.toUpperCase()} / ${amount.toFiatString()} ${fiatCurrency} ${conditionMessage}`,
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

function getBetSize() {
  if (game === "baccarat") {
    return bankerBetSize + playerBetSize + tieBetSize;
  } else if (game === "roulette") {
    return Object.values(selection).reduce((sum, e) => sum + e, 0);
  }
  return betSize;
}

function stopLossCheck() {
  potentialLoss = -(profit - getBetSize);

  checkStopWithLog(
    stopOnLoss !== 0 && profit < -Math.abs(stopOnLoss),
    "#FFFF2A",
    "⛔️ Stopped on loss of",
    -profit,
    "Loss",
  );
  checkStopWithLog(
    stopBeforeLoss !== 0 && profit - getBetSize() <= -Math.abs(stopBeforeLoss),
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
