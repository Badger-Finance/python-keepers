import logging
import os
import sys
from time import sleep, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from oracle import Oracle
from utils import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger()
    logger.info(f"INVOKED AT {time()}")

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("price-bots/infura-url", "INFURA_URL")

    oracle = Oracle(keeper_address=keeper_address, keeper_key=keeper_key, web3=node_url)

    logger.info("+-----Proposing 24 hour TWAP to market oracle-----+")
    oracle.propose_centralized_report_push()