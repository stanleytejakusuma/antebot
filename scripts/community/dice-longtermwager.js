strategyTitle = "Longterm Dice Wager";
version = "3.2";
author = "SatoshiMaster";
scripter = "SatoshiMaster";

game = "dice";

//---------------------------------------------------------------
// do not Change anything above this line
target = 10; // set the target you want to play. i would take 10 or above. if you take high target you also should increasing chased multi to increase not to fast.
betHigh = true; // bet hight or low

divider = 50000; // i recommand at least 10k, better more.
chasedMulti = 1000; // i recommend at least 300. i prefere more. If you go less you will need higher divider.
recalculateOnBalance = false; // true or false. recalculate initialBetSize to the new balance

seedOnChasedRTP = false; // true or false. change Seed when chasedRTP is reached.
resetOnChasedRTP = false; // true or false. reset Stats when chasedRTP is reached.
stopOnChasedRTP = false; // true or false. stop script when chasedRTP reached.
chasedRTP = 99.66; // i recommend between 99.5 till 99.80. Not testet higher till yet with my setup.

onlyIncreaseOnLowRTP = true; // true or false. Will only go in increasing mode when RTP is below this RTP.
downChasedRTP = 99.0; // Will only go in increasing mode when RTP is below this RTP.

seedOnProfit = false; // true or false. change Seed when stopProfit is reached.
resetOnProft = false; // true or false. reset Stats when Stop on Profit reached
stopOnProfit = false; // stop the script when chasedRTP is reached
stopProfit = 0.00000001; // in cryptocurrncie

stopOnLoss = true; // // stop the script when stopLoss or trailingStopLoss is reached
stopLoss = 999; // stopLoss in cryptocurrncie not fiat
trailingStopLoss = 9999; // trailingStopLoss in cryptocurrncie that will only stop if your loss is bigger than the allowed loss based on chased rtp

hightWager = true; // true or false. Use lower divider while rtp > hightWagerRTP result in faster wager or bigger profit
hightWagerRTP = 99.66; // set your rtp for start highwager. should be >= chasedRTP
chasedHighWagerRTP = 100; // set your target like a stopProfit in hightWager Mode. you will go back to normal lower initialBetSize, when you reach this RTP
hightWagerDivider = 25000; // Divider while RTP > hightWagerRTP if hightWager = true
asyncMode = true; // can have delayed actions with asyncMode in combination with optional functions
// do not change anything under this line
//---------------------------------------------------------------
// Simulation Setup
if (isSimulationMode) {
  setSimulationBalance(parseFloat(divider));
  resetSeed();
  resetStats();
  clearConsole();
}
initialInitialBetSize = balance / divider;
hightWagerInitialInitialBetSize = balance / hightWagerDivider;
initialBetSize = initialInitialBetSize;
betSize = initialBetSize;
chasedHouseEdge = 1 - chasedRTP / 100;
downChasedHouseEdge = 1 - downChasedRTP / 100;
dontGoOverStopLoss = true;
stage = false;
highWagerStage = false;
stop = false;

logBanner();
engine.onBetPlaced(async (lastBet) => {
  allowedLoss = wagered * chasedHouseEdge;
  downAllowedLoss = wagered * downChasedHouseEdge;

  if (rtp > chasedRTP) {
    initialBetSize = initialInitialBetSize;
    betSize = initialBetSize;

    if (stage) {
      log(
        `[${new Date().toLocaleString("en-US", { timeZone: "Europe/Berlin" })}] In Germany`,
      );
      log("chasedRTP reached. Results of this Run:");
      log(`Wager: ${wagered}`);
      log(`RTP: ${rtp}`);
      log(`Highest: ${highestProfit}`);
      log(`Lowest: ${lowestProfit}`);
      log(`Profit: ${profit}`);
      stage = false;

      if (resetOnChasedRTP) {
        resetStats();
      }

      if (seedOnChasedRTP) {
        await resetSeed();
      }

      if (recalculateOnBalance) {
        initialInitialBetSize = balance / divider;
        initialBetSize = initialInitialBetSize;
        betSize = initialBetSize;
      }

      if (stopOnChasedRTP) {
        stop = true;
        engine.stop();
      }
    }
  }

  if (hightWager & (rtp > hightWagerRTP)) {
    initialBetSize = hightWagerInitialInitialBetSize;
    betSize = initialBetSize;
    highWagerStage = true;
  }

  if (hightWager & highWagerStage & (rtp > chasedHighWagerRTP)) {
    initialBetSize = initialInitialBetSize;
    betSize = initialBetSize;
    highWagerStage = false;
  }

  if (hightWager & highWagerStage & (rtp < hightWagerRTP)) {
    initialBetSize = initialInitialBetSize;
    betSize = initialBetSize;
    highWagerStage = false;
  }

  if (!onlyIncreaseOnLowRTP & (-profit > chasedMulti * betSize + allowedLoss)) {
    initialBetSize = initialInitialBetSize;
    betSize += initialBetSize;
    stage = true;
  }

  if (
    onlyIncreaseOnLowRTP &
    (-profit > chasedMulti * betSize + downAllowedLoss)
  ) {
    initialBetSize = initialInitialBetSize;
    betSize += initialBetSize;
    stage = true;
  }

  if (seedOnProfit | resetOnProft | stopOnProfit) {
    if (profit > stopProfit) {
      log(
        `[${new Date().toLocaleString("en-US", { timeZone: "Europe/Berlin" })}] In Germany`,
      );
      log("stopProfit reached. Results of this Run:");
      log(`Wager: ${wagered}`);
      log(`RTP: ${rtp}`);
      log(`Highest: ${highestProfit}`);
      log(`Lowest: ${lowestProfit}`);
      log(`Profit: ${profit}`);

      if (resetOnProft & (profit > stopProfit)) {
        resetStats();
      }

      if (seedOnProfit) {
        await resetSeed();
      }

      if (recalculateOnBalance) {
        initialInitialBetSize = balance / divider;
        initialBetSize = initialInitialBetSize;
        betSize = initialBetSize;
      }

      if (stopOnProfit) {
        stop = true;
        engine.stop();
      }
    }
  }

  if (stopOnLoss) {
    if (-profit + betSize > stopLoss) {
      log(
        `[${new Date().toLocaleString("en-US", { timeZone: "Europe/Berlin" })}] In Germany`,
      );
      log("stopLoss reached. Results of this Run:");
      log(`Wager: ${wagered}`);
      log(`RTP: ${rtp}`);
      log(`Highest: ${highestProfit}`);
      log(`Lowest: ${lowestProfit}`);
      log(`Profit: ${profit}`);
      stop = true;
      engine.stop();
    }

    if (-profit > trailingStopLoss + allowedLoss) {
      log(
        `[${new Date().toLocaleString("en-US", { timeZone: "Europe/Berlin" })}] In Germany`,
      );
      log("trailingStopLoss reached. Results of this Run:");
      log(`Wager: ${wagered}`);
      log(`RTP: ${rtp}`);
      log(`Highest: ${highestProfit}`);
      log(`Lowest: ${lowestProfit}`);
      log(`Profit: ${profit}`);
      stop = true;
      engine.stop();
    }
  }
});

engine.onBettingStopped((isManualStop) => {
  if (!isManualStop) {
    if (!stop) {
      engine.start();
    }
  }
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