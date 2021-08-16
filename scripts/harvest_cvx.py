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
CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
CVX_CRV_HELPER_STRATEGY = "0x826048381d65a65DAa51342C51d464428d301896"
HBTC_CRV_STRATEGY = "0xff26f400e57bf726822eacbb64fa1c52f1f27988"
PBTC_CRV_STRATEGY = "0x1C1fD689103bbFD701b3B7D41A3807F12814033D"
OBTC_CRV_STRATEGY = "0x2bb864cdb4856ab2d148c5ca52dd7ccec126d138"
BBTC_CRV_STRATEGY = "0x4f3e7a4566320b2709fd1986f2e9f84053d3e2a0"
TRICRYPTO_CRV_STRATEGY = "0x05ec4356e1acd89cc2d16adc7415c8c95e736ac1"


def safe_harvest(harvester, strategy_name, strategy):
    try:
        harvester.harvest(strategy)
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "NODE_URL")
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )
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
        use_flashbots=True,
    )

    for strategy_address in [
        #CVX_CRV_HELPER_STRATEGY,
        #CVX_HELPER_STRATEGY,
        HBTC_CRV_STRATEGY,
        PBTC_CRV_STRATEGY,
        OBTC_CRV_STRATEGY,
        BBTC_CRV_STRATEGY,
        TRICRYPTO_CRV_STRATEGY,
    ]:
        strategy = web3.eth.contract(
            address=strategy_address, abi=get_abi("eth", "strategy")
        )
        strategy_name = strategy.functions.getName().call()

        logger.info(f"+-----Harvesting {strategy_name}-----+")
        safe_harvest(harvester, strategy_name, strategy)

        # Sleep for a minute in between harvests
        time.sleep(60)
