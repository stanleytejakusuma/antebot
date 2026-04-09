// Simulation Setup
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}
strategyTitle = "The Hurt Locker";
author = "Deko Night";

// Is async mode supported on this script ? NO

divider = 1000000;
includeLastRollsInHeatmap = 40;

settings = [
  {
    mines: 3,
    hotNumbers: 12,
    middleNumbers: 0,
    coldNumbers: 0,
    increaseOnLoss: 17,
    maxStreak: 18,
    additionalIncreaseBeforeSwitch: 23,
  },
  {
    mines: 5,
    hotNumbers: 0,
    middleNumbers: 7,
    coldNumbers: 0,
    increaseOnLoss: 25,
    maxStreak: 13,
    additionalIncreaseBeforeSwitch: 36,
  },
  {
    mines: 8,
    hotNumbers: 0,
    middleNumbers: 0,
    coldNumbers: 4,
    increaseOnLoss: 29,
    maxStreak: 9,
    additionalIncreaseBeforeSwitch: -58,
  },
];

seedChangeAfterRolls = 0;
seedChangeAfterWins = 0;
seedChangeAfterLosses = 0;
seedChangeAfterWinStreak = 0;
seedChangeAfterLossStreak = 0;
seedChangeOnMultiplier = 0;
stopOnResetSeedFailure = false;

vaultProfitsThreshold = 0;
stopOnProfit = 0;
stopOnLoss = 0; // this one can't be reached, will stop if next bet can go over the loss
stopOnReachedLoss = 0; // will only stop if reached (if async mode is false)

// END OF EDITION ZONE
// DO NOT EDIT BELOW
asyncMode = false;
lookupBetIds = false;
initialBetSize = balance / divider;
game = "mines";
betSize = initialBetSize;
mines = 1; // 1-24
fields = [0];

maxStreak = 0;
settings.forEach((e, i) => {
  settings[i].iol = 1 + e.increaseOnLoss / 100;
  settings[i].xtraIol = 1 + e.additionalIncreaseBeforeSwitch / 100;
  settings[i].maxStreak += maxStreak;
  maxStreak = settings[i].maxStreak;
});

version = "1.0";
scripter = "ConnorMcLeod";

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

settingsIndex = 0;

hotNumbers = 1;
middleNumbers = 1;
coldNumbers = 2;

heatmap = {};
for (let i = 0; i <= 24; i++) {
  heatmap[i] = [];
}

function cleanUpOldRollsData(heatmap) {
  for (const heatmapIndex in heatmap) {
    heatmap[heatmapIndex] = heatmap[heatmapIndex].filter(
      (rn) => rollNumber - rn <= includeLastRollsInHeatmap,
    );
  }

  return heatmap;
}

function getHeatmapFields() {
  const fields = [];

  if (hotNumbers > 0) {
    fields.push(...getHotNumbers(hotNumbers));
  }

  if (middleNumbers > 0) {
    fields.push(...getMiddleNumbers(middleNumbers));
  }

  if (coldNumbers > 0) {
    fields.push(...getColdNumbers(coldNumbers));
  }

  return fields;
}

function getHotNumbers(amount) {
  return Object.entries(heatmap)
    .sort((a, b) => a[1].length - b[1].length)
    .slice(-amount)
    .map((value) => parseInt(value[0]));
}

function getMiddleNumbers(amount) {
  const entries = Object.entries(heatmap),
    middle = Math.round(entries.length / 2),
    sliceStart = middle - Math.floor(amount / 2),
    sliceEnd = sliceStart + amount;

  return entries
    .sort((a, b) => a[1].length - b[1].length)
    .slice(sliceStart, sliceEnd)
    .map((value) => parseInt(value[0]));
}

function getColdNumbers(amount) {
  return Object.entries(heatmap)
    .sort((a, b) => a[1].length - b[1].length)
    .slice(0, amount)
    .map((value) => parseInt(value[0]));
}

function randomFields(amount) {
  // Create array with a number range from 0 to 24
  const fields = Array.from(Array(25).keys());

  return shuffle(fields).slice(0, amount);
}

function updateHeatMap() {
  for (const heatmapIndex in heatmap) {
    // for mines only
    if (!lastBet.state.mines.includes(parseInt(heatmapIndex))) {
      heatmap[heatmapIndex].push(rollNumber);
    }
  }
  heatmap = cleanUpOldRollsData(heatmap);
}

setting = {};

function pickSettings() {
  setting = settings[settingsIndex % settings.length];
  mines = setting.mines;

  hotNumbers = setting.hotNumbers;
  middleNumbers = setting.middleNumbers;
  coldNumbers = setting.coldNumbers;
}

pickSettings();
fields = randomFields(hotNumbers + middleNumbers + coldNumbers);
ourCurrentStreak = 0;

function strategy() {
  if (lastBet.win) {
    betSize = initialBetSize;
    ourCurrentStreak = 0;
    settingsIndex = 0;
    pickSettings();
  } else {
    ourCurrentStreak--;
    betSize = lastBet.amount * setting.iol;
    if (-ourCurrentStreak === setting.maxStreak) {
      betSize *= setting.xtraIol;
      if (++settingsIndex >= settings.length) {
        settingsIndex = 0;
        ourCurrentStreak = 0;
      }
      pickSettings();
    }
  }
}
logBanner();
engine.onBetPlaced(async (lastBet) => {
  checkStopProfit();
  await checkVaultAllProfits();
  checkResetSeed();

  updateHeatMap();
  strategy();
  fields = getHeatmapFields();

  checkStopLoss();
});

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
  if (stopOnReachedLoss !== 0 && profit < -Math.abs(stopOnReachedLoss)) {
    log(
      `Lost ${(-profit).dynFixed()} ${currency} / ${(-profit).toFiatString()}`,
    );
    engine.stop();
  }
  sizeBet = getBetSize();
  if (stopOnLoss !== 0 && profit - sizeBet <= -Math.abs(stopOnLoss)) {
    log(
      `Stopped to prevent a ${(-(profit - sizeBet)).dynFixed()} ${currency} / ${(-(profit - sizeBet)).toFiatString()} loss`,
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

async function checkVaultAllProfits() {
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
        engine.stop();
      }
    })
    .finally(() => {
      resettingSeed = false;
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
