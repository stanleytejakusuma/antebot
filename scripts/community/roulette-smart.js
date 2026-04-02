strategyTitle = "Smart Roulette";
author = "SmartWonga";
version = "2.1";
scripter = "ConnorMcLeod & Vrafasky";

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

//setup your seting here
numbersToPick = 2;
streakToCover = 135; // streak you gonna bust at

// Setup wagering mode
wageringMode = false;
wagerBetSize = balance / 20;

switchToWageringThreshold = 1; // in percent
backToGainingThreshold = 0.1;

// Seed Reset setup
seedChangeAfterRolls = 0;
seedChangeAfterWins = 0;
seedChangeAfterLosses = 0;
seedChangeAfterWinStreak = 0;
seedChangeAfterLossStreak = 0;
seedChangeOnMultiplier = 0;
stopOnResetSeedFailure = false;

//  Stop P/L & Vaulting  Setup
vaultProfitsThreshold = 0;
stopOnProfit = 0;
stopOnLoss = 0;

// MAIN SCRIPT  LOGIC
// DO NOT EDIT BELOW

game = "roulette";
asyncMode = false;
lookupBetIds = false;
startBalance = balance;

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

lastVaultedProfit = profit;
startProfit = profit;
vaulting = false;
agressivity = 0; // 0 to 100

rouletteNumbersKeys = [
  "number0",
  "number1",
  "number2",
  "number3",
  "number4",
  "number5",
  "number6",
  "number7",
  "number8",
  "number9",
  "number10",
  "number11",
  "number12",
  "number13",
  "number14",
  "number15",
  "number16",
  "number17",
  "number18",
  "number19",
  "number20",
  "number21",
  "number22",
  "number23",
  "number24",
  "number25",
  "number26",
  "number27",
  "number28",
  "number29",
  "number30",
  "number31",
  "number32",
  "number33",
  "number34",
  "number35",
  "number36",
];

iol = getRecoverIncreaseFromPayout(36 / numbersToPick, agressivity);
divider = Math.ceil(geometricSerieSum(iol, streakToCover));
initialBetSize = balance / divider;

function theLog() {
  logBanner();

  log(
    "#FF71A7",
    `CHOOSEN STRAT:
Picking : ${numbersToPick} Numbers || Target Payout: ${36 / numbersToPick}x || Wagering Mode?: ${wageringMode ? "Yes" : "No"}`,
  );

  log(
    "#8BE9FD",
    `BET SIZE AUTO-CALCULATED TO COVER : ${streakToCover} Max LS
==========
Base Bet Size : ${initialBetSize.toFixed(8)} ${currency.toUpperCase()}
Base Bet Size per Chip : ${initialBetSize.toFixed(8) / numbersToPick} ${currency.toUpperCase()}
`,
  );

  log(
    "#F1FA8C",
    `Our Max LS: ${ourHighestLS.join(" / ")}
Our Current Streaks: ${ourLS}`,
  );

  if (strategy == wagering) {
    log(
      "#50EE69",
      `CURRENT STATUS:
Wagering
`,
    );
  }

  if (strategy == mainStrategy)
    log(
      "#FF8A36",
      `CURRENT STATUS:
Betting On : \n${logArray.join("\n")}`,
    );
}

selection = {};
if (
  initialBetSize < 0.000001 / getConversionRate() ||
  initialBetSize / numbersToPick < 1e-10
) {
  log("#c80815", "Balance too low, or max streak too high for those settings");
} else {
  for (let i = 0; i < numbersToPick; i++) {
    selection[rouletteNumbersKeys[i]] = initialBetSize / numbersToPick;
  }
}

lastHits = Array(37);
firstNonce = -1;
lastNonce = -1;
logArray = [];

wageringBetsCount = 0;
ourLS = 0;
ourHighestLS = [0, 0, 0, 0, 0, 0, 0, 0];

engine.onBetPlaced((lastBet) => {
  checkStopProfit();
  checkVaultAllProfits();
  checkResetSeed();

  nonce = lastBet.nonce;
  result = lastBet.state.result;
  if (firstNonce === -1) {
    firstNonce = nonce - 1;
    lastNonce = firstNonce;
    lastHits.fill(firstNonce);
  }
  lastHits[result] = Math.max(nonce, lastHits[result]);
  if (nonce - lastNonce !== 1) {
    log("#c80815", "Missing nonce, resetting streaks");
    firstNonce = nonce - 1;
    lastHits.forEach((e, i) => (lastHits[i] = Math.max(firstNonce, e)));
  }
  lastNonce = Math.max(nonce, lastNonce);

  strategy();

  clearConsole();
  theLog();

  checkStopLoss();
});

