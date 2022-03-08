import pytest
from hexbytes import HexBytes

from config.enums import Network
from src.utils import get_explorer


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
