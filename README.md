# python-keepers
Python based keeper bots for Badger setts.

## testing:

Set `TEST_DISCORD_WEBHOOK_URL` in `.env` to a test url if you have one or want to see notifications.

To test sushi bots with the forked mainnet network:
`brownie test tests/test_sushi.py -s`

To test pancake bots on the forked bsc network:
`brownie test tests/test_cake.py -s --network bsc-fork`