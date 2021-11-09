import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from constants import MULTICHAIN_CONFIG, NODE_URL_SECRET_NAMES
from earner import Earner
from enums import Network
from utils import get_secret, get_strategies_and_vaults, get_node_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")

INVALID_STRATS = ["0xDb0C3118ef1acA6125200139BEaCc5D675F37c9C"]


def safe_earn(earner, sett_name, vault, strategy):
    try:
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running {sett_name} earn: {e}")


if __name__ == "__main__":
    for chain in [Network.Polygon]:
        node_url = get_node_url(chain)
        node = Web3(Web3.HTTPProvider(node_url))

        strategies, vaults = get_strategies_and_vaults(node, chain)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG[chain]["gas_oracle"],
        )

        for strategy, vault in zip(strategies, vaults):
            if strategy.address not in INVALID_STRATS:
                strat_name = strategy.functions.getName().call()

                logger.info(f"+-----Earning {strat_name}-----+")
                safe_earn(earner, strat_name, vault, strategy)
