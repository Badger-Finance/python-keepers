import logging

from web3 import Web3

from config.constants import MULTICHAIN_CONFIG
from config.constants import POLY_OLD_STRATEGY
from config.enums import Network
from src.earner import Earner
from src.utils import get_node_url
from src.utils import get_secret
from src.web3_utils import get_strategies_and_vaults

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INVALID_STRATS = [POLY_OLD_STRATEGY]


def safe_earn(earner, sett_name, vault, strategy):
    try:
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running {sett_name} earn: {e}")


if __name__ == "__main__":
    for chain in [Network.Polygon]:
        node_url = get_node_url(chain)
        node = Web3(Web3.HTTPProvider(node_url))

        strategies, vaults = get_strategies_and_vaults(node, chain)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")

        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG[chain]["gas_oracle"],
        )

        for strategy, vault in zip(strategies, vaults):
            if strategy.address not in INVALID_STRATS:
                strat_name = strategy.functions.getName().call()

                logger.info(f"+-----Earning {strat_name}-----+")
                safe_earn(earner, strat_name, vault, strategy)
