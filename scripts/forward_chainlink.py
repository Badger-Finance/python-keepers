import logging
from time import time

from config.enums import Network
from src.oracle import Oracle
from src.utils import get_healthy_node
from src.aws import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)
    logger.info(f"INVOKED AT {time()}")

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    web3 = get_healthy_node(Network.Ethereum)

    oracle = Oracle(keeper_address=keeper_address, keeper_key=keeper_key, web3=web3)

    if not oracle.is_negative_rebase():
        logger.info("+-----Forwarding ChainLink price to market oracle-----+")
        oracle.publish_chainlink_report()
    else:
        logger.info("SKIPPING: negative rebase")
