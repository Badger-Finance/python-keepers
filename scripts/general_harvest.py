import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harvester import GeneralHarvester

logging.basicConfig(level=logging.INFO)

BADGER_WBTC_STRATEGY = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
DIGG_WBTC_STRATEGY = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
ETH_WBTC_STRATEGY = "0x7A56d65254705B4Def63c68488C0182968C452ce"


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")

def get_abi(chain: str, contract_id: str):
        with open(f"./abi/{chain}/{contract_id}.json") as f:
            return json.load(f)

def get_strategy_from_vault(node: Web3, vault_address: str) -> contract:
    # TODO: make chain agnostic
    vault_contract = node.eth.contract(
        address=vault_address,
        abi=get_abi("poly", "vault")
    )

    token_address = vault_contract.functions.token().call()
    controller_address = vault_contract.functions.controller().call()

    controller_contract = node.eth.contract(
        address=controller_address,
        abi=get_abi("poly", "controller")
    )

    strategy_address = controller_contract.functions.strategies(token_address).call()

    # TODO: handle v1 vs v2 strategy abi
    strategy_contract = node.eth.contract(
        address=strategy_address,
        abi=get_abi("poly", "strategy")
    )

    return strategy_contract



if __name__ == "__main__":
    node = Web3(Web3.HTTPProvider(os.getenv("NODE_URL")))
    # get strategy addresses
    poly_registry = node.eth.contract(
        address=node.toChecksumAddress(os.getenv("POLY_REGISTRY")),
        abi=get_abi("poly", "registry"),
    )

    poly_vault_owner = node.toChecksumAddress(os.getenv("POLY_VAULT_OWNER"))
    for vault_address in poly_registry.functions.fromAuthor(poly_vault_owner).call():
        strategy = get_strategy_from_vault(node, vault_address)

        estimated_harvest = strategy.functions.harvest().call()

    # eth_registry = get_abi("eth", "registry")

    logger = logging.getLogger()  

    harvester = GeneralHarvester()

    logger.info("+-----Harvesting BADGER WBTC LP-----+")
    safe_harvest(harvester, "BADGER WBTC LP", BADGER_WBTC_STRATEGY)

    logger.info("+-----Harvesting DIGG WBTC LP-----+")
    safe_harvest(harvester, "DIGG WBTC LP", DIGG_WBTC_STRATEGY)

    logger.info("+-----Harvesting ETH WBTC LP-----+")
    safe_harvest(harvester, "ETH WBTC LP", ETH_WBTC_STRATEGY)
