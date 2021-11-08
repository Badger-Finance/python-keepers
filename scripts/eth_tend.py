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

from general_harvester import GeneralHarvester
from utils import get_abi, get_secret
from enums import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"

strategies = [
    ####################### New Strategies #########################
    # "0xe66dB6Eb807e6DAE8BD48793E9ad0140a2DEE22A",  # renBTC/wBTC
    # "0x2f278515425c8eE754300e158116930B8EcCBBE1",  # renBTC/wBTC/sBTC
    # "0x9e0742EE7BECde52A5494310f09aad639AA4790B",  # tBTC/sbtcCrv
    # "0x7354D5119bD42a77E7162c8Afa8A1D18d5Da9cF8",  # hBTC/wBTC
    # "0x3f98F3a21B125414e4740316bd6Ef14718764a22",  # pBTC/sbtcCRV
    "0x50Dd8A61Bdd11Cf5539DAA83Bc8E0F581eD8110a",  # oBTC/sbtcCRV
    # "0xf92660E0fdAfE945aa13616428c9fB4BE19f4d34",  # bBTC/sbtcCRV
    # "0xf3202Aa2783F3DEE24a35853C6471db065B05D37",  # USD-BTC-ETH
    # "0xf6D442Aead5960b283281A794B3e7d3605601247",  # Convex CRV
    # "0xc67129cf19BB00d60CC5CF62398fcA3A4Dc02a14",  # Convex Token
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
            abi=get_abi(Network.Ethereum, "strategy"),
        )

        if strategy.functions.isTendable().call():
            strategy_name = strategy.functions.getName().call()

            logger.info(f"+-----Tending {strategy_name}-----+")
            safe_tend(harvester, strategy_name, strategy)

            # Sleep for 2 blocks in between tends
            time.sleep(30)
