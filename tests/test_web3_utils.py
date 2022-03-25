from unittest.mock import MagicMock

import pytest
import responses
from hexbytes import HexBytes
from web3 import exceptions
from web3 import Web3

from config.enums import Network
from src.web3_utils import confirm_transaction
from src.web3_utils import get_last_harvest_times


def test_confirm_transaction():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(eth=MagicMock(wait_for_transaction_receipt=MagicMock())),
        tx_hash=tx_hash,
    )
    assert success
    assert tx_msg == f"Transaction {tx_hash.hex()} succeeded!"


def test_confirm_transaction_raises():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(
                wait_for_transaction_receipt=MagicMock(
                    side_effect=exceptions.TimeExhausted
                )
            )
        ),
        tx_hash=tx_hash,
    )
    assert not success
    assert (
        tx_msg == f"Transaction {tx_hash.hex()} timed out, not included in block yet."
    )


def test_confirm_transaction_raises__max_block():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(
                wait_for_transaction_receipt=MagicMock(
                    side_effect=exceptions.TimeExhausted
                ),
                block_number=1234,
            )
        ),
        tx_hash=tx_hash,
        max_block=123,
    )
    assert not success
    assert tx_msg == f"Transaction {tx_hash.hex()} was not included in the block."


def test_confirm_transaction_raises_unexpected():
    tx_hash = HexBytes("0x123123")
    success, tx_msg = confirm_transaction(
        MagicMock(
            eth=MagicMock(wait_for_transaction_receipt=MagicMock(side_effect=Exception))
        ),
        tx_hash=tx_hash,
    )
    assert not success
    assert tx_msg == f"Error waiting for {tx_hash.hex()}. Error: ."


@responses.activate
@pytest.mark.parametrize(
    "chain, mock_scan_url",
    [
        (Network.Ethereum, "https://api.etherscan.io/api"),
        (Network.Fantom, "https://api.ftmscan.com/api"),
    ],
)
def test_get_last_harvest_times(mocker, chain, mock_scan_url):
    mocker.patch("src.web3_utils.get_secret")
    some_strategy = "0x111111"
    expected_timestamp = "123123123"
    responses.add(
        responses.GET,
        mock_scan_url,
        json={
            "result": [
                {
                    "to": "0xaffb3b889E48745Ce16E90433A61f4bCb95692Fd",
                    "input": "",
                    "timeStamp": expected_timestamp,
                }
            ]
        },
        status=200,
    )
    times = get_last_harvest_times(
        MagicMock(
            eth=MagicMock(
                block_number=1234,
            ),
            toChecksumAddress=Web3.toChecksumAddress,
        ),
        keeper_acl=MagicMock(  # noqa
            address="0xaffb3b889E48745Ce16E90433A61f4bCb95692Fd",
            decode_function_input=MagicMock(
                return_value=(
                    "<Function harvest(address)>",
                    {"strategy": some_strategy},
                )
            ),
        ),
        chain=chain,
    )
    assert times == {some_strategy: int(expected_timestamp)}


@responses.activate
@responses.activate
@pytest.mark.parametrize(
    "chain, mock_scan_url",
    [
        (Network.Ethereum, "https://api.etherscan.io/api"),
        (Network.Fantom, "https://api.ftmscan.com/api"),
    ],
)
def test_get_last_harvest_times_empty_response(mocker, chain, mock_scan_url):
    """
    Case when etherscan returns empty array of transactions
    """
    mocker.patch("src.web3_utils.get_secret")
    responses.add(
        responses.GET,
        mock_scan_url,
        json={"result": []},
        status=200,
    )
    assert (
        get_last_harvest_times(
            MagicMock(
                eth=MagicMock(
                    block_number=1234,
                ),
                toChecksumAddress=Web3.toChecksumAddress,
            ),
            keeper_acl=MagicMock(),  # noqa
            chain=chain,
        )
        == {}
    )
