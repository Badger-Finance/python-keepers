from dataclasses import dataclass
from typing import List

from config.constants import ETH_BVECVX_STRATEGY
from config.constants import ETH_BVECVX_VAULT
from config.constants import ETH_GRAVIAURA_VAULT
from config.constants import ETH_GRAVIAURA_STRATEGY

ETH_INFLUENCE_VAULTS = [ETH_BVECVX_VAULT, ETH_GRAVIAURA_VAULT]
ETH_INFLUENCE_STRATEGIES = [ETH_BVECVX_STRATEGY, ETH_GRAVIAURA_STRATEGY]


@dataclass
class EarnSettings:
    """Represents smart contract."""

    influence_strategies: List[str]
    influence_vaults: List[str]


ETH_EARN_SETTINGS = EarnSettings(
    influence_strategies=ETH_INFLUENCE_STRATEGIES,
    influence_vaults=ETH_INFLUENCE_VAULTS,
)
