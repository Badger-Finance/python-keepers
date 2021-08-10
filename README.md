# python-keepers
Python based keeper bots for Badger setts.

## Available Keepers

#### Centralized Oracle Proposer
```
Chain: Ethereum
Cadence: Daily 18:30 UTC
```
#### General Harvester
```
Chain: Polygon
Cadence: Hourly
Setts: 
```
#### ibBTC Fee Collector
```
Chain: Ethereum
Cadence: Daily 10:00 UTC
```
#### Private Harvester
```
Chain: Ethereum
Cadence: Daily 10:15 UTC
Setts: cvxCRV, cvx
```
#### Rebaser
```
Chain: Ethereum
Cadence: Daily 20:00 UTC
```
## testing:

Set `TEST_DISCORD_WEBHOOK_URL` in `.env` to a test url if you have one or want to see notifications.

To test sushi bots with the forked mainnet network:
`brownie test tests/test_sushi.py -s`

To test pancake bots on the forked bsc network:
`brownie test tests/test_cake.py -s --network bsc-fork`