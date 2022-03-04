import logging
import os
import sys

from time import sleep

from src.eth.sushi_harvester import SushiHarvester

logging.basicConfig(level=logging.INFO)

BADGER_WBTC_STRATEGY = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
DIGG_WBTC_STRATEGY = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
ETH_WBTC_STRATEGY = "0x7A56d65254705B4Def63c68488C0182968C452ce"


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
