import logging
import os
import sys
import time
from pathlib import Path
from web3 import Web3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from enums import Network
from general_harvester import GeneralHarvester
from utils import get_abi, get_secret, get_strategies_from_registry
from constants import MULTICHAIN_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

# strategies = {
#     "0x86f772C82914f5bFD168f99e208d0FC2C371e9C2",  # WETH-SUSHI-SLP
#     "0xA6827f0f14D0B83dB925B616d820434697328c22",  # WBTC-WETH-SLP
# }

# TODO: Add conditional harvest logic
def safe_harvest(harvester, strategy) -> str:
    try:
        strategy_name = strategy.functions.getName().call()
        logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running harvest: {e}")
    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running tend_then_harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    # node_url = get_secret("alchemy/arbitrum-node-url", "ARBITRUM_NODE_URL")
    node_url = "https://arb1.arbitrum.io/rpc"
    discord_url = get_secret(
        "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
    )

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        chain=Network.Arbitrum,
        keeper_acl=MULTICHAIN_CONFIG[Network.Arbitrum]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Arbitrum]["gas_oracle"],
        use_flashbots=False,
        discord_url=discord_url,
    )

    strategies = get_strategies_from_registry(web3, Network.Arbitrum)

    for strategy in strategies:
        if (
            strategy.address
            not in MULTICHAIN_CONFIG[Network.Arbitrum]["harvest"]["invalid_strategies"]
        ):
            safe_harvest(harvester, strategy)

            # Sleep for a few blocks in between harvests
            time.sleep(30)
