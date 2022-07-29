from collections import defaultdict
from typing import Dict, Tuple
from web3 import Web3

from config.constants import REGISTRY_V2
from config.enums import Network, VaultStatus, VaultVersion
from src.utils import get_abi


class InvalidVaultVersion(Exception):
    pass


def get_vault_version(version: str) -> VaultVersion:
    if version == "v1.5":
        return VaultVersion.v1_5.value
    elif version == "v1":
        return VaultVersion.v1.value
    elif version == "v2":
        return VaultVersion.v2.value

    raise InvalidVaultVersion(f"Version {version} not supported")


def get_production_vaults(web3: Web3, chain: Network) -> Dict:
    registry = web3.eth.contract(address=REGISTRY_V2, abi=get_abi(chain, "registry_v2"))
    vaults = registry.functions.getProductionVaults().call()
    formatted_vaults = format_vaults(vaults)
    production_vaults = defaultdict(dict)
    for version in formatted_vaults.keys():
        for status in formatted_vaults[version].keys():
            if status in [
                VaultStatus.Experimental.name,
                VaultStatus.Guarded.name,
                VaultStatus.Open.name,
            ]:
                production_vaults[version] = {
                    **production_vaults[version],
                    **formatted_vaults[version][status],
                }
    return production_vaults


def format_vaults(vaults: Tuple) -> Dict:
    formatted_vaults = defaultdict(dict)

    for version, status, data in vaults:
        formatted_version = get_vault_version(version)
        formatted_vaults[formatted_version][VaultStatus(status).name] = {}

        for address, metadata in data:
            meta_dict = format_vault_metadata(metadata)

            formatted_vaults[formatted_version][VaultStatus(status).name][
                address
            ] = meta_dict

    return formatted_vaults


def format_vault_metadata(metadata: str) -> Dict:
    meta_dict = {}
    fields = metadata.split(",")

    for field_raw in fields:
        parsed_field = field_raw.split("=")
        meta_dict[parsed_field[0]] = parsed_field[1]

    return meta_dict
