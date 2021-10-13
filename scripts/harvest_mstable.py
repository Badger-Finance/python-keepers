import logging
import os
import sys
import time
from pathlib import Path
from web3 import Web3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret, hours, get_last_harvest_times
from tx_utils import get_latest_base_fee

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"

MSTABLE_VOTER_PROXY = "0x10D96b1Fd46Ce7cE092aA905274B8eD9d4585A6E"

MSTABLE_STRATEGIES = {
    "0x54D06A0E1cE55a7a60Ee175AbCeaC7e363f603f3",  # mBTC/hBTC mstable
    "0xd409C506742b7f76f164909025Ab29A47e06d30A",  # ibmBTC mstable
}


def conditional_harvest(harvester, strategy_name, strategy) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)

    hours_48 = hours(48)
    hours_60 = hours(60)
    # regular thresholds for rest of vaults
    if harvester.is_time_to_harvest(strategy, hours_48) and latest_base_fee < int(80e9):
        logger.info(f"Been longer than 48 hours and base fee < 80 for {strategy_name}")
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)
    elif harvester.is_time_to_harvest(strategy, hours_60) and latest_base_fee < int(
        100e9
    ):
        logger.info(f"Been longer than 60 hours and base fee < 100 for {strategy_name}")
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)
    elif harvester.is_time_to_harvest(strategy) and latest_base_fee < int(150e9):
        logger.info(
            f"Been longer than 71 hours harvest no matter what for {strategy_name}"
        )
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)


def safe_harvest_mta(harvester, voter_proxy) -> str:
    logger.info(f"+-----Calling harvestMta {voter_proxy}-----+")

    try:
        harvester.harvest_mta(voter_proxy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {voter_proxy} harvestMta: {e}")


def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")

    try:
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} tend_then_harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "NODE_URL")
    discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")

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

    # Call harvestMta before harvesting strategies
    voter_proxy = web3.eth.contract(
        address=web3.toChecksumAddress(MSTABLE_VOTER_PROXY),
        abi=get_abi("eth", "mstable_voter_proxy"),
    )
    safe_harvest_mta(harvester, voter_proxy)
    # Sleep for 2 blocks before harvesting
    time.sleep(30)

    for strategy_address in MSTABLE_STRATEGIES:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi("eth", "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        conditional_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)
