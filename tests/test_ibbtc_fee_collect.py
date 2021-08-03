from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import os

from src.ibbtc_fee_collector import ibBTCFeeCollector
from tests.utils import *

os.environ["IBBTC_CORE_ADDRESS"] = "0x2A8facc9D49fBc3ecFf569847833C380A13418a8"
os.environ["BTC_ETH_CHAINLINK"] = "0xdeb288F737066589598e9214E782fa5A8eD689e8"
os.environ["ETH_USD_CHAINLINK"] = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"

@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def collector() -> ibBTCFeeCollector:
    return ibBTCFeeCollector(
        keeper_address=test_address,
        keeper_key=test_key,
        web3="http://127.0.0.1:8545",
    )


def test_collect(collector):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(test_address, "1 ether")

    # TODO: mock call to secretsmanager and have a real assert
    assert collector.collect_fees() == {}
