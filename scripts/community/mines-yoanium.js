strategyTitle = "yoanium_mines";
author = "yoa";
version = "1.1";
scripter = "yoa";

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

game = "mines";

mines = 5;
amount = 1;
fields = randomFields(amount);

divider = 10000;
initialBetSize = balance / divider;
betSize = initialBetSize;

// Vaulting & Stop P/L Setup. Set 0 to disable
vaultProfitsThreshold = 1; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

//DO NOT EDIT BELOW
//vault init
lastVaultedProfit = profit;
startProfit = profit;

engine.onBetPlaced(async (lastBet) => {
  stopProfitCheck();
  await vaultHandle();

  if (lastBet.win) {
    betSize = initialBetSize;
    mines = 5;
    amount = 1;
  } else if (-20 < currentStreak && currentStreak <= -1) {
    betSize = betSize * 3;
    mines = 5;
    amount = 2;
  }
  fields = randomFields(amount);

  stopLossCheck();
});

logBanner();

function randomFields(amount) {
  // Create array with a number range from 0 to 24
  const fields = Array.from(Array(25).keys());

  return shuffle(fields).slice(0, amount);
}

Number.prototype.dynFixed = function () {
  return this.toFixed(Math.max(-Math.floor(Math.log10(this)), 0) + 2);
};

Number.prototype.toFiatString = function () {
  return (this * getConversionRate()).toLocaleString(0, {
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