mainStrategy = () => {
  if (lastBet.win) {
    if (
      wageringMode &&
      profit >= (switchToWageringThreshold / 100) * startBalance
    ) {
      initWagering();
      strategy = wagering;
    } else {
      pickNewNumbers();
    }

    if (ourLS > Math.min(...ourHighestLS)) {
      ourHighestLS.push(ourLS);
      ourHighestLS.sort((a, b) => a - b).splice(0, 1);
    }
    ourLS = 0;
  } else {
    betSize = lastBet.amount * iol;
    Object.keys(selection).forEach(
      (key) => (selection[key] = betSize / numbersToPick),
    );
    ourLS++;
  }
};
strategy = mainStrategy;

wagering = () => {
  if (profit <= (backToGainingThreshold / 100) * startBalance) {
    pickNewNumbers();
    strategy = mainStrategy;
  }
};

function initWagering() {
  wageringBetsCount = 0;

  rouletteNumbersKeys.forEach(
    (e) => (selection[e] = wagerBetSize / rouletteNumbersKeys.length),
  );
}

function pickNewNumbers() {
  copyHits = lastHits
    .map((e, i) => [i, e])
    .sort((a, b) => a[1] - b[1])
    .splice(0, numbersToPick);
  selection = {};
  logArray = [];
  copyHits.forEach((e) => {
    index = e[0];
    logArray.push(`Number ${index} - Streak ${nonce - e[1]}`);
    selection[rouletteNumbersKeys[index]] = initialBetSize / numbersToPick;
  });
}

function getRecoverIncreaseFromPayout(payout, agressivity = 0) {
  multiplier = 1 / (payout - 1) + 1;
  multiplier += ((multiplier - 1) * agressivity) / 100;
  return multiplier;
}

function geometricSerieSum(q, n, a = 1) {
  return (a * (1 - Math.pow(q, n))) / (1 - q);
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

function checkStopProfit() {
  if (stopOnProfit && profit >= stopOnProfit) {
    log(
      `Made ${profit.dynFixed()} ${currency} profit / ${profit.toFiatString()}`,
    );
    engine.stop();
  }
}

function checkStopLoss() {
  sizeBet = getBetSize();
  if (stopOnLoss && profit - sizeBet <= -stopOnLoss) {
    log(
      `Lost ${(-profit).dynFixed()} ${currency} / ${(-profit).toFiatString()}`,
    );
    engine.stop();
  }
}

function getBetSize() {
  if (game === "baccarat") {
    return bankerBetSize + playerBetSize + tieBetSize;
  } else if (game === "roulette") {
    return Object.values(selection).reduce((sum, e) => sum + e, 0);
  }
  return betSize;
}

function checkVaultAllProfits() {
  if (
    !vaulting &&
    vaultProfitsThreshold > 0 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    let vaultingAmount = profit - lastVaultedProfit;
    vaulting = true;
    depositToVault(vaultingAmount)
      .then((response) => {
        log(
          `Vaulting ${vaultingAmount.dynFixed()} ${currency} / ${vaultingAmount.toFiatString()}`,
        );
        lastVaultedProfit = profit;
      })
      .catch((response) => {
        // log( typeof response, response, response[0].message );
        log(response[0].message);
      })
      .finally(() => {
        vaulting = false;
      });
  }
}

const resetseed = () => {
  // 'Finish existing games to change seed'
  // 'Please try again in an hour. '
  // 'Please try again in 39 minutes. '
  resetSeed()
    .then((response) => {})
    .catch((response) => {
      if (response[0].message.includes("Please try again in")) {
        if (response[0].message.includes("hour")) {
          log("#ee3a1f", "Can't change seed before 1 hour");
        } else {
          minutes = response[0].message.match(/\d+/)[0];
          log("#ee3a1f", `Can't change seed before ${minutes} minutes`);
        }
      } else {
        log("#ee3a1f", response[0].message);
      }
      if (stopOnResetSeedFailure) {
        stop();
      }
    })
    .finally(() => {
      resettingSeed = false;
      lastHits = Array(37);
      firstNonce = -1;
      lastNonce = -1;
      logArray = [];
    });
};

function checkResetSeed() {
  if (seedChangeAfterRolls && rollNumber % seedChangeAfterRolls === 0) {
    resetseed();
  } else if (lastBet.win) {
    if (seedChangeAfterWins && wins % seedChangeAfterWins === 0) {
      resetseed();
    } else if (
      seedChangeAfterWinStreak &&
      currentStreak % seedChangeAfterWinStreak === 0
    ) {
      resetseed();
    } else if (
      seedChangeOnMultiplier &&
      lastBet.payoutMultiplier >= seedChangeOnMultiplier
    ) {
      resetseed();
    }
  } else {
    if (seedChangeAfterLosses && losses % seedChangeAfterLosses === 0) {
      resetseed();
    } else if (
      seedChangeAfterLossStreak &&
      currentStreak % seedChangeAfterLossStreak === 0
    ) {
      resetseed();
    }
  }
}
