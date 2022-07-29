import logging

from config.constants import ETH_AURA_BAL_VAULT
from config.constants import ETH_B_BB_A_USD_AURA_VAULT
from config.constants import ETH_20WBTC_80BADGER_AURA_VAULT
from config.constants import ETH_33AURABAL_33WETH_33GRAVIAURA_VAULT
from config.constants import ETH_40DIGG_40WBTC_20GRAVIAURA_VAULT
from config.constants import ETH_BADGER_WBTC_CRV_VAULT
from config.constants import ETH_BBTC_VAULT
from config.constants import ETH_BDIGG_VAULT
from config.constants import ETH_BVECVX_VAULT
from config.constants import ETH_BVECVX_CVX_LP_VAULT
from config.constants import ETH_DIGG_STABILITY_VAULT
from config.constants import ETH_DIGG_WBTC_SUSHI_VAULT
from config.constants import ETH_DIGG_WBTC_UNI_VAULT
from config.constants import ETH_FRAX_CRV_VAULT
from config.constants import ETH_GRAVIAURA_VAULT
from config.constants import ETH_IBBTC_CRV_LP_VAULT
from config.constants import ETH_IBBTC_SUSHI_VAULT
from config.constants import ETH_MIM_CRV_VAULT
from config.constants import ETH_PBTC_VAULT
from config.constants import ETH_SBTC_VAULT
from config.constants import ETH_TBTC_VAULT
from config.constants import ETH_TRICRYPTO_VAULT
from config.constants import ETH_YVWBTC_VAULT
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from config.enums import VaultVersion
from src.aws import get_secret
from src.earner import Earner
from src.tx_utils import get_latest_base_fee
from src.utils import get_abi
from src.utils import get_healthy_node
from src.web3_utils import get_strategy_from_vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INVALID_VAULTS = [
    ETH_YVWBTC_VAULT,
    ETH_TRICRYPTO_VAULT,
    ETH_IBBTC_SUSHI_VAULT,
    ETH_SBTC_VAULT,
    ETH_TBTC_VAULT,
    ETH_PBTC_VAULT,
    ETH_BBTC_VAULT,
    ETH_BDIGG_VAULT,
    ETH_DIGG_WBTC_SUSHI_VAULT,
    ETH_DIGG_WBTC_UNI_VAULT,
    ETH_BVECVX_VAULT,
    ETH_GRAVIAURA_VAULT,
    ETH_DIGG_STABILITY_VAULT,
]


def safe_earn(earner, sett_name, vault, strategy):
    try:
        earner.earn(vault, strategy, sett_name=sett_name)
    except Exception as e:
        logger.error(f"Error running {sett_name} earn: {e}")


if __name__ == "__main__":
    for chain in [Network.Ethereum]:
        node = get_healthy_node(chain)

        registry = node.eth.contract(
            address=node.toChecksumAddress(MULTICHAIN_CONFIG[chain]["registry"]),
            abi=get_abi(chain, "registry"),
        )

        vaults = []
        strategies = []

        vault_addresses_v1 = registry.functions.getFilteredProductionVaults(
            "v1", 1
        ).call()
        vault_addresses_v1.extend(
            registry.functions.getFilteredProductionVaults("v1", 2).call()
        )
        vault_addresses_v1.append(ETH_BVECVX_CVX_LP_VAULT)
        vault_addresses_v1.append(ETH_IBBTC_CRV_LP_VAULT)
        vault_addresses_v1.append(ETH_FRAX_CRV_VAULT)
        vault_addresses_v1.append(ETH_MIM_CRV_VAULT)
        vault_addresses_v1.append(ETH_BADGER_WBTC_CRV_VAULT)

        for address in vault_addresses_v1:
            if address not in INVALID_VAULTS:
                logger.info(f"address: {address}")
                strategy, vault = get_strategy_from_vault(node, chain, address)
                strategies.append(strategy)
                vaults.append(vault)

        vault_addresses_v1_5 = [
            ETH_AURA_BAL_VAULT,
            ETH_B_BB_A_USD_AURA_VAULT,
            ETH_20WBTC_80BADGER_AURA_VAULT,
            ETH_33AURABAL_33WETH_33GRAVIAURA_VAULT,
            ETH_40DIGG_40WBTC_20GRAVIAURA_VAULT,
        ]
        for address in vault_addresses_v1_5:
            if address not in INVALID_VAULTS:
                logger.info(f"address: {address}")
                strategy, vault = get_strategy_from_vault(
                    node, chain, address, version=VaultVersion.v1_5
                )
                strategies.append(strategy)
                vaults.append(vault)

        keeper_key = get_secret("keepers/rebaser/keeper-pk", "KEEPER_KEY")
        keeper_address = get_secret("keepers/rebaser/keeper-address", "KEEPER_ADDRESS")
        discord_url = get_secret("keepers/info-webhook", "DISCORD_WEBHOOK_URL")
        earner = Earner(
            chain=chain,
            keeper_acl=MULTICHAIN_CONFIG[chain]["keeper_acl"],
            keeper_address=keeper_address,
            keeper_key=keeper_key,
            web3=node,
            base_oracle_address=MULTICHAIN_CONFIG[chain]["gas_oracle"],
            discord_url=discord_url,
        )

        latest_base_fee = get_latest_base_fee(earner.web3)

        for strategy, vault in zip(strategies, vaults):
            if strategy.address not in MULTICHAIN_CONFIG[chain]["earn"][
                "invalid_strategies"
            ] and latest_base_fee < int(150e9):
                strat_name = strategy.functions.getName().call()

                logger.info(f"+-----Earning {strat_name}-----+")
                safe_earn(earner, strat_name, vault, strategy)
