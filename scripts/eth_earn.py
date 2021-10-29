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
from utils import get_secret, get_strategies_and_vaults, get_strategy_from_vault
from constants import (
    MULTICHAIN_CONFIG,
    ETH_YVWBTC_VAULT,
    ETH_TRICRYPTO_VAULT,
    ETH_BVECVX_CVX_LP_VAULT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")

INVALID_VAULTS = [ETH_YVWBTC_VAULT, ETH_TRICRYPTO_VAULT]


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

        registry = node.eth.contract(
            address=node.toChecksumAddress(MULTICHAIN_CONFIG[chain]["registry"]),
            abi=get_abi(chain, "registry"),
        )

        vaults = []
        strategies = []
        vault_addresses = registry.functions.getFilteredProductionVaults("v1", 1).call()
        vault_addresses.extend(
            registry.functions.getFilteredProductionVaults("v1", 2).call()
        )
        # vault_addresses.append(ETH_BVECVX_CVX_LP_VAULT)

        for address in vault_addresses:
            if address not in INVALID_VAULTS:
                logger.info(f"address: {address}")
                strategy, vault = get_strategy_from_vault(node, chain, address)
                strategies.append(strategy)
                vaults.append(vault)

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
