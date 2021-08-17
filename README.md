# python-keepers
Python based keeper bots for Badger setts.

## Contributing
This repo is wired up to the BadgerDAO Kubernetes ArgoCD managed environment. On a PR to master the container creation, push, and manifest update will occur, which triggers ArgoCD to update the "prod" environment (dev is prod as of 8/11/21).

In order to prevent overwriting the current working prod manifests the contributor workflow is as follows:
1. Create feature branch from `develop`.
2. Create PR to `develop`.
3. Upon PR LGTM, merge into `develop`.
4. Releases will be PRs opened from `develop` to `main` and will deploy the updated keepers to prod.

## Available Keepers

#### Centralized Oracle Proposer
```
Chain: Ethereum
Cadence: Daily 18:30 UTC
```
#### General Harvester
```
Chain: Polygon
Cadence: Hourly, 5 min past the hour
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