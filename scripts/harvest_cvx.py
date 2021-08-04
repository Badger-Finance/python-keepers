import logging
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/eth"))
)

from cvx_harvester import CvxHarvester
from utils import get_secret

logging.basicConfig(level=logging.INFO)

CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "ETH_NODE_URL")

    harvester = CvxHarvester(
        keeper_address=keeper_address, keeper_key=keeper_key, web3=node_url
    )

    logger.info("+-----Harvesting CVX Helper-----+")
    safe_harvest(harvester, "CVX Helper", CVX_HELPER_STRATEGY)
