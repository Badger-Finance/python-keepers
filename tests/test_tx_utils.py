from unittest.mock import MagicMock

from src.tx_utils import get_latest_base_fee


def test_get_latest_base_fee():
    base_fee = 1213
    web3 = MagicMock(
        eth=MagicMock(
            get_block=MagicMock(
                return_value={"baseFeePerGas": base_fee}
            )
        )
    )
    assert get_latest_base_fee(web3) == base_fee
