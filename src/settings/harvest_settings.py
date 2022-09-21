from dataclasses import dataclass
from typing import List, Optional

from config.constants import ARB_SWAPR_BADGER_WETH_VAULT
from config.constants import ARB_SWAPR_IBBTC_WETH_VAULT
from config.constants import ARB_SWAPR_SWAPR_WETH_VAULT
from config.constants import ARB_SWAPR_WBTC_WETH_VAULT
from config.constants import ETH_SLP_BADGER_WBTC_VAULT
from config.constants import REMBADGER

ETH_RESTITUTION_VAULTS = [REMBADGER]
ETH_REWARDS_MANAGER_VAULTS = [ETH_SLP_BADGER_WBTC_VAULT]
ARB_DEPRECATED_VAULTS = [
    ARB_SWAPR_BADGER_WETH_VAULT,
    ARB_SWAPR_IBBTC_WETH_VAULT,
    ARB_SWAPR_SWAPR_WETH_VAULT,
    ARB_SWAPR_WBTC_WETH_VAULT,
]


@dataclass
class HarvestSettings:

    restitution_vaults: Optional[List] = []
    rewards_manager_vaults: Optional[List] = []
    deprecated_vaults: Optional[List] = []


ETH_HARVEST_SETTINGS = HarvestSettings(
    restitution_vaults=ETH_RESTITUTION_VAULTS,
    rewards_manager_vaults=ETH_REWARDS_MANAGER_VAULTS,
)

ARB_HARVEST_SETTINGS = HarvestSettings(deprecated_vaults=ARB_DEPRECATED_VAULTS)
