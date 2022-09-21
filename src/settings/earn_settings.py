from dataclasses import dataclass
from typing import List
from typing import Optional

from config.constants import ARB_SWAPR_BADGER_WETH_VAULT
from config.constants import ARB_SWAPR_IBBTC_WETH_VAULT
from config.constants import ARB_SWAPR_SWAPR_WETH_VAULT
from config.constants import ARB_SWAPR_WBTC_WETH_VAULT
from config.constants import ETH_BVECVX_STRATEGY
from config.constants import ETH_BVECVX_VAULT
from config.constants import ETH_GRAVIAURA_VAULT
from config.constants import ETH_GRAVIAURA_STRATEGY

ETH_INFLUENCE_VAULTS = [ETH_BVECVX_VAULT, ETH_GRAVIAURA_VAULT]
ETH_INFLUENCE_STRATEGIES = [ETH_BVECVX_STRATEGY, ETH_GRAVIAURA_STRATEGY]
ARB_DEPRECATED_VAULTS = [
    ARB_SWAPR_BADGER_WETH_VAULT,
    ARB_SWAPR_IBBTC_WETH_VAULT,
    ARB_SWAPR_SWAPR_WETH_VAULT,
    ARB_SWAPR_WBTC_WETH_VAULT,
]


@dataclass
class EarnSettings:

    influence_strategies: Optional[List] = None
    influence_vaults: Optional[List] = None
    deprecated_vaults: Optional[List] = None


ETH_EARN_SETTINGS = EarnSettings(
    influence_strategies=ETH_INFLUENCE_STRATEGIES,
    influence_vaults=ETH_INFLUENCE_VAULTS,
)

ARB_EARN_SETTINGS = EarnSettings(deprecated_vaults=ARB_DEPRECATED_VAULTS)
