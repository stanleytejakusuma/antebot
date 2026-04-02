# Mines

> Source: https://forum.antebot.com/t/mines/767

## Variables

- `betSize`
Type: float
Required: true
- `mines`
Type: integer
Required: true
Possible values: From 1 to 24
- `fields`
Type: array
Required: true
Example: `fields = [0, 8, 10, 16, 18, 24];`
Fields are the range from 0 to 24. At least one number required.
- `gridSize`
Type: number
Required: false
Example: `gridSize = 25;`
Only required for casinos that offer different grid sizes for Mines.

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 9,
  "nonce": 1027,
  "active": false,
  "game": "mines",
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
    "mines": [5, 7, 14],
    "minesCount": 3,
    "rounds": [
      {"field": 2, "payoutMultiplier": 0},
      {"field": 5, "payoutMultiplier": 0},
      {"field": 6, "payoutMultiplier": 0},
      {"field": 7, "payoutMultiplier": 0},
      {"field": 14, "payoutMultiplier": 0},
      {"field": 15, "payoutMultiplier": 0},
      {"field": 16, "payoutMultiplier": 1.125},
      {"field": 18, "payoutMultiplier": 0},
      {"field": 21, "payoutMultiplier": 0},
      {"field": 23, "payoutMultiplier": 0}
    ]
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

function randomFields(amount) {
    // Create array with a number range from 0 to 24
    const fields = Array.from(Array(25).keys());

    return shuffle(fields).slice(0, amount);
}

game = 'mines';
gridSize = 25;
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
mines = 3;
amount = 10;
fields = randomFields(amount);
minFields = 1;
maxFields = 10;

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        // Add 3 numbers on win, make sure we have 10 numbers max.
        amount = Math.min(maxFields, amount + 3);
    } else {
        // Remove one number on loss, make sure we have at least 1 number.
        amount = Math.max(minFields, amount - 1);
    }
    
    fields = randomFields(amount);
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
