from dataclasses import dataclass
from typing import List

from config.constants import ETH_YVWBTC_VAULT, ETH_GRAVIAURA_VAULT

ETH_EXTERNAL_VAULTS = [ETH_YVWBTC_VAULT, ETH_GRAVIAURA_VAULT]


@dataclass
class RegistrySettings:

    externally_managed_vaults: List[str]


ETH_REGISTRY_SETTINGS = RegistrySettings(
    externally_managed_vaults=ETH_EXTERNAL_VAULTS,
)
