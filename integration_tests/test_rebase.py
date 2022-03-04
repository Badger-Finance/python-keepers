from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import os

from src.rebaser import Rebaser
from integration_tests.utils import *

os.environ["DISCORD_WEBHOOK_URL"] = os.getenv("TEST_DISCORD_WEBHOOK_URL")
os.environ["ETH_USD_CHAINLINK"] = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
os.environ["DIGG_TOKEN_ADDRESS"] = "0x798D1bE841a82a273720CE31c822C61a67a601C3"
os.environ["DIGG_ORCHESTRATOR_ADDRESS"] = "0xbd5d9451e004fc495f105ceab40d6c955e4192ba"
os.environ["DIGG_POLICY_ADDRESS"] = "0x327a78D13eA74145cc0C63E6133D516ad3E974c3"
os.environ["UNIV2_DIGG_WBTC_ADDRESS"] = "0xe86204c4eddd2f70ee00ead6805f917671f56c52"
os.environ["SUSHI_DIGG_WBTC_ADDRESS"] = "0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3"
os.environ["GAS_LIMIT"] = "1000000"


@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def rebaser() -> Rebaser:
    return Rebaser(
        keeper_address=test_address,
        keeper_key=test_key,
        web3="http://127.0.0.1:8545",
    )


def test_rebase(rebaser):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(test_address, "1 ether")

    assert rebaser.rebase() == {}


def test_send_rebase_tx(rebaser):
    accounts[0].transfer(test_address, "10 ether")

    # TODO: mock send discord functions
    rebaser._Rebaser__process_rebase() == {}
