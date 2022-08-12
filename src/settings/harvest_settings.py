from dataclasses import dataclass
from typing import List

from config.constants import ETH_SLP_BADGER_WBTC_VAULT
from config.constants import REMBADGER

ETH_RESTITUTION_VAULTS = [REMBADGER]
ETH_REWARDS_MANAGER_VAULTS = [ETH_SLP_BADGER_WBTC_VAULT]


@dataclass
class HarvestSettings:

    restitution_vaults: List[str]
    rewards_manager_vaults: List[str]


ETH_HARVEST_SETTINGS = HarvestSettings(
    restitution_vaults=ETH_RESTITUTION_VAULTS,
    rewards_manager_vaults=ETH_REWARDS_MANAGER_VAULTS,
)
