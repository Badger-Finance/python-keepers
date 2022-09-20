import time

from eth_account.account import Account
from flashbots import flashbot

from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import ETH_KEEPER_ACL
from config.enums import Network
from src.aws import get_secret
from src.general_harvester import GeneralHarvester
from src.json_logger import logger
from src.utils import get_abi
from src.utils import get_healthy_node

strategies = {}


def safe_harvest(harvester, strategy_name, strategy) -> str:
    logger.info(f"HARVESTING strategy {strategy.address}")
    try:
        harvester.harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvest: {e}")

    logger.info("Trying to run harvestNoReturn")
    try:
        harvester.harvest_no_return(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} harvestNoReturn: {e}")

    logger.info("Tend first, then harvest")
    try:
        harvester.tend_then_harvest(strategy)
        return "Success!"
    except Exception as e:
        logger.error(f"Error running {strategy_name} tend_then_harvest: {e}")


if __name__ == "__main__":
    # Load secrets
    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    web3 = get_healthy_node(Network.Ethereum)
    flashbots_signer = Account.from_key(
        get_secret("keepers/flashbots/test-signer", "FLASHBOTS_SIGNER_KEY")
    )

    # Account which signifies your identify to flashbots network
    flashbot(web3, flashbots_signer)

    harvester = GeneralHarvester(
        web3=web3,
        keeper_acl=ETH_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        use_flashbots=False,
    )

    for strategy_address in strategies:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Ethereum, "strategy"),
        )
        strategy_name = strategy.functions.getName().call()

        logger.info(f"+-----Harvesting {strategy_name}-----+")
        safe_harvest(harvester, strategy_name, strategy)

        # Sleep for 2 blocks in between harvests
        time.sleep(30)
