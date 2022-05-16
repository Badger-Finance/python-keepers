import logging

from config.enums import Network
from src.aws import get_secret
from src.rebaser import Rebaser
from src.utils import get_healthy_node

logging.basicConfig(level=logging.INFO)


def safe_rebase(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    web3 = get_healthy_node(Network.Ethereum)

    rebaser = Rebaser(
        keeper_address=keeper_address, keeper_key=keeper_key, web3=web3
    )

    logger.info("+-----REBASING DIGG-----+")
    rebaser.rebase()
