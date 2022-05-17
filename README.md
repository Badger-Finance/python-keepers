# python-keepers
Coverage: [![codecov](https://codecov.io/gh/Badger-Finance/python-keepers/branch/develop/graph/badge.svg?token=H8ULEZLN3Q)](https://codecov.io/gh/Badger-Finance/python-keepers)

Python based keeper bots for Badger system.


## Contributing
This repo is wired up to the BadgerDAO Kubernetes ArgoCD managed environment. On a PR to master the container creation, push, and manifest update will occur, which triggers ArgoCD to update the "prod" environment (dev is prod as of 8/11/21).

In order to prevent overwriting the current working prod manifests the contributor workflow is as follows:
1. Create feature branch from `develop`.
2. Create PR to `develop`.
3. Upon PR LGTM, merge into `develop`.
4. Releases will be PRs opened from `develop` to `main` and will deploy the updated keepers to prod.

## testing:

Set `WEB3_INFURA_PROJECT_ID` environment variable in terminal before running script.

To run tests with the forked mainnet network:
`brownie test tests/<test-file> --network=hardhat-fork`

To test pancake bots on the forked bsc network:
`brownie test tests/test_cake.py -s --network bsc-fork`