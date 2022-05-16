import logging

from config.constants import ETH_BVECVX_STRATEGY
from config.constants import ETH_BVECVX_VAULT
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.aws import get_secret
from src.earner import Earner
from src.utils import get_abi
from src.utils import get_healthy_node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    chain = Network.Ethereum
    web3 = get_healthy_node(chain)

    keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
    keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
    earner = Earner(
        chain=chain,
        keeper_acl=MULTICHAIN_CONFIG.get(chain).get("keeper_acl"),
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        web3=web3,
        base_oracle_address=MULTICHAIN_CONFIG.get(chain).get("gas_oracle"),
    )

    strategy = node.eth.contract(
        address=ETH_BVECVX_STRATEGY, abi=get_abi(chain, "strategy")
    )
    vault = node.eth.contract(address=ETH_BVECVX_VAULT, abi=get_abi(chain, "vault"))

    strat_name = "Badger Vested Escrow Convex Token"

    logger.info(f"+-----Earning {strat_name}-----+")
    earner.earn(vault, strategy, strat_name)
