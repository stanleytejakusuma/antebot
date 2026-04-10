strategyTitle = 'SurgeWager';
author = 'macvault';
version = '1.0';
scripter = 'Vrafasky';

// USER SETTINGS

// WAGER PHASE SETTING
wagerDivider = 100 // balance divider to set base bet size for the wager phase
wagerTarget = 1.0102; // target multiplier for the wager phase

increaseOnWinPercent = 15; // percentage to increase the bet size on win during the wager phase
resetOnWinStreak = 5; // reset bet size to base bet after this many consecutive wins during the wager phase

switchOverUnderEveryBets = 51; // switch between over and under bet every X bets, set to 0 to disable

switchToRecoverOnSessionLossPercent = 2.5; // switch to recovery phase when session loss reach this percentage of the balance

// RECOVERY PHASE SETTING
recoverTarget = 2.2; // target multiplier for the recovery phase
recoverDivider = 5000; // balance divider to set base bet size for the recovery phase
increaseOnLossPercent = 88; // percentage to increase the bet size on loss during the recovery phase



// DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU ARE DOING

game = "dice";
betHigh = true

divider = wagerDivider
    // Simulation Setup
if (isSimulationMode) {
    setSimulationBalance(100);
    resetSeed();
    resetStats();
    clearConsole();
}

wagerBaseBet = balance / wagerDivider
recoverBaseBet = balance / recoverDivider;

betSize = wagerBaseBet
target = wagerTarget

phase = 1
sessionProfit = 0
startBalance = balance;


engine.onBetPlaced(async(lastBet) => {

    sessionProfit += (lastBet.payout - lastBet.amount);

    if (phase == 1) {
        if (lastBet.win) {
            betSize *= (1 + increaseOnWinPercent / 100)
            if (currentStreak % resetOnWinStreak == 0) {
                betSize = wagerBaseBet
            }
        } else {
            betSize = wagerBaseBet
            if (sessionProfit <= -(switchToRecoverOnSessionLossPercent / 100 * startBalance)) {
                phase = 2;
                target = recoverTarget;
                betSize = recoverBaseBet
            }
        }

        if (switchOverUnderEveryBets && rollNumber % switchOverUnderEveryBets == 0) {
            betHigh = !betHigh
        }
    }
    if (phase == 2) {
        if (lastBet.win) {
            betSize = recoverBaseBet
            if (sessionProfit >= 0) {
                phase = 1;
                betSize = wagerBaseBet
                target = wagerTarget;
            }
        } else {
            if (lastBet.state.multiplierTarget != wagerTarget) {
                betSize *= (1 + increaseOnLossPercent / 100)
            }
        }
    }


    clearConsole();

    logBanner();

});





function logBanner() {
    log('#80EE51', `================================
${strategyTitle} v${version} by ${author} 
================================
Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`);
}