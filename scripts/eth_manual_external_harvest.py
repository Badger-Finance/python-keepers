from decimal import Decimal
import json
import logging
import os
import sys
from time import sleep
from typing import Tuple
from web3 import Web3, contract

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from external_harvester import ExternalHarvester
from utils import get_secret, get_strategies_and_vaults, get_abi
from constants import (
    MULTICHAIN_CONFIG,
    DIGG_TOKEN,
    BADGER_TOKEN,
    WBTC_TOKEN,
    ETH_BDIGG_STRATEGY,
    ETH_BDIGG_VAULT,
    ETH_DIGG_SUSHI_LP_STRATEGY,
    ETH_DIGG_SUSHI_LP_VAULT,
    ETH_BADGER_SUSHI_LP_STRATEGY,
    ETH_BADGER_SUSHI_LP_VAULT,
    ETH_BADGER_UNI_LP_STRATEGY,
    ETH_BADGER_UNI_LP_VAULT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eth-external-harvest")


def to_digg_shares_and_fragments(node, gdigg: float) -> Tuple[float, float]:
    if gdigg == 0:
        return 0
    digg_contract = node.eth.contract(
        address=node.toChecksumAddress(DIGG_TOKEN),
        abi=get_abi("eth", "digg_token"),
    )
    initial_fragments = int(gdigg * 10 ** 9)
    shares = (
        initial_fragments * digg_contract.functions._initialSharesPerFragment().call()
    )
    current_fragments = digg_contract.functions.sharesToFragments(shares).call()

    logger.info(
        (
            "Digg Conversion",
            {
                "input": gdigg,
                "scaledInput": initial_fragments,
                "shares": shares,
                "fragments": current_fragments,
                "fragmentsScaled": current_fragments / 10 ** 9,
                "ratio": current_fragments / initial_fragments,
            },
        )
    )
    return shares, current_fragments


def calculate_retroactive_digg(scheduled_emissions, missed_days):
    days_in_week = 7
    to_emit = scheduled_emissions / days_in_week * missed_days
    logger.info(f"should emit {to_emit} digg")
    shares, fragments = to_digg_shares_and_fragments(node, to_emit)
    logger.info(f"shares: {shares}")
    logger.info(f"frags: {fragments}")
    return fragments


def calculate_retroactive_badger(scheduled_emissions, missed_days):
    days_in_week = 7
    to_emit = scheduled_emissions / days_in_week * missed_days
    logger.info(f"should emit {Decimal(to_emit)} badger")
    return to_emit


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    node = Web3(Web3.HTTPProvider(os.getenv("ETH_NODE_URL")))

    eharvester = ExternalHarvester(
        node, base_oracle_address=MULTICHAIN_CONFIG["eth"]["gas_oracle"]
    )

    # BDIGG
    days_since = eharvester.days_since_last_harvest(ETH_BDIGG_STRATEGY)
    last_harvest = eharvester.last_harvest_times[ETH_BDIGG_STRATEGY]
    amount_owed = eharvester.get_amount_digg_owed(last_harvest, ETH_BDIGG_VAULT)
    if amount_owed != 0:
        _, fragments = to_digg_shares_and_fragments(node, amount_owed)
    else:
        fragments = 0

    logger.info("BDIGG")
    logger.info(
        {
            "want": DIGG_TOKEN,
            "strategy": ETH_BDIGG_STRATEGY,
            "amount": fragments,
            "days": days_since,
        }
    )

    # DIGG SUSHI
    days_since = eharvester.days_since_last_harvest(ETH_DIGG_SUSHI_LP_STRATEGY)
    last_harvest = eharvester.last_harvest_times[ETH_DIGG_SUSHI_LP_STRATEGY]
    amount_owed = eharvester.get_amount_digg_owed(last_harvest, ETH_DIGG_SUSHI_LP_VAULT)
    if amount_owed != 0:
        _, fragments = to_digg_shares_and_fragments(node, amount_owed)
    else:
        fragments = 0
    strategy = node.eth.contract(
        address=ETH_DIGG_SUSHI_LP_STRATEGY, abi=get_abi("eth", "strategy")
    )

    logger.info("-------------------------------------------")
    logger.info("DIGG SLP")
    logger.info(
        {
            "want": strategy.functions.want().call(),
            "strategy": ETH_DIGG_SUSHI_LP_STRATEGY,
            "total_amount": fragments,
            "days": days_since,
            "swap": {
                "token0": DIGG_TOKEN,
                "amount": fragments // 2,
                "path": [DIGG_TOKEN, WBTC_TOKEN],
            },
        }
    )

    # BADGER SUSHI
    days_since = eharvester.days_since_last_harvest(ETH_BADGER_SUSHI_LP_STRATEGY)
    last_harvest = eharvester.last_harvest_times[ETH_BADGER_SUSHI_LP_STRATEGY]
    amount_owed = Decimal(
        eharvester.get_amount_badger_owed(last_harvest, ETH_BADGER_SUSHI_LP_VAULT)
        * 1e18
    )
    strategy = node.eth.contract(
        address=ETH_BADGER_SUSHI_LP_STRATEGY, abi=get_abi("eth", "strategy")
    )

    logger.info("-------------------------------------------")
    logger.info("BADGER SLP")
    logger.info(
        {
            "want": strategy.functions.want().call(),
            "strategy": ETH_BADGER_SUSHI_LP_STRATEGY,
            "total_amount": str(amount_owed),
            "days": days_since,
            "swap": {
                "token0": BADGER_TOKEN,
                "amount": amount_owed // 2,
                "path": [BADGER_TOKEN, WBTC_TOKEN],
            },
        }
    )

    # BADGER UNI
    days_since = eharvester.days_since_last_harvest(ETH_BADGER_UNI_LP_STRATEGY)
    last_harvest = eharvester.last_harvest_times[ETH_BADGER_UNI_LP_STRATEGY]
    amount_owed = Decimal(
        eharvester.get_amount_badger_owed(last_harvest, ETH_BADGER_UNI_LP_VAULT) * 1e18
    )
    strategy = node.eth.contract(
        address=ETH_BADGER_UNI_LP_STRATEGY, abi=get_abi("eth", "strategy")
    )

    logger.info("-------------------------------------------")
    logger.info("BADGER UNI LP")
    logger.info(
        {
            "want": strategy.functions.want().call(),
            "strategy": ETH_BADGER_UNI_LP_STRATEGY,
            "total_amount": str(amount_owed),
            "days": days_since,
            "swap": {
                "token0": BADGER_TOKEN,
                "amount": amount_owed // 2,
                "path": [BADGER_TOKEN, WBTC_TOKEN],
            },
        }
    )
