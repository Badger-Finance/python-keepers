import logging
import os
import sys
import time
from pathlib import Path
from web3 import Web3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612"
# TODO: Use registry for this (0xfda7eb6f8b7a9e9fcfd348042ae675d1d652454f)
KEEPER_ACL = "0x265820F3779f652f2a9857133fDEAf115b87db4B"

strategies = {
    "0x86f772C82914f5bFD168f99e208d0FC2C371e9C2",  # WETH-SUSHI-SLP
    "0xA6827f0f14D0B83dB925B616d820434697328c22",  # WBTC-WETH-SLP
}

# TODO: Add conditional harvest logic
def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
    try:
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")
    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} tend_then_harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("alchemy/arbitrum-node-url", "ARBITRUM_NODE_URL")
    discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=False,
        discord_url=discord_url,
    )

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi("eth", "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        safe_harvest(harvester, strategy_name, strategy)

        # Sleep for a few blocks in between harvests
        time.sleep(30)
