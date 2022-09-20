from config.constants import ETH_BVECVX_STRATEGY
from config.constants import ETH_BVECVX_VAULT
from config.constants import ETH_GRAVIAURA_STRATEGY
from config.constants import ETH_GRAVIAURA_VAULT
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from src.aws import get_secret
from src.earner import Earner
from src.json_logger import logger
from src.utils import get_abi
from src.utils import get_healthy_node


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

    strategy = web3.eth.contract(
        address=ETH_BVECVX_STRATEGY, abi=get_abi(chain, "strategy")
    )
    vault = web3.eth.contract(address=ETH_BVECVX_VAULT, abi=get_abi(chain, "vault"))

    bvecvx_strat_name = "Badger Vested Escrow Convex Token"

    logger.info(f"+-----Earning {bvecvx_strat_name}-----+")
    try:
        earner.earn(vault, strategy, bvecvx_strat_name)
    except Exception:
        logger.error("ERROR EARNING BVECVX")

    graviaura_strategy = web3.eth.contract(
        address=ETH_GRAVIAURA_STRATEGY, abi=get_abi(chain, "strategy")
    )
    graviaura_vault = web3.eth.contract(
        address=ETH_GRAVIAURA_VAULT, abi=get_abi(chain, "vault")
    )

    graviaura_strategy_name = "graviAURA"

    logger.info(f"+-----Earning {graviaura_strategy_name}-----+")
    earner.earn(graviaura_vault, graviaura_strategy, graviaura_strategy_name)
