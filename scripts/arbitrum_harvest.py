import logging
import os
import sys
import time
from pathlib import Path
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612"
KEEPER_ACL = "0x265820F3779f652f2a9857133fDEAf115b87db4B"
REGISTRY = "0xFda7eB6f8b7a9e9fCFd348042ae675d1d652454f"

# strategies = {
#     "0x86f772C82914f5bFD168f99e208d0FC2C371e9C2",  # WETH-SUSHI-SLP
#     "0xA6827f0f14D0B83dB925B616d820434697328c22",  # WBTC-WETH-SLP
# }

CONFIG = {
    "arbitrum": {
        "gas_oracle": ETH_USD_CHAINLINK,
        "keeper_acl": KEEPER_ACL,
        # TODO: may need to make vault owner a list eventually
        "vault_owner": "0xeE8b29AA52dD5fF2559da2C50b1887ADee257556",
        "registry": REGISTRY,
    },
}

# TODO: Add conditional harvest logic
def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
    try:
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")
    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} tend_then_harvest: {e}")


def get_strategies(node: Web3, chain: str) -> list:
    strategies = []
    vault_owner = node.toChecksumAddress(CONFIG.get(chain).get("vault_owner"))
    registry = node.eth.contract(
        address=node.toChecksumAddress(CONFIG.get(chain).get("registry")),
        abi=get_abi(chain, "registry"),
    )

    for vault_address in registry.functions.getVaults("v1", vault_owner).call():
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
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("alchemy/arbitrum-node-url", "ARBITRUM_NODE_URL")
    discord_url = get_secret(
        "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
    )

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=False,
        discord_url=discord_url,
    )

    strategies = get_strategies(web3, "arbitrum")

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi("arbitrum", "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        safe_harvest(harvester, strategy_name, strategy)

        # Sleep for a few blocks in between harvests
        time.sleep(30)
