import logging

from config.enums import Network
from src.ibbtc_fee_collector import ibBTCFeeCollector
from src.utils import get_node_url
from src.utils import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    node_url = get_node_url(Network.Ethereum)

    collector = ibBTCFeeCollector(
        keeper_address=keeper_address, keeper_key=keeper_key, web3=node_url
    )

    logger.info("+-----Checking if we should collect ibBTC fees-----+")
    collector.collect_fees()
