import logging
import time

from web3 import Web3

from config.constants import FTM_VAULTS
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.general_harvester import GeneralHarvester
from src.utils import get_secret
from src.utils import get_strategy_from_vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
