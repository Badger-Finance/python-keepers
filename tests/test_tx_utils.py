import pytest
import responses

from hexbytes import HexBytes
from unittest.mock import MagicMock
from web3 import Web3

from config.constants import GAS_LIMITS
from config.enums import Network
from src.tx_utils import get_gas_price
from src.tx_utils import get_latest_base_fee
from src.tx_utils import get_tx_options
from src.tx_utils import sign_and_send_tx
from src.discord_utils import get_hash_from_failed_tx_error


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
    discord = mocker.patch("src.discord_utils.send_error_to_discord")
    tx_hash = "0x123123"
    assert (
        get_hash_from_failed_tx_error(
            ValueError({"data": {tx_hash: 123}}),
            "Harvest",
        )
        == tx_hash
    )
    assert discord.called


def test_get_hash_from_failed_tx_error_raises(mocker):
    """
    In case something goes wrong, func just returns HexBytes(0)
    """
    mocker.patch(
        "src.discord_utils.send_error_to_discord",
        side_effect=Exception,
    )
    tx_hash = "0x123123"
    assert (
        get_hash_from_failed_tx_error(
            ValueError({"data": {tx_hash: 123}}),
            "Harvest",
        )
        == HexBytes(0)
    )


@responses.activate
def test_get_gas_price_poly(mocker):
    responses.add(
        responses.GET,
        "https://gasstation-mainnet.matic.network",
        json={
            "safeLow": 32.8,
            "standard": 43.2,
            "fast": 44.9,
            "fastest": 44.9,
            "blockTime": 1,
            "blockNumber": 27096593,
        },
        status=200,
    )

    web3 = MagicMock(
        eth=MagicMock(get_block=MagicMock(return_value={})),
        toWei=lambda x, y: x * 10 ** 18,
    )
    assert get_gas_price(web3, Network.Polygon) == 49000000000000000000


@responses.activate
def test_get_gas_price_eth(mocker):
    mocker.patch(
        "src.tx_utils.get_effective_gas_price", return_value=40000000000000000000
    )
    web3 = MagicMock(
        eth=MagicMock(),
    )

    assert get_gas_price(web3, Network.Ethereum) == 40000000000000000000


@responses.activate
def test_get_gas_price_ftm_arb(mocker):
    gas_price = 40000000000000000000
    web3 = MagicMock(
        eth=MagicMock(gas_price=gas_price),
    )

    assert get_gas_price(web3, Network.Arbitrum) == int(gas_price * 1.1)
    assert get_gas_price(web3, Network.Fantom) == int(gas_price * 1.1)


def test_get_tx_options(mocker):
    web3 = MagicMock(
        eth=MagicMock(get_transaction_count=MagicMock(return_value=3)),
    )
    eth_options = {
        "from": "0x00",
        "gas": 6000000,
        "maxFeePerGas": 40000000000000000000,
        "maxPriorityFeePerGas": 10000000000000000000,
        "nonce": 3,
    }
    arb_options = {
        "from": "0x00",
        "gas": GAS_LIMITS[Network.Arbitrum],
        "gasPrice": 40000000000000000000,
        "nonce": 3,
    }
    ftm_options = {
        "from": "0x00",
        "gas": GAS_LIMITS[Network.Fantom],
        "gasPrice": 40000000000000000000,
        "nonce": 3,
    }

    mocker.patch("src.tx_utils.get_priority_fee", return_value=10000000000000000000)
    mocker.patch("src.tx_utils.get_gas_price", return_value=40000000000000000000)

    assert get_tx_options(web3, Network.Ethereum, HexBytes(0).hex()) == eth_options
    assert get_tx_options(web3, Network.Arbitrum, HexBytes(0).hex()) == arb_options
    assert get_tx_options(web3, Network.Fantom, HexBytes(0).hex()) == ftm_options

def test_sign_and_send_tx(mocker):
    web3 = MagicMock(
        eth=MagicMock(
            account=MagicMock(
                sign_transaction=MagicMock(
                    return_value=MagicMock(
                        hash=HexBytes(45).hex(),
                        rawTransaction={}
                    )
                )
            ),
            send_raw_transaction=MagicMock()
        ),
    )

    assert sign_and_send_tx(web3, {}, "") == HexBytes(45).hex()
    assert web3.eth.send_raw_transaction.called

    web3.eth.send_raw_transaction = MagicMock(side_effect=Exception)
    assert sign_and_send_tx(web3, {}, "") == HexBytes(0)
