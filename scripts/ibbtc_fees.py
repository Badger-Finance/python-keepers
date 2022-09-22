import sys

from config.enums import Network
from src.aws import get_secret
from src.ibbtc_fee_collector import ibBTCFeeCollector
from src.json_logger import exception_logging
from src.json_logger import logger
from src.utils import get_healthy_node

sys.excepthook = exception_logging


if __name__ == "__main__":
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    web3 = get_healthy_node(Network.Ethereum)

    collector = ibBTCFeeCollector(
        keeper_address=keeper_address, keeper_key=keeper_key, web3=web3
    )

    logger.info("+-----Checking if we should collect ibBTC fees-----+")
    collector.collect_fees()
