import pytest
from unittest.mock import MagicMock

from config.constants import ARB_ETH_USD_CHAINLINK
from config.enums import Network
from src.vester import Vester
from tests.utils import test_keeper_address


@pytest.fixture
def mock_arb_vester():
    vester = Vester(
        Network.Arbitrum,
        "dummy.discord.com",
        keeper_address=test_keeper_address,
        keeper_key="dummykey",
        base_oracle_address=ARB_ETH_USD_CHAINLINK,
        web3=MagicMock(
            eth=MagicMock(
                wait_for_transaction_receipt=MagicMock(return_value={}),
                get_transaction_count=MagicMock(return_value={}),
                max_priority_fee=MagicMock(return_value={}),
                account=MagicMock(return_value={}),
                send_raw_transaction=MagicMock(return_value={}),
                gas_price=MagicMock(return_value={}),
            )
        ),
    )
    vester.vesting_contract = MagicMock(
        functions=MagicMock(
            release=MagicMock(buildTransaction=MagicMock(return_value={}))
        )
    )
    return vester


def test_vest_happy(mock_arb_vester, mocker):
    success_message = mocker.patch("src.vester.send_success_to_discord")
    confirm_transaction = mocker.patch(
        "src.vester.confirm_transaction", return_value=(True, True)
    )
    mocker.patch("src.vester.get_gas_price_of_tx", return_value=1)
    mock_arb_vester.vest()
    assert confirm_transaction.called
    assert success_message.called


def test_vest_pending_tx(mock_arb_vester, mocker):
    success_message = mocker.patch("src.vester.send_success_to_discord")
    confirm_transaction = mocker.patch(
        "src.vester.confirm_transaction", return_value=(False, False)
    )
    mock_arb_vester.vest()
    assert confirm_transaction.called
    assert success_message.called


def test_vest_error(mock_arb_vester, mocker):
    mock_arb_vester._send_vest_tx = MagicMock(side_effect=Exception)
    error_message = mocker.patch("src.vester.send_error_to_discord")
    mock_arb_vester.vest()
    assert error_message.called
