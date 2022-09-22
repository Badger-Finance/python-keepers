import sys

from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.aws import get_secret
from src.data_classes.contract import Contract
from src.earner import Earner
from src.json_logger import exception_logging
from src.json_logger import logger
from src.settings.earn_settings import ETH_EARN_SETTINGS
from src.tx_utils import get_latest_base_fee
from src.utils import get_healthy_node
from src.web3_utils import get_strategies_and_vaults


sys.excepthook = exception_logging


def safe_earn(earner: Earner, vault: Contract, strategy: Contract):
    try:
        earner.earn(vault.contract, strategy.contract, sett_name=vault.name)
    except Exception as e:
        logger.error(f"Error running {vault.name} earn: {e}")


if __name__ == "__main__":
    node = get_healthy_node(Network.Ethereum)

    strategies, vaults = get_strategies_and_vaults(node, Network.Ethereum)

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")
    earner = Earner(
        chain=Network.Ethereum,
        keeper_acl=MULTICHAIN_CONFIG[Network.Ethereum]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        web3=node,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Ethereum]["gas_oracle"],
        discord_url=discord_url,
    )

    latest_base_fee = get_latest_base_fee(earner.web3)

    for strategy, vault in zip(strategies, vaults):
        if (
            vault.address not in ETH_EARN_SETTINGS.influence_vaults
            and latest_base_fee < int(150e9)
        ):

            logger.info(f"+-----Earning {vault.name}-----+")
            safe_earn(earner, vault, strategy)
