import logging
import os
import sys
import time
from eth_account.account import Account
from flashbots import flashbot
from pathlib import Path
from web3 import Web3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret, hours
from tx_utils import get_latest_base_fee

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"

CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
CVX_CRV_HELPER_STRATEGY = "0x826048381d65a65DAa51342C51d464428d301896"

strategies = {
    "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95",  # CVX_HELPER_STRATEGY
    "0x826048381d65a65DAa51342C51d464428d301896",  # CVX_CRV_HELPER_STRATEGY
    "0xff26f400e57bf726822eacbb64fa1c52f1f27988",  # HBTC_CRV_STRATEGY
    "0x1C1fD689103bbFD701b3B7D41A3807F12814033D",  # PBTC_CRV_STRATEGY
    "0x2bb864cdb4856ab2d148c5ca52dd7ccec126d138",  # OBTC_CRV_STRATEGY
    "0x4f3e7a4566320b2709fd1986f2e9f84053d3e2a0",  # BBTC_CRV_STRATEGY
    "0x2eB6479c2f033360C0F4575A88e3b8909Cbc6a03",  # TRICRYPTO_CRV_STRATEGY
    # "0x75b8E21BD623012Efb3b69E1B562465A68944eE6",  # native.badger
    "0x6582a5b139fc1c6360846efdc4440d51aad4df7b",  # native.renCrv
    "0xf1ded284e891943b3e9c657d7fc376b86164ffc2",  # native.sbtcCrv
    "0x522bb024c339a12be1a47229546f288c40b62d29",  # native.tbtcCrv
    # "0x95826C65EB1f2d2F0EDBb7EcB176563B61C60bBf",  # native.uniBadgerWbtc
    "0xaaE82E3c89e15E6F26F60724f115d5012363e030",  # harvest.renCrv
    "0x7A56d65254705B4Def63c68488C0182968C452ce",  # native.sushiWbtcEth
    "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1",  # native.sushiBadgerWbtc
    # "0x4a8651F2edD68850B944AD93f2c67af817F39F62",  # native.digg
    # "0xadc8d7322f2E284c1d9254170dbe311E9D3356cf",  # native.uniDiggWbtc
    "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a",  # native.sushiDiggWbtc
    "0xf4146A176b09C664978e03d28d07Db4431525dAd",  # experimental.sushiIBbtcWbtc
    # "0xA6af1B913E205B8E9B95D3B30768c0989e942316",  # experimental.digg
    "0x3406402caE1f745714a9aFFc45939854e7Fbe12B",  # locked cvx vault
}


def conditional_harvest(harvester, strategy_name, strategy) -> str:
    latest_base_fee = get_latest_base_fee(harvester.web3)

    hours_24 = hours(24)
    hours_48 = hours(48)
    hours_60 = hours(60)
    # separate check for cvx helpers
    if (
        strategy.address == CVX_CRV_HELPER_STRATEGY
        and harvester.is_time_to_harvest(strategy, hours_24)
        and latest_base_fee < int(100e9)
    ):
        logger.info(f"Been longer than 24 hours and base fee < 100 for {strategy_name}")
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)

    if (
        strategy.address == CVX_HELPER_STRATEGY
        and harvester.is_time_to_harvest(strategy, hours_24)
        and latest_base_fee < int(80e9)
    ):
        logger.info(f"Been longer than 24 hours and base fee < 80 for {strategy_name}")
        res = safe_harvest(harvester, strategy_name, strategy)
        logger.info(res)

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
    elif harvester.is_time_to_harvest(strategy):
        logger.info(
            f"Been longer than 71 hours harvest no matter what for {strategy_name}"
        )
        res = safe_harvest(harvester, strategy_name, strategy)
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


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "NODE_URL")
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
            abi=get_abi("eth", "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        conditional_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)
