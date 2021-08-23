import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")

CONFIG = {
    "poly": {
        "gas_oracle": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0",
        "keeper_acl": "0x46fa8817624eea8052093eab8e3fdf0e2e0443b2",
        # TODO: may need to make vault owner a list eventually
        "vault_owner": "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556",
        "registry": "0x22765948A3d5048F3644b81792e4E1aA7ea3da4a",
    },
}


def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"HARVESTING strategy {strategy.address}")
    try:
        harvester.harvest(strategy)
        return "Success"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")

    logger.info("ATTEMPT: harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvestNoReturn: {e}")

    logger.info("ATTEMPT: tend_then_harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success"
    except Exception as e:
        logger.error(f"Error running {strategy_name} tend_then_harvest: {e}")

    return "Failure"


def get_strategies(node: Web3, chain: str) -> list:
    strategies = []
    vault_owner = node.toChecksumAddress(CONFIG.get(chain).get("vault_owner"))
    registry = node.eth.contract(
        address=node.toChecksumAddress(CONFIG.get(chain).get("registry")),
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
    for chain in CONFIG.keys():
        node_url = get_secret(f"quiknode/{chain}-node-url", "NODE_URL")
        node = Web3(Web3.HTTPProvider(node_url))

        if chain == "eth":
            strategies = [
                node.eth.contract(
                    address=node.toChecksumAddress(address),
                    abi=get_abi(chain, "strategy"),
                )
                for address in CONFIG.get(chain).get("strategies")
            ]
        else:
            strategies = get_strategies(node, chain)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

        harvester = GeneralHarvester(
            chain=chain,
            web3=node,
            keeper_acl=CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            base_oracle_address=CONFIG.get(chain).get("gas_oracle"),
        )

        for strategy in strategies:
            strat_name = strategy.functions.getName().call()

            logger.info(f"+-----Harvesting {strat_name}-----+")
            res = safe_harvest(harvester, strat_name, strategy)
            logger.info(f"{res}")
