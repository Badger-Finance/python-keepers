import logging
import os
import sys
from time import sleep

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/bsc")))

from cake_harvester import CakeHarvester

logging.basicConfig(level=logging.INFO)

BBADGER_BTCB_STRATEGY = "0x2A842e01724F10d093aE8a46A01e66DbCf3C7373"
BDIGG_BTCB_STRATEGY = "0xC8C53A293edca5a0146d713b9b95b0cd0a2e5ca4"
BNB_BTCB_STRATEGY = "0x120BB9F87bAB3C49b89c7745eDC07FED50786534"


def safe_harvest(harvester, sett_name, strategy):
    try:
        harvester.harvest(sett_name, strategy)
    except Exception as e:
        logging.error(f"Error running {sett_name} harvest: {e}")


if __name__ == "__main__":

    logger = logging.getLogger()
    
    while True:

        harvester = CakeHarvester()

        logger.info("+-----Harvesting BBADGER BTCB LP-----+")
        safe_harvest(harvester, "BBADGER BTCB LP", BBADGER_BTCB_STRATEGY)

        logger.info("+-----Harvesting BDIGG BTCB LP-----+")
        safe_harvest(harvester, "BDIGG BTCB LP", BDIGG_BTCB_STRATEGY)

        logger.info("+-----Harvesting BNB BTCB LP-----+")
        safe_harvest(harvester, "BNB BTCB LP", BNB_BTCB_STRATEGY)

        sleep(30*60)
