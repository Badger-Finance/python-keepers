import pytest
from hexbytes import HexBytes

from config.enums import Network
from src.utils import get_abi
from src.utils import get_explorer
from src.utils import hours
from src.utils import seconds_to_blocks


@pytest.mark.parametrize(
    "chain, expected_explorer_root",
    [
        (Network.Ethereum, "https://etherscan.io/"),
        (Network.Polygon, "https://polygonscan.com"),
        (Network.Arbitrum, "https://arbiscan.io/"),
        (Network.Fantom, "https://ftmscan.com/"),
    ]
)
def test_get_explorer(chain, expected_explorer_root):
    _, explorer_url = get_explorer(chain, HexBytes("0x123123"))
    assert expected_explorer_root in explorer_url


def test_seconds_to_blocks():
    assert seconds_to_blocks(100) == 8.101851851851851
    assert seconds_to_blocks(0) == 0


def test_hours():
    num_of_hours = 2
    assert hours(num_of_hours) == num_of_hours * 3600  # seconds


@pytest.mark.parametrize(
    "chain",
    [Network.Ethereum, Network.Polygon, Network.Arbitrum, Network.Fantom]
)
def test_get_abi(chain):
    abi = get_abi(chain, "keeper_acl")
    assert abi is not None
