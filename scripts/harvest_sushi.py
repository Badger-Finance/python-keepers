import logging
import os
import sys
from time import sleep

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from strategies import eth_strategies
from eth.sushi_harvester import SushiHarvester

logging.basicConfig(level=logging.INFO)

BADGER_WBTC_STRATEGY = eth_strategies["WBTC_BADGER_STRATEGY"]
DIGG_WBTC_STRATEGY = eth_strategies["WBTC_DIGG_STRATEGY"]
ETH_WBTC_STRATEGY = eth_strategies["WBTC_ETH_STRATEGY"]


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()

    while True:

        harvester = SushiHarvester()

        logger.info("+-----Harvesting BADGER WBTC LP-----+")
        safe_harvest(harvester, "BADGER WBTC LP", BADGER_WBTC_STRATEGY)

        logger.info("+-----Harvesting DIGG WBTC LP-----+")
        safe_harvest(harvester, "DIGG WBTC LP", DIGG_WBTC_STRATEGY)

        logger.info("+-----Harvesting ETH WBTC LP-----+")
        safe_harvest(harvester, "ETH WBTC LP", ETH_WBTC_STRATEGY)

        sleep(30 * 60)
