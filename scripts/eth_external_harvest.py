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

from earner import Earner
from utils import get_secret, get_strategies_and_vaults, get_abi
from constants import MULTICHAIN_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eth-external-harvest")

DIGG_TOKEN = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
BADGER_TOKEN = "0x3472A5A71965499acd81997a54BBA8D852C6E53d"
WBTC_TOKEN = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"


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

    amount_badger = node.toWei(2300, "ether")

    # badger_schedule_amt = 2300
    logger.info("bDIGG")
    calculate_retroactive_digg(2.5, 2)
    logger.info("bBADGER")
    emitted_badger = calculate_retroactive_badger(amount_badger, 4)

    # lp strat

    # calculte retroactive reward amount

    # swap retroactive amount / 2 for wbtc

    # addLiquiditySushiswap or Uniswap(rtoken_address, want_address)
    # transfer balanceOf(want) to pool
    logger.info("slp wbtc / digg")
    full_amount = calculate_retroactive_digg(10, 12)
    logger.info(f"amount to swap: {full_amount // 2}")

    logger.info("lp wbtc / badger")
    amount_badger = node.toWei(4600, "ether")
    emitted_badger1 = calculate_retroactive_badger(amount_badger, 9)
    amount_badger = node.toWei(4565, "ether")
    emitted_badger2 = calculate_retroactive_badger(amount_badger, 1)
    logger.info(
        f"amount to swap: {Decimal(Decimal(emitted_badger1 + emitted_badger2) // 2)}"
    )

{
    "want": "0x798d1be841a82a273720ce31c822c61a67a601c3",
    "strategy": "0x4a8651F2edD68850B944AD93f2c67af817F39F62",
    "amount": 92649023,
}

{"token0": DIGG_TOKEN, "amount": 1111788282, "path": [DIGG_TOKEN, WBTC_TOKEN]}
