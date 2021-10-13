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
from utils import get_secret, get_strategies_and_vaults
from constants import MULTICHAIN_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")


def safe_earn(earner, sett_name, vault, strategy):
    try:
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running {sett_name} earn: {e}")


def get_abi(chain: str, contract_id: str):
    with open(f"./abi/{chain}/{contract_id}.json") as f:
        return json.load(f)


if __name__ == "__main__":
    for chain in ["eth"]:
        node_url = get_secret(f"quiknode/{chain}-node-url", "NODE_URL")
        node = Web3(Web3.HTTPProvider(node_url))

        strategies, vaults = get_strategies_and_vaults(node, chain)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
        discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")

        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG[chain]["keeper_acl"],
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG[chain]["gas_oracle"],
            discord_url=discord_url,
        )

        for strategy, vault in zip(strategies, vaults):
            if (
                strategy.address
                not in MULTICHAIN_CONFIG[chain]["earn"]["invalid_strategies"]
            ):
                strat_name = strategy.functions.getName().call()

                logger.info(f"+-----Earning {strat_name}-----+")
                safe_earn(earner, strat_name, vault, strategy)
