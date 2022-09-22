import sys
import time

from hexbytes import HexBytes
from web3 import Web3
from web3 import contract

from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.aws import get_secret
from src.general_harvester import GeneralHarvester
from src.json_logger import exception_logging
from src.json_logger import logger
from src.settings.harvest_settings import ARB_HARVEST_SETTINGS
from src.web3_utils import get_strategies_and_vaults

sys.excepthook = exception_logging


def safe_harvest(
    harvester: GeneralHarvester,
    strategy_contract: contract,
    strategy_address: HexBytes,
    strategy_name: str,
) -> str:
    try:
        logger.info(f"+-----Harvesting {strategy_name} {strategy_address}-----+")
        harvester.harvest(strategy_contract, strategy_name=strategy_name)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running harvest: {e}")
    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy_contract, strategy_name=strategy_name)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy_contract, strategy_name=strategy_name)
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

    strategies, vaults = get_strategies_and_vaults(web3, Network.Arbitrum)

    for strategy, vault in zip(strategies, vaults):
        if vault.address not in ARB_HARVEST_SETTINGS.deprecated_vaults:
            safe_harvest(harvester, strategy.contract, strategy.address, strategy.name)

            # Sleep for a few blocks in between harvests
            time.sleep(30)
