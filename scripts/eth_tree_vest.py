import logging

from config.constants import ETH_ETH_USD_CHAINLINK, ETH_REMDRIPPER
from config.enums import Network
from src.aws import get_secret
from src.utils import get_node_url
from src.vester import Vester

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    chain = Network.Ethereum

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    discord_url = get_secret(
        "keepers/info-webhook", "DISCORD_WEBHOOK_URL"
    )
    node_url = get_node_url(chain)

    vester = Vester(
        chain,
        discord_url,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        vesting_contract_address=ETH_REMDRIPPER,
        node_url=node_url,
    )

    logger.info("+-----Sending vested rem assets to tree on Ethereum-----+")
    vester.vest()
