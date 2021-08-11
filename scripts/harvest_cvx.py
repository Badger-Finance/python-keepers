import logging
import os
import sys
from eth_account.account import Account
from flashbots import flashbot
from web3 import Web3

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/eth"))
)

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret

logging.basicConfig(level=logging.INFO)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"
CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
CVX_CRV_HELPER_STRATEGY = "0x826048381d65a65DAa51342C51d464428d301896"


def safe_harvest(harvester, strategy_name, strategy):
    try:
        harvester.harvest(strategy)
    except Exception as e:
        logging.error(f"Error running {strategy_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()

    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "NODE_URL")
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )

    web3 = Web3(Web3.HTTPProvider(node_url))

    # Account which signifies your identify to flashbots network
    flashbot(web3, flashbots_signer)

    harvester = GeneralHarvester(
        web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=True,
    )

    for strategy_address in [CVX_HELPER_STRATEGY, CVX_CRV_HELPER_STRATEGY]:
        strategy = web3.eth.contract(
            address=strategy_address, abi=get_abi("eth", "strategy")
        )
        strategy_name = strategy.functions.getName().call()

        logger.info(f"+-----Harvesting {strategy_name}-----+")
        safe_harvest(harvester, strategy_name, strategy)
