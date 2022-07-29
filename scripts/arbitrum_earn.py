import logging

from web3 import Web3, contract

from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.earner import Earner
from src.aws import get_secret
from src.web3_utils import get_strategies_and_vaults

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_earn(earner: Earner, vault: contract, strategy: contract, name: str):
    try:
        logger.info(f"+-----Earning {name}-----+")
        earner.earn(vault, strategy, sett_name=name)
    except Exception as e:
        logger.error(f"Error running earn: {e}")


if __name__ == "__main__":
    for chain in [Network.Arbitrum]:
        # node_url = get_secret("alchemy/arbitrum-node-url", "ARBITRUM_NODE_URL")
        node_url = "https://arb1.arbitrum.io/rpc"
        node = Web3(Web3.HTTPProvider(node_url))

        strategies, vaults = get_strategies_and_vaults(node, chain)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
        discord_url = get_secret(
            "keepers/harvester/arbitrum/info-webhook", "DISCORD_WEBHOOK_URL"
        )

        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG.get(chain).get("gas_oracle"),
            discord_url=discord_url,
        )

        for strategy, vault in zip(strategies, vaults):
            if (
                strategy["address"]
                not in MULTICHAIN_CONFIG[chain]["earn"]["invalid_strategies"]
            ):
                safe_earn(
                    earner, vault["contract"], strategy["contract"], strategy["name"]
                )
