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
from utils import get_abi, get_secret, get_strategy_from_vault
from constants import MULTICHAIN_CONFIG, FTM_VAULTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)


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
    node_url = "https://rpc.ftm.tools/"
    discord_url = get_secret(
        "keepers/harvester/fantom/info-webhook", "DISCORD_WEBHOOK_URL"
    )

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        chain=Network.Fantom,
        keeper_acl=MULTICHAIN_CONFIG[Network.Fantom]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Fantom]["gas_oracle"],
        use_flashbots=False,
        discord_url=discord_url,
    )
    strategies = []
    for vault_address in FTM_VAULTS:
        strategy, _ = get_strategy_from_vault(web3, Network.Fantom, vault_address)
        strategies.append(strategy)

    for strategy in strategies:
        if (
            strategy.address
            not in MULTICHAIN_CONFIG[Network.Fantom]["harvest"]["invalid_strategies"]
        ):
            # safe_harvest(harvester, strategy)
            strategy_name = strategy.functions.getName().call()
            logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
            harvester.harvest(strategy)

            # Sleep for a few blocks in between harvests
            time.sleep(30)
