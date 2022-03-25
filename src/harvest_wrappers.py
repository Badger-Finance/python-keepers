import logging

from web3.contract import Contract

from src.general_harvester import GeneralHarvester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# TODO: Reuse this in all harvest scripts
def safe_harvest(harvester: GeneralHarvester, strategy: Contract) -> str:
    try:
        strategy_name = strategy.functions.getName().call()
        logger.info(f"+-----Harvesting {strategy_name} {strategy.address}-----+")
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running harvest: {e}")
    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running tend_then_harvest: {e}")
