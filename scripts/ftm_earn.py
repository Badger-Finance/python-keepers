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
from utils import get_secret, get_strategy_from_vault
from constants import MULTICHAIN_CONFIG, FTM_VAULTS
from enums import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.ftm_earn")


def safe_earn(earner, vault, strategy):
    try:
        sett_name = strategy.functions.getName().call()
        logger.info(f"+-----Earning {sett_name}-----+")
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running earn: {e}")


if __name__ == "__main__":
    for chain in [Network.Fantom]:
        node_url = "https://rpc.ftm.tools/"
        node = Web3(Web3.HTTPProvider(node_url))

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
        discord_url = get_secret(
            "keepers/harvester/fantom/info-webhook", "DISCORD_WEBHOOK_URL"
        )

        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG.get(chain).get("gas_oracle"),
            discord_url=discord_url,
        )
        strategies = []
        vaults = []
        for vault_address in FTM_VAULTS:
            strategy, vault = get_strategy_from_vault(node, chain, vault_address)
            strategies.append(strategy)
            vaults.append(vault)

        for strategy, vault in zip(strategies, vaults):
            if (
                strategy.address
                not in MULTICHAIN_CONFIG[chain]["earn"]["invalid_strategies"]
            ):
                safe_earn(earner, vault, strategy)
