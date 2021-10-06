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

from earner import Earner
from utils import get_secret, get_strategies_and_vaults, get_abi
from constants import MULTICHAIN_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eth-external-harvest")

DIGG_TOKEN = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
BDIGG_BTCB_STRATEGY = "0xC8C53A293edca5a0146d713b9b95b0cd0a2e5ca4"
BNB_BTCB_STRATEGY = "0x120BB9F87bAB3C49b89c7745eDC07FED50786534"


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


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    node = Web3(Web3.HTTPProvider(os.getenv("ETH_NODE_URL")))

    logger.info("now badger time")
    badger_schedule_amt = 2300
