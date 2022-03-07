import logging
from time import time

from src.oracle import Oracle
from src.utils import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)
    logger.info(f"INVOKED AT {time()}")

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("price-bots/infura-url", "INFURA_URL")

    oracle = Oracle(keeper_address=keeper_address, keeper_key=keeper_key, web3=node_url)

    logger.info("+-----Approving 24 hour TWAP to market oracle-----+")
    oracle.approve_centralized_report_push()
