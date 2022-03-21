import logging

from config.constants import ARB_ETH_USD_CHAINLINK, ARB_VESTER
from config.enums import Network
from src.vester import Vester
from src.utils import get_node_url
from src.aws import get_secret

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    discord_url = get_secret(
        "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
    )
    node_url = "https://arb1.arbitrum.io/rpc"

    vester = Vester(
        Network.Arbitrum,
        discord_url,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ARB_ETH_USD_CHAINLINK,
        vesting_contract_address=ARB_VESTER,
        node_url=node_url,
    )

    logger.info("+-----Sending vested Badger to tree on Arbitrum-----+")
    vester.vest()
