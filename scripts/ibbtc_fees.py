import logging
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
)

from ibbtc_fee_collector import ibBTCFeeCollector
from utils import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger()

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("price-bots/infura-url", "INFURA_URL")

    collector = ibBTCFeeCollector(
        keeper_address=keeper_address, keeper_key=keeper_key, web3=node_url
    )

    logger.info("+-----Checking if we should collect ibBTC fees-----+")
    collector.collect_fees()

