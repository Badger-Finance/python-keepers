from brownie import Contract
from decimal import Decimal
from hexbytes import HexBytes
import json
import pytest

from src.utils import get_abi

test_address = "0xD88a9aF149366d57aEbc32D2eABAdf93EdA41A84"
test_key = "0f0bdc830bde4be43c3a54c369c6f6a94ac9071911dc3913e35ce5ed8fe955b9"


def get_strategy(
    strategy_address: str, network: str, abi_file: str = "strategy"
) -> Contract:
    strategy = Contract.from_abi(
        "Strategy",
        strategy_address,
        get_abi(network, abi_file),
    )
    gov = strategy.governance()
    strategy.setKeeper(test_address, {"from": gov})
    return strategy


def mock_send_discord(
    tx_hash: HexBytes,
    tx_type: str,
    gas_cost: Decimal = None,
    amt: Decimal = None,
    sett_name: str = None,
    chain: str = "ETH",
    url: str = None,
):
    print("sent")


@pytest.fixture
def schedule_json():
    with open("tests/data_classes/mock_emissions_schedule.json") as f:
        mock_schedule_json = json.load(f)
        return mock_schedule_json
