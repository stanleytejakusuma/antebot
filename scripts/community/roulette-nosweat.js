strategyTitle = "No Sweat Roulette";
author = "BeggarsBeDamned";
version = "1.2";
scripter = "009";

if (isSimulationMode) {
  setSimulationBalance(100);
}
resetSeed();
resetStats();
clearConsole();

minBet = minBetSize; // xrp at shuffle
numberOfFails = 8;
divider = (balance - minBet) / minBet;

//or below divider calculation is based on the number of Fails
failTotal = 1;
for (var i = 0; i < numberOfFails; i++) {
  failTotal = failTotal * 4;
}
divider = failTotal;

betMultiplier = 63;
numberBet = 1 * betMultiplier;
rowBet = 12 * betMultiplier;

coinsOnChips = {
  number0: numberBet,
  number1: numberBet,
  number2: 0,
  number3: numberBet,
  number4: 0,
  number5: 0,
  number6: 0,
  number7: numberBet,
  number8: 0,
  number9: numberBet,
  number10: 0,
  number11: 0,
  number12: numberBet,
  number13: 0,
  number14: 0,
  number15: 0,
  number16: numberBet,
  number17: 0,
  number18: numberBet,
  number19: numberBet,
  number20: 0,
  number21: numberBet,
  number22: 0,
  number23: 0,
  number24: 0,
  number25: numberBet,
  number26: 0,
  number27: numberBet,
  number28: 0,
  number29: 0,
  number30: numberBet,
  number31: 0,
  number32: 0,
  number33: 0,
  number34: numberBet,
  number35: 0,
  number36: numberBet,
  row1: 0,
  row2: rowBet,
  row3: 0,
  colorRed: 0,
  colorBlack: 0,
  parityEven: 0,
  parityOdd: 0,
  range0112: 0,
  range1324: 0,
  range2536: 0,
  range0118: 0,
  range1936: 0,
};

increaseOnLoss = 300;

stopOnProfitPercentage = 50;
stopOnLossPercentage = 50;
dontGoOverStopLoss = true; // will only stop if reached

// Vaulting
vaultProfitsThreshold = 0; //vaulting amount

// END OF EDITION ZONE
// DO NOT EDIT BELOW
asyncMode = false;
lookupBetIds = false;
initialBetSize = GetBet();
game = "roulette";

stopLoss = (balance * stopOnLossPercentage) / 100;
stopProfit = (balance * stopOnProfitPercentage) / 100;

totalCoins = Object.values(coinsOnChips).reduce((a, b) => a + b);

selection = {};

for (const [chip, coins] of Object.entries(coinsOnChips)) {
  if (coins) {
    selection[chip] = (initialBetSize * coins) / totalCoins;
  } else {
    delete coinsOnChips[chip];
  }
}

//vault init
lastVaultedProfit = profit;
startProfit = profit;

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
logBanner();
engine.onBetPlaced(async (lastBet) => {
  await vaultHandle();

  if (lastBet.win) {
    if (profit >= highestProfit) {
      if (stopProfit && profit >= stopProfit) {
        playHitSound();
        log("Profit made, stopping");
        engine.stop();
      }
      stopLoss = (balance * stopOnLossPercentage) / 100;
      initialBetSize = GetBet();
    }
    betSize = GetBet();
  } else {
    betSize = lastBet.amount * (1 + increaseOnLoss / 100);
  }

  if (stopLoss) {
    lostAmount = highestProfit - profit;
    if (dontGoOverStopLoss) {
      lostAmount += betSize;
    }
    if (lostAmount >= stopLoss) {
      log("Stop loss reached");
      engine.stop();
    }
  }

  for (const [chip, coins] of Object.entries(coinsOnChips)) {
    selection[chip] = (betSize * coins) / totalCoins;
  }
});

function GetBet() {
  firstBetSize = (balance - minBet) / divider;
  betSize = Math.max(firstBetSize, minBet);
  return betSize;
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
