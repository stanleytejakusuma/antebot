strategyTitle = 'The RollingStint';
version = '1.2.2';
author = 'Vrafasky';
scripter = 'Vrafasky'

// Initial Game setup
game = "limbo"
startBalance = balance;

// USER SETUP HERE
target = 5; // our multi target
stint = 10; // this is the number of roll  we hunt with real bet before skipping to minimum bet size until the next hit

preroll = 10 // number of LS to preroll before starting the stint.
prerollBetSize = minBetSize // bet size during the preroll / after stint. default to casino's min bet size. But you could put 0 for stake/pd.

coveredStreak = 35; // this is how many loss streak during real bet stint that you want to cover. It will autocalculate the starting betSize and divider.


// Vaulting & Stop P/L Setup. Set 0 to disable
vaultProfitsThreshold = 0; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

// Seed Reset Configuration
resetSeedAfterRolls = 0;
resetSeedAfterWins = 0;



// DO NOT EDIT BELOW THIS LINE
iol = calcIncrease(target)

if (coveredStreak > 0) {
    divider = Math.ceil(calcDivider(iol, coveredStreak));
}


// Simulation Setup
if (isSimulationMode) {
    setSimulationBalance(100);
    resetSeed();
    resetStats();
    clearConsole();
}


initialBetSize = startBalance / divider;
nextBet = initialBetSize

betSize = prerollBetSize;

rollingStreak = 0
ourStreak = 0
longestAS = [0, 0, 0, 0, 0, 0, 0, 0]



//vault init
lastVaultedProfit = profit;
startProfit = profit;

engine.onBetPlaced(async(lastBet) => {

    scriptLog();
    stopProfitCheck();
    await vaultHandle();
    seedResetCheck();

    mainStrategy();


    stopLossCheck();
});


function mainStrategy() {

    if (lastBet.win) {
        ourStreak = 0

        if (rollingStreak !== 0) {
            betSize = nextBet

        }



        if (lastBet.amount == prerollBetSize.toFixed(8)) {
            betSize = prerollBetSize.toFixed(8);
        } else {
            if (rollingStreak > Math.min(...longestAS)) {
                longestAS.push(rollingStreak);
                longestAS.sort((a, b) => b - a).splice(longestAS.length - 1, 1);
            }
            rollingStreak = 0;
            nextBet = initialBetSize
            betSize = prerollBetSize.toFixed(8);

        }
    } else {
        --ourStreak

        if (ourStreak <= -preroll && ourStreak > -stint - preroll) {
            betSize = nextBet
            nextBet *= iol
            rollingStreak++;
        }

        if (ourStreak <= -stint - preroll) {
            betSize = prerollBetSize.toFixed(8)
        }
    }


}


function scriptLog() {
    clearConsole()
    logBanner();
    log('#42CAF7', `🎯 Our Longest Covered Streaks :
   ${longestAS.join(' / ')}`);


}

// Functions for auto calculating betSize/divider

function calcSum(r, t, s = 1) {
    return s * (1 - Math.pow(r, t)) / (1 - r);
}

function calcIncrease(payout) {
    multi = 1 / (payout - 1) + 1;
    return multi;
}

function calcDivider(iol, maxStreak) {
    return calcSum(iol, maxStreak) + 1; // + 1 to get rid of balance rounding
}



// Utilities Functions

function logBanner() {
    log('#FFFF2A', `             ================================
               🎢 ${strategyTitle} v${version}  🎢
             ================================
        Created by ${author} for Antebot Originals
        -------------------------------------------
`);
}


Number.prototype.dynFixed = function() {
    return this.toFixed(Math.max(-Math.floor(Math.log10(this)), 0) + 2);
};

Number.prototype.toFiatString = function() {
    return (this * getConversionRate()).toLocaleString(0, {
        style: "currency",
        currency: fiatCurrency,
    });
};

function checkStopWithLog(condition, color, messagePrefix, amount, conditionMessage = '') {
    if (condition) {
        log(color, `${messagePrefix} ${amount.dynFixed()} ${currency.toUpperCase()} / ${amount.toFiatString()} ${conditionMessage}`);
        engine.stop();
    }
}

function stopProfitCheck() {
    checkStopWithLog(stopOnProfit && profit >= stopOnProfit, '#4FFB4F', '✅ Stopped on', profit, 'Profit');
}

function stopLossCheck() {
    potentialLoss = -(profit - betSize);

    checkStopWithLog(stopOnLoss !== 0 && profit < -Math.abs(stopOnLoss), '#FFFF2A', '⛔️ Stopped on loss of', -profit, 'Loss');
    checkStopWithLog(stopBeforeLoss !== 0 && profit - betSize <= -Math.abs(stopBeforeLoss), '#FFFF2A', '⛔️ Stopped to prevent a', potentialLoss, 'Loss');
}

async function vaultHandle() {
    if (vaultProfitsThreshold > 0 && profit - lastVaultedProfit >= vaultProfitsThreshold) {
        let vaultingAmount = profit - lastVaultedProfit;
        await depositToVault(vaultingAmount);
        log(`Vaulting ${(vaultingAmount).toFixed(Math.max( -Math.floor(Math.log10(vaultingAmount)), 0 ) + 2)} ${currency}`);
        lastVaultedProfit = profit;
    }
}


function seedResetCheck() {
    if (resetSeedAfterRolls && rollNumber % resetSeedAfterRolls === 0) {
        resetSeed();
    } else if (lastBet.win && resetSeedAfterWins && wins % resetSeedAfterWins === 0) {
        resetSeed();
    }
}