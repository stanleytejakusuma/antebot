# Tower

> Source: https://forum.antebot.com/t/tower/763

## Variables

- `betSize`
Type: float
Required: true
- `difficulty`
Type: string
Required: true
Possible values: easy, medium, hard, expert, master
- `tiles`
Type: array
Required: true
Example: `tiles = [0, 0, 1, 1];`
Each number represents the index of a row. If you have an array with 3 numbers, that means you’re betting on 3 rows.
Be aware, that Stake doesn’t validate if the chosen number is valid for the current difficulty! You have to make sure to not use `2` for difficulty `hard`, for example, because there are only 2 columns to choose from and the numbers start with 0.

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 6,
  "nonce": 1027,
  "active": false,
  "game": "tower",
  "win": true,
  "amount": 0,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 1.74,
  "b2bMultiplier": 1.74,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "currentRound": 2,
    "playedRounds": [
      [2, 0, 1],
      [1, 0, 3],
      [2, 0, 1],
      [2, 0, 3],
      [0, 1, 2],
      [0, 1, 3],
      [3, 2, 1],
      [3, 1, 2],
      [0, 1, 3]
    ],
    "difficulty": "easy",
    "rounds": [
      [2, 0, 1],
      [1, 0, 3],
      [2, 0, 1],
      [2, 0, 3],
      [0, 1, 2],
      [0, 1, 3],
      [3, 2, 1],
      [3, 1, 2],
      [0, 1, 3]
    ],
    "tilesSelected": [1, 3]
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Always bet on 2 rows and cycle through the difficulties

// resetStats();
// resetSeed();

function randomNumber(min, max) {
    return Math.floor(Math.random() * (max - min + 1) + min);
}

function randomTiles(amount, difficultyIndex) {
    const maxTiles = [4, 3, 2, 3, 4],
        tiles = [];

    while (tiles.length < amount) {
        tiles.push(randomNumber(0, maxTiles[difficultyIndex] - 1));
    }

    return tiles;
}

game = 'tower';
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
difficulties = casino === 'SHUFFLE' ? ['EASY', 'MEDIUM', 'HARD', 'EXPERT', 'MASTER'] : ['easy', 'medium', 'hard', 'expert', 'master'];
difficultyIndex = 0;
difficulty = difficulties[difficultyIndex];
rows = 2;
tiles = randomTiles(rows, difficultyIndex);

engine.onBetPlaced(async (lastBet) => {
    difficulty = difficulties[++difficultyIndex];
    tiles = randomTiles(rows, difficultyIndex);

    if (difficultyIndex + 1 === difficulties.length) {
        difficultyIndex = 0;
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
