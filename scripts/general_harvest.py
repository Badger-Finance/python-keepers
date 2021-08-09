import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harvester import GeneralHarvester
from utils import get_secret

logging.basicConfig(level=logging.INFO)

BADGER_WBTC_STRATEGY = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
DIGG_WBTC_STRATEGY = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
ETH_WBTC_STRATEGY = "0x7A56d65254705B4Def63c68488C0182968C452ce"
MATIC_USD_ORACLE = "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


def get_abi(chain: str, contract_id: str):
    with open(f"./abi/{chain}/{contract_id}.json") as f:
        return json.load(f)


def get_strategies(node: Web3, chain: str) -> list:
    strategies = []
    vault_owner = node.toChecksumAddress(os.getenv(f"{chain.upper()}_VAULT_OWNER"))
    registry = node.eth.contract(
        address=node.toChecksumAddress(os.getenv(f"{chain.upper()}_REGISTRY")),
        abi=get_abi(chain, "registry"),
    )

    for vault_address in registry.functions.fromAuthor(vault_owner).call():
        strategy = get_strategy_from_vault(node, chain, vault_address)
        strategies.append(strategy)

    return strategies


def get_strategy_from_vault(node: Web3, chain: str, vault_address: str) -> contract:
    vault_contract = node.eth.contract(
        address=vault_address, abi=get_abi(chain, "vault")
    )

    token_address = vault_contract.functions.token().call()
    controller_address = vault_contract.functions.controller().call()

    controller_contract = node.eth.contract(
        address=controller_address, abi=get_abi(chain, "controller")
    )

    strategy_address = controller_contract.functions.strategies(token_address).call()

    # TODO: handle v1 vs v2 strategy abi
    strategy_contract = node.eth.contract(
        address=strategy_address, abi=get_abi(chain, "strategy")
    )

    return strategy_contract


if __name__ == "__main__":
    node = Web3(Web3.HTTPProvider(os.getenv("NODE_URL")))

    strategies = get_strategies(node, "poly")

    logger = logging.getLogger("script")

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

    harvester = GeneralHarvester(
        chain="poly",
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        web3=os.getenv("POLY_NODE_URL"),
        base_oracle_address=MATIC_USD_ORACLE,
    )

    for strategy in strategies:
        strat_name = strategy.functions.getName().call()

        logger.info(f"+-----Harvesting {strat_name}-----+")
        safe_harvest(harvester, strat_name, strategy)
