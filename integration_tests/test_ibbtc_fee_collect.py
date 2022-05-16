import pytest
from brownie import *

import integration_tests.utils as test_utils
from config.enums import Network
from src.ibbtc_fee_collector import ibBTCFeeCollector
from src.utils import get_healthy_node


@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def collector() -> ibBTCFeeCollector:
    return ibBTCFeeCollector(
        keeper_address=test_utils.test_address,
        keeper_key=test_utils.test_key,
        web3=get_healthy_node(Network.Ethereum),
    )


def test_collect(collector, mocker):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    success_message = mocker.patch("src.ibbtc_fee_collector.send_success_to_discord")
    accounts[0].transfer(test_utils.test_address, "5 ether")

    collector.collect_fees()
    assert success_message.called
