from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import os

from src.eth.cvx_harvester import CvxHarvester
from tests.utils import *

os.environ["DISCORD_WEBHOOK_URL"] = os.getenv("TEST_DISCORD_WEBHOOK_URL")

MaxUint256 = str(int(2 ** 256 - 1))


@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def cvx_helper_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
    # strategy_address = "0x826048381d65a65DAa51342C51d464428d301896"
    return (
        strategy_address,
        "CVX Helper",
    )


@pytest.fixture
def keeper_acl_address() -> str:
    contract_address = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"
    keeper_acl = Contract.from_abi(
        "KeeperAccessControl",
        contract_address,
        get_abi("keeper_acl", "eth"),
    )
    harvester_key = keeper_acl.HARVESTER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(harvester_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(harvester_key, test_address, {"from": admin})
    return contract_address


@pytest.fixture
def harvester() -> CvxHarvester:
    return CvxHarvester(
        keeper_address=test_address,
        keeper_key=test_key,
        node_url="http://127.0.0.1:8545",
        use_flashbots=False,
        send_to_discord=False,
    )


def get_harvestable_rewards(harvester, keeper_acl_address=None, strategy_address=None):
    return


def test_harvest(harvester, keeper_acl_address, cvx_helper_strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(test_address, "1 ether")

    strategy_address, strategy_name = cvx_helper_strategy
    keeper_acl = harvester.web3.eth.contract(
        address=keeper_acl_address,
        abi=get_abi("keeper_acl", "eth"),
    )

    # Hack: For some reason, harvest call() fails without first calling estimateGas()
    harvester.estimate_gas_fee(
        keeper_acl,
        strategy_address,
    )

    before_claimable = harvester.get_harvestable_rewards_amount(
        keeper_acl, strategy_address
    )
    print(strategy_name, "before_claimable:", before_claimable)
    current_price_eth = harvester.get_current_rewards_price()
    gas_fee = harvester.estimate_gas_fee(keeper_acl, strategy_address)
    should_harvest = harvester.is_profitable(
        before_claimable, current_price_eth, gas_fee
    )

    print(strategy_name, "should_harvest:", should_harvest)

    harvester.harvest(strategy_name, keeper_acl_address, strategy_address)
    after_claimable = harvester.get_harvestable_rewards_amount(
        keeper_acl, strategy_address
    )
    print(strategy_name, "after_claimable:", after_claimable)

    assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
        before_claimable == after_claimable and not should_harvest
    )
