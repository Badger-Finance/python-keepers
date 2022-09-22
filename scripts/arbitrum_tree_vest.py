import sys

from config.constants import ARB_ETH_USD_CHAINLINK
from config.constants import ARB_VESTER_Q2_22
from config.enums import Network
from src.aws import get_secret
from src.json_logger import exception_logging
from src.json_logger import logger
from src.utils import get_healthy_node
from src.vester import Vester

sys.excepthook = exception_logging


if __name__ == "__main__":
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    discord_url = get_secret(
        "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
    )
    web3 = get_healthy_node(Network.Arbitrum)

    vester = Vester(
        web3,
        Network.Arbitrum,
        discord_url,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ARB_ETH_USD_CHAINLINK,
        vesting_contract_address=ARB_VESTER_Q2_22,
    )

    logger.info("+-----Sending vested Badger to tree on Arbitrum-----+")
    vester.vest()
