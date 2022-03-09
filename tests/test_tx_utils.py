from unittest.mock import MagicMock

from hexbytes import HexBytes

from src.tx_utils import get_latest_base_fee
from src.utils import get_hash_from_failed_tx_error


def test_get_latest_base_fee():
    base_fee = 1213
    web3 = MagicMock(
        eth=MagicMock(get_block=MagicMock(return_value={"baseFeePerGas": base_fee}))
    )
    assert get_latest_base_fee(web3) == base_fee


def test_get_latest_base_fee_no_fee():
    default_fee = int(100e9)
    web3 = MagicMock(eth=MagicMock(get_block=MagicMock(return_value={})))
    assert get_latest_base_fee(web3) == default_fee


def test_get_latest_base_fee_hex_fee():
    hex_gas = "0x64"
    web3 = MagicMock(
        eth=MagicMock(get_block=MagicMock(return_value={"baseFeePerGas": hex_gas}))
    )
    assert get_latest_base_fee(web3) == int(hex_gas, 0)


def test_get_hash_from_failed_tx_error(mocker):
    discord = mocker.patch("src.utils.send_error_to_discord")
    tx_hash = "0x123123"
    assert get_hash_from_failed_tx_error(
        ValueError({'data': {tx_hash: 123}}),
        "Harvest",
    ) == tx_hash
    assert discord.called


def test_get_hash_from_failed_tx_error_raises(mocker):
    """
    In case something goes wrong, func just returns HexBytes(0)
    """
    mocker.patch(
        "src.utils.send_error_to_discord",
        side_effect=Exception,
    )
    tx_hash = "0x123123"
    assert get_hash_from_failed_tx_error(
        ValueError({'data': {tx_hash: 123}}),
        "Harvest",
    ) == HexBytes(0)
