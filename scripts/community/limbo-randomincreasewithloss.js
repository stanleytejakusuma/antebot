strategyTitle = "JarRandomLimboWithIncrease";
author = "J";
version = "Finale Version";
scripter = "J";

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

divider = 1000000;
initialBetSize = balance / divider;
target = 1000;
initialTarget = target;
asyncMode = true;
betSize = initialBetSize;

game = "limbo";

earlyNonceLogMinMulti = 100;
earlyNonceMaxNonce = 200000; // nonce where we stop logging multi > 150

nonceLogMinMulti = 1000;
nonceMaxNonce = 200000; // nonce where we stop logging multi > 1000

seedChangeDelay = 36000; // 36sec
asyncModeSafeSeedChange = 10;

nextSeedChangeTime = performance.now() + seedChangeDelay;
seedCount = 1;
lastThousandHit = 0;

function logBanner() {
  log(
    "#80EE51",
    `================================
🎯${strategyTitle}
💡 Created by ${author}
⌨️ Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`,
  );
}
logBanner();

colors = {
  earlyMultis: ["#FEFEFE", "#FEFEFE"], // blanc
  minMultis: ["#F5F509", "#F5F509"], // jaune
  wins: ["#09F509", "#09F509"], // vert1, vert2
};

function randomInteger(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

engine.onBetPlaced((lastBet) => {
  const targetChance = Math.random();
  if (targetChance < 0.05) {
    target = randomInteger(36666, 999999);
  } else if (targetChance < 0.1) {
    target = randomInteger(6666, 66666);
  } else if (targetChance < 0.2) {
    target = randomInteger(9666, 20000);
  } else if (targetChance < 0.3) {
    target = randomInteger(1600, 3506);
  } else if (targetChance < 0.4) {
    target = randomInteger(1000, 1900);
  } else if (targetChance < 0.6) {
    target = randomInteger(1000, 1250);
  } else {
    target = randomInteger(1000, 1100);
  }

  if (lastBet.win) {
    log(
      colors.wins[seedCount % 2],
      `#${lastBet.nonce} T x${lastBet.state.multiplierTarget}  M x${lastBet.state.result.toFixed(2)} P ${lastBet.fiatPayout}`,
    );
    betSize = initialBetSize;
  } else {
    if (lastBet.state.result > nonceLogMinMulti) {
      lastThousandHit = lastBet.nonce;
      log(
        colors.minMultis[seedCount % 2],
        `#${lastBet.nonce} T x${lastBet.state.multiplierTarget}  M x${lastBet.state.result.toFixed(2)}`,
      );
    } else if (
      lastBet.state.result > earlyNonceLogMinMulti &&
      lastBet.nonce < earlyNonceMaxNonce
    ) {
      log(
        colors.earlyMultis[seedCount % 2],
        `#${lastBet.nonce} T x${lastBet.state.multiplierTarget}  M x${lastBet.state.result.toFixed(2)}`,
      );
    } else if (
      currentStreak == -800 ||
      (currentStreak < -800 && currentStreak % 550 == 0)
    ) {
      betSize *= 2;
    } else if (currentStreak == -5502) {
      betSize = initialBetSize;
    }
  }

  asyncMode =
    lastBet.nonce - lastThousandHit < nonceMaxNonce - asyncModeSafeSeedChange;

  if (lastBet.nonce - lastThousandHit > nonceMaxNonce) {
    theTime = performance.now();
    if (theTime > nextSeedChangeTime) {
      nextSeedChangeTime = theTime + seedChangeDelay;
      //resetSeed();
      seedCount++;
      lastThousandHit = 0;
    }
  }
});
