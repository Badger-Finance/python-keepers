from unittest.mock import MagicMock

from hexbytes import HexBytes
from web3 import exceptions

from src.utils import confirm_transaction


def test_confirm_transaction():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(wait_for_transaction_receipt=MagicMock())
        ),
        tx_hash=tx_hash,
    )
    assert success
    assert tx_msg == f"Transaction {tx_hash.hex()} succeeded!"


def test_confirm_transaction_raises():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(
                wait_for_transaction_receipt=MagicMock(side_effect=exceptions.TimeExhausted)
            )
        ),
        tx_hash=tx_hash,
    )
    assert not success
    assert tx_msg == f"Transaction {tx_hash.hex()} timed out, not included in block yet."


def test_confirm_transaction_raises__max_block():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(
                wait_for_transaction_receipt=MagicMock(side_effect=exceptions.TimeExhausted),
                block_number=1234,
            )
        ),
        tx_hash=tx_hash,
        max_block=123
    )
    assert not success
    assert tx_msg == f"Transaction {tx_hash.hex()} was not included in the block."


def test_confirm_transaction_raises_unexpected():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(
                wait_for_transaction_receipt=MagicMock(side_effect=Exception)
            )
        ),
        tx_hash=tx_hash,
    )
    assert not success
    assert tx_msg == f"Error waiting for {tx_hash.hex()}. Error: ."
