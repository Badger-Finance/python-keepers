import logging
import os
import sys

from time import sleep


from config.enums import Network
from src.rebaser import Rebaser
from src.utils import get_secret, get_node_url

logging.basicConfig(level=logging.INFO)


def safe_rebase(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_node_url(Network.Ethereum)

    rebaser = Rebaser(
        keeper_address=keeper_address, keeper_key=keeper_key, web3=node_url
    )

    logger.info("+-----REBASING DIGG-----+")
    rebaser.rebase()
