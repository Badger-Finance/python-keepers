import json
import logging
import os
import sys
from time import sleep
from web3 import Web3, contract
from web3.middleware import geth_poa_middleware

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret, get_strategies_from_registry
from constants import HARVEST_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("script")


INVALID_STRATS = ["0xDb0C3118ef1acA6125200139BEaCc5D675F37c9C"]


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


if __name__ == "__main__":
    for chain in ["poly"]:
        node_url = get_secret(f"quiknode/{chain}-node-url", "NODE_URL")
        node = Web3(Web3.HTTPProvider(node_url))

        if chain == "eth":
            strategies = [
                node.eth.contract(
                    address=node.toChecksumAddress(address),
                    abi=get_abi(chain, "strategy"),
                )
                for address in HARVEST_CONFIG.get(chain).get("strategies")
            ]
        else:
            strategies = get_strategies_from_registry(node, chain)

        if chain == "poly":
            discord_url = get_secret("keepers/discord/poly-url", "DISCORD_WEBHOOK_URL")
            node.middleware_onion.inject(geth_poa_middleware, layer=0)
        else:
            discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

        harvester = GeneralHarvester(
            chain=chain,
            web3=node,
            keeper_acl=HARVEST_CONFIG[chain]["keeper_acl"],
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            base_oracle_address=HARVEST_CONFIG[chain]["gas_oracle"],
            discord_url=discord_url,
        )

        for strategy in strategies:
            if strategy.address not in INVALID_STRATS:
                strat_name = strategy.functions.getName().call()

                logger.info(f"+-----Harvesting {strat_name}-----+")
                res = safe_harvest(harvester, strat_name, strategy)
                logger.info(f"{res}")
                sleep(30)
