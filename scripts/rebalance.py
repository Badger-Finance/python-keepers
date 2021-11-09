import logging
import os
import sys
from eth_account.account import Account
from flashbots import flashbot
from pathlib import Path
from web3 import Web3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../config"))
)
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/eth"))
)

from utils import get_secret, get_abi, get_node_url
from constants import NODE_URL_SECRET_NAMES
from enums import Network
from rebalancer import Rebalancer

logging.basicConfig(level=logging.INFO)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"
STABILIZE_STRAT = "0xA6af1B913E205B8E9B95D3B30768c0989e942316"

if __name__ == "__main__":

    logger = logging.getLogger("script")

    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_node_url(Network.Ethereum)
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )
    # flashbots_signer = Account.create()

    web3 = Web3(Web3.HTTPProvider(node_url))

    strategy = web3.eth.contract(
        address=STABILIZE_STRAT, abi=get_abi(Network.Ethereum, "stability_strat")
    )

    rebalancer = Rebalancer(
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=False,
    )

    logger.info("+-----REBALANCING DIGG STABILITY SETT-----+")
    rebalancer.rebalance(strategy)
