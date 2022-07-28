import pytest

from unittest.mock import MagicMock

from config.enums import Network, VaultVersion
from src.registry_utils import (
    format_vaults,
    format_vault_metadata,
    get_production_vaults,
    get_vault_version,
    InvalidVaultVersion,
)
from tests.test_data.production_vaults import (
    PRODUCTION_VAULT_RAW,
    PRODUCTION_VAULT_FINAL,
    PRODUCTION_VAULT_FORMATTED,
)


def test_get_vault_version():
    assert get_vault_version("v1") == VaultVersion.v1.value
    assert get_vault_version("v1.5") == VaultVersion.v1_5.value
    assert get_vault_version("v2") == VaultVersion.v2.value

    with pytest.raises(InvalidVaultVersion):
        get_vault_version("jintao")


def test_format_metadata():
    metadata = "name=CVX/bveCVX,protocol=Curve,behavior=None"
    formatted_metadata = {
        "name": "CVX/bveCVX",
        "protocol": "Curve",
        "behavior": "None",
    }

    assert format_vault_metadata(metadata) == formatted_metadata


def test_format_vault():
    formatted_vaults = format_vaults(PRODUCTION_VAULT_RAW)

    assert formatted_vaults == PRODUCTION_VAULT_FORMATTED


def test_get_production_vaults():
    web3 = MagicMock(
        eth=MagicMock(
            contract=MagicMock(
                return_value=MagicMock(
                    getProductionVaults=MagicMock(return_value=PRODUCTION_VAULT_RAW)
                )
            )
        )
    )

    assert get_production_vaults(web3, Network.Ethereum) == PRODUCTION_VAULT_FINAL
