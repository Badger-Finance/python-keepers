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
    "eth": {
        "gas_oracle": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        "keeper_acl": "0x711A339c002386f9db409cA55b6A35a604aB6cF6",
        "strategies": [
            "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95",  # CVX_HELPER_STRATEGY
            "0x826048381d65a65DAa51342C51d464428d301896",  # CVX_CRV_HELPER_STRATEGY
            "0xff26f400e57bf726822eacbb64fa1c52f1f27988",  # HBTC_CRV_STRATEGY
            "0x1C1fD689103bbFD701b3B7D41A3807F12814033D",  # PBTC_CRV_STRATEGY
            "0x2bb864cdb4856ab2d148c5ca52dd7ccec126d138",  # OBTC_CRV_STRATEGY
            "0x4f3e7a4566320b2709fd1986f2e9f84053d3e2a0",  # BBTC_CRV_STRATEGY
            "0x05ec4356e1acd89cc2d16adc7415c8c95e736ac1",  # TRICRYPTO_CRV_STRATEGY
            "0x75b8E21BD623012Efb3b69E1B562465A68944eE6",  # native.badger
            "0x6582a5b139fc1c6360846efdc4440d51aad4df7b",  # native.renCrv
            "0xf1ded284e891943b3e9c657d7fc376b86164ffc2",  # native.sbtcCrv
            "0x522bb024c339a12be1a47229546f288c40b62d29",  # native.tbtcCrv
            "0x95826C65EB1f2d2F0EDBb7EcB176563B61C60bBf",  # native.uniBadgerWbtc
            "0xaaE82E3c89e15E6F26F60724f115d5012363e030",  # harvest.renCrv
            "0x7A56d65254705B4Def63c68488C0182968C452ce",  # native.sushiWbtcEth
            "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1",  # native.sushiBadgerWbtc
            "0x4a8651F2edD68850B944AD93f2c67af817F39F62",  # native.digg
            "0xadc8d7322f2E284c1d9254170dbe311E9D3356cf",  # native.uniDiggWbtc
            "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a",  # native.sushiDiggWbtc
            "0xf4146A176b09C664978e03d28d07Db4431525dAd",  # experimental.sushiIBbtcWbtc
            "0xA6af1B913E205B8E9B95D3B30768c0989e942316",  # experimental.digg
        ],
    },
}


def safe_harvest(harvester, strategy_name, strategy) -> str:
    try:
        harvester.harvest(strategy)
        return "Success"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")

    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
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
                node.eth.contract(address=node.toChecksumAddress(address), abi=get_abi(chain, "strategy"))
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
            logger.info(f"+-----{res} Harvesting {strat_name}-----+")
