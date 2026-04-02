strategyTitle = "Wheel ATH B2B Low";
author = "Q";
version = "1.1";
scripter = "Q";

game = "wheel";
risk = "low";
segments = 50;

// Bet Size Settings
balanceDivider = 10000;
betSize = balance / balanceDivider;

// Vaulting & Stop P/L Setup. Set 0 to disable, in crypto value
vaultProfitsThreshold = 0; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

// DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU ARE DOING

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

//vault init
lastVaultedProfit = profit;
startProfit = profit;

logBanner();

function checkVaultAllProfits() {
  if (
    vaultProfitsThreshold > 0 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    let vaultingAmount = profit - lastVaultedProfit;
    depositToVault(vaultingAmount);
    log(
      `Vaulting ${vaultingAmount.toFixed(Math.max(-Math.floor(Math.log10(vaultingAmount)), 0) + 2)} ${currency}`,
    );
    lastVaultedProfit = profit;
  }
}

engine.onBetPlaced(async (lastBet) => {
  stopProfitCheck();
  await vaultHandle();

  if (lastBet.win) {
    betSize = lastBet.payout;
  }

  if (profit >= highestProfit) {
    betSize = balance / balanceDivider;
  }

  stopLossCheck();
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
  potentialLoss = -(profit - getBetSize());

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