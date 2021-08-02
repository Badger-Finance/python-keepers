import logging
import os
import sys
from time import sleep

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from cvx_harvester import CvxHarvester

logging.basicConfig(level=logging.INFO)

CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()

    while True:

        harvester = CvxHarvester()

        logger.info("+-----Harvesting CVX Helper-----+")
        safe_harvest(harvester, "CVX Helper", CVX_HELPER_STRATEGY)

        sleep(30 * 60)

