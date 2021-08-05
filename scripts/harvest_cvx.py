import logging
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/eth"))
)

from cvx_harvester import CvxHarvester
from utils import get_secret

logging.basicConfig(level=logging.INFO)

KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"
CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"


def safe_harvest(harvester, sett_name, keeper_acl, strategy):
    try:
        harvester.harvest(sett_name, keeper_acl, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_secret("quiknode/eth-node-url", "ETH_NODE_URL")

    harvester = CvxHarvester(
        keeper_address=keeper_address, keeper_key=keeper_key, node_url=node_url
    )

    logger.info("+-----Harvesting CVX Helper-----+")
    safe_harvest(harvester, "CVX Helper", KEEPER_ACL, CVX_HELPER_STRATEGY)
