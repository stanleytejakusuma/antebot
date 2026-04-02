# General

> Source: https://forum.antebot.com/t/general/300

# General
All programming is done in JavaScript. You’re allowed to use all the features, which JavaScript offer you, in this editor. Variable and function names are case-sensitive!

You can find example codes for all games in the sections below. Please note, that these are just examples to give you some inspiration and are not guaranteed to make profit!

## Variables
The following variables are available in all games:

- `game`
Type: string
Required: true
Possible values: baccarat, blackjack, slots-samurai, cases, coinflip, diamonds, dice, tower, hilo, keno, limbo, mines, plinko, pump, rock-paper-scissors, roulette, slots-scarab, snakes, slots-tomeoflife,video-poker, wheel
- `casino`
Type: string (read-only)
Possible values: `500CASINO`, `BCHGAMES`, `CHIPSGG`, `GOATED`, `SHUFFLE`, `SHUFFLE_US`, `STAKE`, `STAKE_US`, `WOLFBET`, `THRILL`
- `minBetSize`
Type: float (read-only)
The minimum bet size for the currently active currency.
- `username`
Type: string (read-only)
Username of the currently logged in casino account.
- `lastBet`
Type: object (read-only)
- `asyncMode`
Type: boolean (default: false)
Use async mode on your own risk! If turned on, bets will be made asynchronously, which means that when switching to normal mode, it can take some more bets until it completely finished all bets made in async mode. Also we do not recommend using async mode, when increasing bet size based on losses or wins. Only use this when you know what you’re doing!
- `lookupBetIds`
Type: boolean (default: false)
Set this to true if you want the bot to lookup the bet IDs (casino:…). We recommend to only set this to true if it’s really necessary for your strategy.
- `isZeroBettingAllowed`
Type: boolean (read-only)
Indicates if betting with 0 bet size is supported in the casino you’re playing in.
- `isSimulationMode
Type: boolean (read-only)
Check if the current mode is on simulation mode or not.
- `currentStreak`
Type: integer (read-only)
Positive on a win streak, negative on a loss streak.
- `rollNumber`
Type: integer (read-only)
- `balance`
Type: float (read-only)
- `currency`
Type: string (read-only)
- `getConversionRate()`
Type: object (read-only)
Conversion rates for all supported crypto and FIAT currencies . When called without parameters, it retrieves the conversion rate based on the currently active cryptocurrency and fiat currency (defaulting to USD). The function also accepts two optional parameters: the cryptocurrency code and the fiat currency code.
Example: ` `(getConversionRate()`will get the currency rate for the currently active  crypto in USD  `(getConversionRate(currency,“EUR”)`will get the currency rate for the currently active crypto in EUR  `(getConversionRate(“TRX”,“EUR”)` will get the currency rate for the TRX  crypto in EUR
- `profit`
Type: float (read-only)
- `highestProfit`
Type: float (read-only)
- `lowestProfit`
Type: float (read-only)
- `wagered`
Type: float (read-only)
- `vaulted`
Type: float (read-only)
- `wins`
Type: integer (read-only)
- `losses`
Type: integer (read-only)
- `rtp`
Type: float (read-only)
- `leftSeedResets`
Type: float (read-only)
- `bestB2bMultipliers`
Type: array (read-only)
Array of the best B2B multipliers, sorted by highest multiplier.
- `betsPerSecond`
Type: integer (read-only)
- `highestBet`
Type: float (read-only)
- `highestLoss`
Type: float (read-only)
- `highestMultipliers`
Type: array (read-only)
Array of the highest won multipliers, sorted by highest multiplier.
- `drawdown`
Type: float (read-only)
Current drawdown, meaning the current distance to the highest profit (min 0).
- `maxDrawdown`
Type: float (read-only)
Maximum drawdown, meaning the highest distance between the highest profit and the lowest profit.
- `profitPerHour`
Type: float (read-only)
Profit projection based on betting timer and current profit.
- `bestWinStreaks`
Type: array (read-only)
Array of the best win streaks, sorted by highest win streak.
- `worstLossStreaks`
Type: array (read-only)
Array of the best loss streaks, sorted by highest loss streak.
- `timeRunning`
Type: integer (read-only)
Amount of seconds betting is running, analogue to the timer that’s shown above the bet list

## Engine functions

- `engine.start()`
Starts betting, equal to pressing the Start button.
- `engine.stop()`
Stops betting, equal to pressing the Stop button.
- `engine.pause()`
Pauses betting, equal to pressing the Pause button.
- `engine.resume()`
Resumes betting, equal to pressing the Resume button.
- `engine.onBetPlaced(callback)`
Sets the callback function (supports async), which is executed after a bet was placed. The first parameter in the callback function is the lastBet object. Find more information about the lastBet object of every single game in the tabs below.
- `engine.onGameRound(callback)`
Sets the callback function (supports async), which is executed for sub-rounds of a game (e.g. in BlackJack or Hilo). Find more information about the lastBet object of every single game in the tabs below.
- `engine.onBettingStopped(callback)`
Sets the callback function, which is executed, when betting was stopped. The first parameter in the callback function is a boolean, which is true when the betting was stopped manually (e.g. when pressing the Stop button or calling engine.stop()).

## Custom functions

- `log(var1 [, var2, ..., varN])`
Example: `log(`Bet size: ${betSize}`)`
Example: `log(lastBet)`
Example: `log(balance, profit)`
Print information in the console tab.
If the first argument is a HEX color code, this will be the color of the log message.
Example: `log('#eb4034', `Bet size: ${betSize}`)`
- `clearConsole()`
Clear messages in the console tab.
- `notification(message [, type = 'info'])`
Example: `notification('Profit target reached!', 'success')`
Possible values for the type variables are: error, success, warning, info (default)
- `resetStats()`
Resets all statistics. Same behaviour, like when you click on the reset button in the statistics window.
- `resetSeed()`
Example: `resetSeed()`
Example: `resetSeed('myCustomClientSeed')`
Creates a new server/client seed pair.
- `logToFile(fileName, content)`
Example: `logToFile('bets.csv', `${lastBet.nonce};${lastBet.payoutMultiplier}`)`
Appends the passed in content to the given file name. If the file doesn’t exist, it will be created. Files are stored in `~/Documents/Antebot/userLogs` on Windows/Linux and `~/Library/Application Support/userdata/logs` on mac OS.
- `chanceToMultiplier(chance)`
Example: `chanceToMultiplier(49.5); // Returns 2`
Converts chance from dice to multiplier.
- `depositToVault(amount)`
Example: `depositToVault(0.001);`
Deposits the given amount to the vault. Currently selected currency is used.
- `playHitSound()`
Example: `playHitSound();`
Plays the currently configured hit sound.
- `setSimulationBalance(amount)`
Example: `setSimulationBalance(100);`
Sets the simulation balance (Q$ FUN).
- `setSimulationNonce(nonce)`
Example: `setSimulationNonce(1);`
Sets the simulation nonce.
- `shuffle(array)`
Example: `shuffledArray = shuffle([0, 1, 2, 3, 4]); // [3, 4, 1, 0, 2]`
Randomizes the order of the input array.
- 
`getVipProgress()`
Example: `await getVipProgress()`
Returns the current VIP progress in the following format:

```json
{
    flag: 'None',
    progress: 50.00,
    nextFlag: 'Bronze',
    wagerLeft: 5000
}

```
