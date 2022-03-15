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
                wait_for_transaction_receipt=MagicMock(),
                get_transaction_count=MagicMock(),
                max_priority_fee=MagicMock(),
                account=MagicMock(),
                send_raw_transaction=MagicMock(),
                gas_price=MagicMock()
            )
        )
    )
    vester.vesting_contract = MagicMock(
        functions=MagicMock(
            release=MagicMock(
                buildTransaction=MagicMock()
            )
        )
    )
    return vester

def test_vest(mock_arb_vester, mocker):
    success_message = mocker.patch("src.vester.send_success_to_discord")
    confirm_transaction = mocker.patch("src.vester.confirm_transaction")
    mock_arb_vester.vest()
    assert confirm_transaction.called
    assert success_message.called
