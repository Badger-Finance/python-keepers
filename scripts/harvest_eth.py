import logging
import os
import sys
import time
from eth_account.account import Account
from flashbots import flashbot
from pathlib import Path
from web3 import Web3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)

from enums import Network
from constants import MULTICHAIN_CONFIG
from general_harvester import GeneralHarvester
from utils import (
    get_abi,
    get_secret,
    hours,
    get_last_harvest_times,
    seconds_to_blocks,
    get_node_url,
)
from tx_utils import get_latest_base_fee

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

HOURS_24 = hours(24)
HOURS_72 = hours(72)
HOURS_96 = hours(96)
HOURS_120 = hours(120)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"

CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
CVX_CRV_HELPER_STRATEGY = "0x826048381d65a65DAa51342C51d464428d301896"
IBBTC_CRV_STRATEGY = "0x6D4BA00Fd7BB73b5aa5b3D6180c6f1B0c89f70D1"

MSTABLE_VOTER_PROXY = "0x10D96b1Fd46Ce7cE092aA905274B8eD9d4585A6E"

strategies = [
    IBBTC_CRV_STRATEGY,
    # "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95",  # CVX_HELPER_STRATEGY
    "0x826048381d65a65DAa51342C51d464428d301896",  # CVX_CRV_HELPER_STRATEGY
    "0x8c26D9B6B80684CC642ED9eb1Ac1729Af3E819eE",  # HBTC_CRV_STRATEGY
    # "0xA9A646668Df5Cec5344941646F5c6b269551e53D",  # PBTC_CRV_STRATEGY
    "0x5dd69c6D81f0a403c03b99C5a44Ef2D49b66d388",  # OBTC_CRV_STRATEGY
    # "0xF2F3AB09E2D8986fBECbBa59aE838a5418a6680c",  # BBTC_CRV_STRATEGY
    "0x647eeb5C5ED5A71621183f09F6CE8fa66b96827d",  # TRICRYPTO_CRV_STRATEGY
    "0x61e16b46F74aEd8f9c2Ec6CB2dCb2258Bdfc7071",  # native.renCrv
    # "0xCce0D2d1Eb2310F7e67e128bcFE3CE870A3D3a3d",  # native.sbtcCrv
    "0xAB73Ec65a1Ef5a2e5b56D5d6F36Bee4B2A1D3FFb",  # native.tbtcCrv
    "0xaaE82E3c89e15E6F26F60724f115d5012363e030",  # harvest.renCrv
    "0x7A56d65254705B4Def63c68488C0182968C452ce",  # native.sushiWbtcEth
    "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1",  # native.sushiBadgerWbtc
    "0xf4146A176b09C664978e03d28d07Db4431525dAd",  # experimental.sushiIBbtcWbtc
    # "0xA6af1B913E205B8E9B95D3B30768c0989e942316",  # experimental.digg
    "0x3ff634ce65cDb8CC0D569D6d1697c41aa666cEA9",  # locked cvx strategy
]

rewards_manager_strategies = {
    "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a",  # native.sushiDiggWbtc
    "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1",  # native.sushiBadgerWbtc
    # "0x4a8651F2edD68850B944AD93f2c67af817F39F62",  # native.digg
    # "0xadc8d7322f2E284c1d9254170dbe311E9D3356cf",  # native.uniDiggWbtc
    # "0x95826C65EB1f2d2F0EDBb7EcB176563B61C60bBf",  # native.uniBadgerWbtc
    # "0x75b8E21BD623012Efb3b69E1B562465A68944eE6",  # native.badger
}

mstable_strategies = {
    "0x54D06A0E1cE55a7a60Ee175AbCeaC7e363f603f3",  # mBTC/hBTC mstable
    "0xd409C506742b7f76f164909025Ab29A47e06d30A",  # ibmBTC mstable
}


def conditional_harvest(harvester, strategy_name, strategy) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)
    logger.info(f"Checking harvests for {strategy_name} {strategy.address}")
    # ibbtc exception
    if (
        strategy.address == IBBTC_CRV_STRATEGY
        and harvester.is_time_to_harvest(strategy, HOURS_72)
        and latest_base_fee < int(120e9)
    ):
        logger.info(f"Been longer than 72 hours and base fee < 120 for {strategy_name}")
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)
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
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
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

    # Mstable harvests
    # Call harvestMta before harvesting strategies
    voter_proxy = web3.eth.contract(
        address=web3.toChecksumAddress(MSTABLE_VOTER_PROXY),
        abi=get_abi(Network.Ethereum, "mstable_voter_proxy"),
    )
    conditional_harvest_mta(harvester, voter_proxy)
    # Sleep for 2 blocks before harvesting
    time.sleep(30)

    # TODO: Check if it's fine if harvestMta and harvests go out of sync
    for strategy_address in mstable_strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Ethereum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        conditional_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)

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
