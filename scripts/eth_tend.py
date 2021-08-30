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
from utils import get_abi, get_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"

strategies = [
    # "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95",  # CVX_HELPER_STRATEGY
    # "0x826048381d65a65DAa51342C51d464428d301896",  # CVX_CRV_HELPER_STRATEGY
    "0xff26f400e57bf726822eacbb64fa1c52f1f27988",  # HBTC_CRV_STRATEGY
    "0x1C1fD689103bbFD701b3B7D41A3807F12814033D",  # PBTC_CRV_STRATEGY
    "0x2bb864cdb4856ab2d148c5ca52dd7ccec126d138",  # OBTC_CRV_STRATEGY
    "0x4f3e7a4566320b2709fd1986f2e9f84053d3e2a0",  # BBTC_CRV_STRATEGY
    "0x05ec4356e1acd89cc2d16adc7415c8c95e736ac1",  # TRICRYPTO_CRV_STRATEGY
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
]


def safe_tend(harvester, strategy_name, strategy) -> str:
    logger.info(f"strategy address at {strategy.address}")
    try:
        harvester.tend(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} tend: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "NODE_URL")

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=False,
    )

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi("eth", "strategy"),
        )

        if strategy.functions.isTendable().call():
            strategy_name = strategy.functions.getName().call()

            logger.info(f"+-----Tending {strategy_name}-----+")
            safe_tend(harvester, strategy_name, strategy)

            # Sleep for 2 blocks in between tends
            time.sleep(30)