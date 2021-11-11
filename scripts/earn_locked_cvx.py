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

from enums import Network
from earner import Earner
from utils import get_secret, get_abi, get_node_url
from constants import (
    MULTICHAIN_CONFIG,
    ETH_BVECVX_STRATEGY,
    ETH_BVECVX_VAULT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")


if __name__ == "__main__":
    chain = Network.Ethereum
    node_url = get_node_url(chain)
    node = Web3(Web3.HTTPProvider(node_url))

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

    earner = Earner(
        chain=chain,
        keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        web3=node,
        base_oracle_address=MULTICHAIN_CONFIG.get(chain).get("gas_oracle"),
    )

    strategy = node.eth.contract(
        address=ETH_BVECVX_STRATEGY, abi=get_abi(chain, "strategy")
    )
    vault = node.eth.contract(address=ETH_BVECVX_VAULT, abi=get_abi(chain, "vault"))

    strat_name = "Badger Vested Escrow Convex Token"

    logger.info(f"+-----Earning {strat_name}-----+")
    earner.earn(vault, strategy, strat_name)
