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

from earner import Earner
from utils import get_secret, get_strategies_and_vaults, get_abi
from constants import MULTICHAIN_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")

LOCKED_CVX_STRATEGY = "0x3ff634ce65cDb8CC0D569D6d1697c41aa666cEA9"
LOCKED_CVX_VAULT = "0xfd05D3C7fe2924020620A8bE4961bBaA747e6305"


if __name__ == "__main__":
    chain = "eth"
    node_url = get_secret(f"quiknode/{chain}-node-url", "NODE_URL")
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
        address=LOCKED_CVX_STRATEGY, abi=get_abi(chain, "strategy")
    )
    vault = node.eth.contract(address=LOCKED_CVX_VAULT, abi=get_abi(chain, "vault"))

    strat_name = "Badger Vested Escrow Convex Token"

    logger.info(f"+-----Earning {strat_name}-----+")
    earner.earn(vault, strategy, strat_name)
