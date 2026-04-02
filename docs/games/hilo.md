# Hilo

> Source: https://forum.antebot.com/t/hilo/764

## Variables

- `betSize`
Type: float
Required: true
- `startCard`
Type: object
Required: true
Example: `{rank: "K", suit: "C"}`
Suit keys: “C” =  Clubs, “D” =  Diamonds, “H” =  Hearts, “S” =  Spades

## onGameRound return constants

- `HILO_BET_HIGH`
Type: string
- `HILO_BET_HIGH_EQUAL`
Type: string
- `HILO_BET_LOW`
Type: string
- `HILO_BET_LOW_EQUAL`
Type: string
- `HILO_SKIP`
Type: string
Hint: You can skip at maximum 52 cards in one Hilo bet!
- `HILO_BET_EQUAL`
Type: string
- `HILO_CASHOUT`
Type: string

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 6,
  "nonce": 1027,
  "active": true,
  "game": "hilo",
  "win": true,
  "amount": 2,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 1.161875,
  "b2bMultiplier": 1.161875,
  "payout": 2.32375,
  "fiatPayout": "$0.00",
  "currency": "trx",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "startCard": {
      "suit": "C",
      "rank": "A"
    },
    "rounds": [
      {
        "card": {
          "suit": "S",
          "rank": "K"
        },
        "guess": "higher",
        "payoutMultiplier": 1.0725
      },
      {
        "card": {
          "suit": "S",
          "rank": "7"
        },
        "guess": "lower",
        "payoutMultiplier": 1.161875
      },
    ]
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Increase bet size every 2nd loss, reset on win

// resetStats();
// resetSeed();

game = 'hilo';
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
startCard = {rank: "7", suit: "C"};
cashOutAtMultiplier = 3;
increaseOnLoss = 2;

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        betSize = initialBetSize;
    }
    
    if (currentStreak < 0 && currentStreak % -2 === 0) {
        betSize *= increaseOnLoss;
    }
});

engine.onGameRound((currentBet) => {
    // Fetching current card rank, fallback to start card rank, because rounds is an empty array on first game round
    currentCardRank = currentBet.state.rounds.at(-1)?.card.rank || currentBet.state.startCard.rank;
    payoutMultiplier = currentBet.state.rounds.at(-1)?.payoutMultiplier || 0;
    skippedCards = currentBet.state.rounds.filter(round => round.guess === 'skip').length;
    
    if (payoutMultiplier >= cashOutAtMultiplier) {
        return HILO_CASHOUT;
    }
    
    if (currentCardRank === "A") {
        return HILO_BET_HIGH;
    }
    
    if (currentCardRank === "J") {
        return HILO_BET_LOW;
    }
    
    if (currentCardRank === "Q") {
        return HILO_BET_LOW;
    }
    
    if (currentCardRank === "K") {
        return HILO_BET_LOW;
    }
    
    if (Number(currentCardRank) < 7) {
        return HILO_BET_LOW;
    }
    
    // You can only skip 52 cards in one Hilo bet!
    if (Number(currentCardRank) === 7 && skippedCards <= 52) {
        return HILO_SKIP;
    }

    return HILO_BET_HIGH;
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
