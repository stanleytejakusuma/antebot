# Keno

> Source: https://forum.antebot.com/t/keno/765

## Variables

- `betSize`
Type: float
Required: true
- `risk`
Type: string
Required: true
Possible values: classic, low, medium, high
- `numbers`
Type: array
Required: true
Example: `numbers = [1, 8, 10, 16, 18, 25];`
Numbers are the range from 0 to 39. At least one number required.

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 7,
  "nonce": 1027,
  "active": false,
  "game": "keno",
  "win": false,
  "amount": 0,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 0,
  "b2bMultiplier": 0,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "drawnNumbers": [0, 9, 13, 16, 27, 29, 30, 31, 36, 38],
    "selectedNumbers": [7, 9, 11, 17, 19, 22, 26, 31, 33, 35],
    "risk": "medium"
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Add 3 random numbers on win, remove one random number on loss.
// Keep minimum of 1 and a maximum of 10 numbers.

// resetStats();
// resetSeed();

function randomNumbers(amount) {
    // Create array with a number range from 0 to 39
    const numbers = Array.from(Array(40).keys());

    return shuffle(numbers).slice(0, amount);
}

game = 'keno';
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
risk = 'medium';
amount = 10;
numbers = randomNumbers(amount);
minNumbers = 1;
maxNumbers = 10;

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        // Add 3 numbers on win, make sure we have 10 numbers max.
        amount = Math.min(maxNumbers, amount + 3);
    } else {
        // Remove one number on loss, make sure we have at least 1 number.
        amount = Math.max(minNumbers, amount - 1);
    }
    
    numbers = randomNumbers(amount);
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
