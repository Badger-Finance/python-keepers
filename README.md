# python-keepers
Python based keeper bots for Badger setts.

## testing:

To test sushi bots with the forked mainnet network:
`brownie test tests/test_sushi.py -s`

To test pancake bots on the forked bsc network:
`brownie test test/test_cake.py -s --network bsc-fork`
Where `bsc-fork` is the name of a brownie network that forks bsc. (Command: `ganache-cli --port 8545 --gasLimit 12000000 --accounts 10 --hardfork istanbul --mnemonic brownie --fork https://bsc-dataseed1.binance.org --chainId 0x38`)