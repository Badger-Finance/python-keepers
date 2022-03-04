import logging
import os
import sys
import time

from eth_account.account import Account
from flashbots import flashbot
from pathlib import Path
from web3 import Web3

from config.constants import (
    MULTICHAIN_CONFIG,
    ETH_ETH_USD_CHAINLINK,
    ETH_KEEPER_ACL,
    ETH_CVX_HELPER_STRATEGY,
    ETH_CVX_CRV_HELPER_STRATEGY,
    ETH_IBBTC_CRV_STRATEGY,
    ETH_BVECVX_STRATEGY,
    ETH_TRICRYPTO_STRATEGY,
    ETH_TBTC_CRV_STRATEGY,
    ETH_RENBTC_CRV_STRATEGY,
    ETH_SLP_BADGER_WBTC_STRATEGY,
    ETH_SLP_DIGG_WBTC_STRATEGY,
)
from config.enums import Network
from src.general_harvester import GeneralHarvester
from src.utils import (
    get_abi,
    get_secret,
    hours,
    get_last_harvest_times,
    seconds_to_blocks,
    get_node_url,
)
from src.tx_utils import get_latest_base_fee

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

HOURS_24 = hours(24)
HOURS_72 = hours(72)
HOURS_96 = hours(96)
HOURS_120 = hours(120)

strategies = [
    ETH_IBBTC_CRV_STRATEGY,
    ETH_CVX_CRV_HELPER_STRATEGY,
    ETH_BVECVX_STRATEGY,
    ETH_TRICRYPTO_STRATEGY,
    ETH_TBTC_CRV_STRATEGY,
    ETH_RENBTC_CRV_STRATEGY,
]

rewards_manager_strategies = {ETH_SLP_BADGER_WBTC_STRATEGY, ETH_SLP_DIGG_WBTC_STRATEGY}


def conditional_harvest(harvester, strategy_name, strategy) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)
    logger.info(f"Checking harvests for {strategy_name} {strategy.address}")
    # regular thresholds for rest of vaults
    if harvester.is_time_to_harvest(strategy, HOURS_96) and latest_base_fee < int(80e9):
        logger.info(f"Been longer than 96 hours and base fee < 80 for {strategy_name}")
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)
    elif harvester.is_time_to_harvest(strategy) and latest_base_fee < int(150e9):
        logger.info(
            f"Been longer than 120 hours harvest no matter what for {strategy_name}"
        )
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)


def conditional_harvest_rewards_manager(harvester, strategy_name, strategy) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)

    # regular thresholds for rest of vaults
    if harvester.is_time_to_harvest(strategy, HOURS_96) and latest_base_fee < int(80e9):
        logger.info(f"Been longer than 96 hours and base fee < 80 for {strategy_name}")
        logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
        try:
            harvester.harvest_rewards_manager(strategy)
        except Exception as e:
            logger.error(f"Error running {strategy_name} harvest: {e}")
    elif harvester.is_time_to_harvest(strategy) and latest_base_fee < int(150e9):
        logger.info(
            f"Been longer than 120 hours harvest no matter what for {strategy_name}"
        )
        logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
        try:
            harvester.harvest_rewards_manager(strategy)
        except Exception as e:
            logger.error(f"Error running {strategy_name} harvest: {e}")


def conditional_harvest_mta(harvester, voter_proxy) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)

    if harvester.is_time_to_harvest(voter_proxy, HOURS_96) and latest_base_fee < int(
        80e9
    ):
        logger.info(f"Been longer than 96 hours and base fee < 80 since harvestMta")
        res = safe_harvest_mta(harvester, voter_proxy)
        logger.info(res)
    elif harvester.is_time_to_harvest(voter_proxy) and latest_base_fee < int(150e9):
        logger.info(
            f"Been longer than 120 hours harvest no matter what since harvestMta"
        )
        res = safe_harvest_mta(harvester, voter_proxy)
        logger.info(res)


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


def safe_harvest_mta(harvester, voter_proxy) -> str:
    logger.info(f"+-----Calling harvestMta {voter_proxy}-----+")

    try:
        harvester.harvest_mta(voter_proxy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {voter_proxy} harvestMta: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    # node_url = get_node_url(Network.Ethereum)
    node_url = "https://rpc.flashbots.net"
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )
    discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")
    # flashbots_signer = Account.create()

    web3 = Web3(Web3.HTTPProvider(node_url))

    # Account which signifies your identify to flashbots network
    flashbot(web3, flashbots_signer)

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=ETH_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        use_flashbots=False,
        discord_url=discord_url,
    )

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Ethereum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        conditional_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)

    rewards_manager = harvester.web3.eth.contract(
        address=harvester.web3.toChecksumAddress(
            MULTICHAIN_CONFIG[harvester.chain]["rewards_manager"]
        ),
        abi=get_abi(harvester.chain, "rewards_manager"),
    )

    # This should be done after mstable since it removes keeper acl harvest times
    harvester.last_harvest_times = get_last_harvest_times(
        harvester.web3,
        rewards_manager,
        start_block=harvester.web3.eth.block_number - seconds_to_blocks(HOURS_120),
    )

    for strategy_address in rewards_manager_strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Ethereum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        conditional_harvest_rewards_manager(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)
