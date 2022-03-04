import logging
import os
import sys
import time

from eth_account.account import Account
from flashbots import flashbot
from pathlib import Path
from web3 import Web3


from config.enums import Network
from src.general_harvester import GeneralHarvester
from src.utils import get_abi, get_secret, get_node_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(Path(__file__).name)

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"

STRATEGIES = {
    # New strategies
    "native.renCrv": "0x61e16b46F74aEd8f9c2Ec6CB2dCb2258Bdfc7071",
    "native.sbtcCrv": "0xCce0D2d1Eb2310F7e67e128bcFE3CE870A3D3a3d",
    "native.tbtcCrv": "0xAB73Ec65a1Ef5a2e5b56D5d6F36Bee4B2A1D3FFb",
    "native.hbtcCrv": "0x8c26D9B6B80684CC642ED9eb1Ac1729Af3E819eE",
    "native.pbtcCrv": "0xA9A646668Df5Cec5344941646F5c6b269551e53D",
    "native.obtcCrv": "0x5dd69c6D81f0a403c03b99C5a44Ef2D49b66d388",
    "native.bbtcCrv": "0xF2F3AB09E2D8986fBECbBa59aE838a5418a6680c",
    "native.tricrypto2": "0x647eeb5C5ED5A71621183f09F6CE8fa66b96827d",
}


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
    node_url = get_node_url(Network.Ethereum)

    web3 = Web3(Web3.HTTPProvider(node_url))

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=False,
    )

    for strategy_address in STRATEGIES.values():
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
