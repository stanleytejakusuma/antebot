# Crossover (aka. Chicken)

> Source: https://forum.antebot.com/t/crossover-aka-chicken/777

## Variables

- `betSize`
Type: float
Required: true
- `difficulty`
Type: string
Required: true
Possible values: easy, medium, hard, expert
- `rounds`
Type: integer
Required: true
Number range starting from 1, ending depending on the difficulty:

easy: 1 - 19
- medium: 1 - 17
- hard: 1 - 15
- expert: 1 - 10

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 6,
  "nonce": 1027,
  "active": false,
  "game": "crossover",
  "win": true,
  "amount": 0,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 1.6333333333333333,
  "b2bMultiplier": 1.6333333333333333,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "difficulty": "expert",
    "roundTarget": 1,
    "roundTargetMultiplier": 1.96,
    "roundResult": 9,
    "roundResultMultiplier": 16460.08
  }
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Randomly change difficulty and rounds after every bet

// resetStats();
// resetSeed();

function randomNumber(min, max) {
    return Math.floor(Math.random() * (max - min + 1) + min);
}

function randomRounds(difficultyIndex) {
    const maxRounds = [19, 17, 15, 10];

    return randomNumber(1, maxRounds[difficultyIndex]);
}

game = 'crossover';
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
difficulties = ['easy', 'medium', 'hard', 'expert'];
difficultyIndex = 0;
difficulty = difficulties[difficultyIndex];
rounds = randomRounds(difficultyIndex);

engine.onBetPlaced(async (lastBet) => {
    difficulty = difficulties[++difficultyIndex];
    rounds = randomRounds(difficultyIndex);

    if (difficultyIndex + 1 === difficulties.length) {
        difficultyIndex = 0;
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
