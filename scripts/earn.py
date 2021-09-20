import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from earner import Earner
from utils import get_secret, get_strategies_and_vaults

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")

CONFIG = {
    "poly": {
        "gas_oracle": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0",
        "keeper_acl": "0x46fa8817624eea8052093eab8e3fdf0e2e0443b2",
        # TODO: may need to make vault owner a list eventually
        "vault_owner": "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556",
        "registry": "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f",
    },
    # "eth": {
    #     "gas_oracle": "eth",
    #     "keeper_acl": "eth",
    #     "vault_owner": "eth",
    #     "registry": "eth"
    # }
}

INVALID_STRATS = ["0xDb0C3118ef1acA6125200139BEaCc5D675F37c9C"]


def safe_earn(earner, sett_name, vault, strategy):
    try:
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running {sett_name} earn: {e}")


def get_abi(chain: str, contract_id: str):
    with open(f"./abi/{chain}/{contract_id}.json") as f:
        return json.load(f)


if __name__ == "__main__":
    for chain in CONFIG.keys():
        node_url = get_secret(f"quiknode/{chain}-node-url", "NODE_URL")
        node = Web3(Web3.HTTPProvider(node_url))

        strategies, vaults = get_strategies_and_vaults(node, chain)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

        earner = Earner(
            chain=chain,
            keeper_acl=CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=CONFIG.get(chain).get("gas_oracle"),
        )

        for strategy, vault in zip(strategies, vaults):
            if strategy.address not in INVALID_STRATS:
                strat_name = strategy.functions.getName().call()

                logger.info(f"+-----Earning {strat_name}-----+")
                safe_earn(earner, strat_name, vault, strategy)
