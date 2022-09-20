from config.constants import ETH_ETH_USD_CHAINLINK
from config.constants import ETH_REMDRIPPER_Q2_22
from config.enums import Network
from src.aws import get_secret
from src.json_logger import logger
from src.utils import get_healthy_node
from src.vester import Vester

if __name__ == "__main__":
    chain = Network.Ethereum

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")
    web3 = get_healthy_node(chain)

    vester = Vester(
        web3,
        chain,
        discord_url,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        vesting_contract_address=ETH_REMDRIPPER_Q2_22,
    )

    logger.info("+-----Sending vested rem assets to tree on Ethereum-----+")
    vester.vest()
