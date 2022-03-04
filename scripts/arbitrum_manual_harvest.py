import logging
import os
import sys
import time

from eth_account.account import Account
from pathlib import Path
from web3 import Web3

from config.constants import MULTICHAIN_CONFIG, ARB_WBTC_WETH_STRATEGY
from config.enums import Network
from src.general_harvester import GeneralHarvester
from src.utils import get_abi, get_secret, get_node_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

strategies = {ARB_WBTC_WETH_STRATEGY}


def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"HARVESTING strategy {strategy.address}")
    try:
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_node_url(Network.Arbitrum)
    discord_url = get_secret(
        "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
    )

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=MULTICHAIN_CONFIG[Network.Arbitrum]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Arbitrum]["gas_oracle"],
        use_flashbots=False,
        discord_url=discord_url,
    )

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Arbitrum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        logger.info(f"+-----Harvesting {strategy_name}-----+")
        safe_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)
