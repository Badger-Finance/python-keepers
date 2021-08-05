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
    strategy = Contract.from_abi(
        "Strategy",
        strategy_address,
        get_abi("cvx_helper_strategy", "eth"),
    )
    cvx = Contract.from_abi(
        "CVX",
        strategy.cvx(),
        get_abi("cvx", "eth"),
    )

    harvestable_amt = strategy.harvest.call({"from": keeper_acl_address})
    return Decimal(harvestable_amt / 10 ** cvx.decimals())

    # return harvester.get_harvestable_rewards_amount(
    #     strategy_address=strategy_address
    # )


def test_harvest(harvester, keeper_acl_address, cvx_helper_strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(test_address, "1 ether")

    ## Process token approvals required for harvest() call
    ## TODO: Format this
    # crvToken = Contract.from_explorer("0xD533a949740bb3306d119CC777fa900bA034cd52")
    # cvxCrvToken = Contract.from_explorer("0x62B9c7356A2Dc64a1969e19C23e4f579F9810Aa7")
    # crvToken.approve(
    #     "0x8014595F2AB54cD7c604B00E9fb932176fDc86Ae",
    #     MaxUint256,
    #     {"from": "0xCF50b810E57Ac33B91dCF525C6ddd9881B139332"},
    # )
    # cvxCrvToken.approve(
    #     "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
    #     MaxUint256,
    #     {"from": "0x0172B8110b47448E32Ea9e4f291dB461Ee82D1d9"},
    # )

    strategy_address, strategy_name = cvx_helper_strategy
    keeper_acl = harvester.web3.eth.contract(
        address=keeper_acl_address,
        abi=get_abi("keeper_acl", "eth"),
    )

    # Hack: For some reason, strategy harvest() returns 0 without first calling estimate_gas
    #       Maybe use chain.sleep()
    harvester.estimate_gas_fee(
        keeper_acl,
        strategy_address,
    )

    before_claimable = get_harvestable_rewards(
        harvester, keeper_acl_address, strategy_address
    )
    print(strategy_name, "before_claimable:", before_claimable)
    current_price_eth = harvester.get_current_rewards_price()
    gas_fee = harvester.estimate_gas_fee(keeper_acl, strategy_address)
    should_harvest = harvester.is_profitable(
        before_claimable, current_price_eth, gas_fee
    )

    print(strategy_name, "should_harvest:", should_harvest)

    harvester.harvest(strategy_name, keeper_acl_address, strategy_address)
    after_claimable = get_harvestable_rewards(
        harvester, keeper_acl_address, strategy_address
    )
    print(strategy_name, "after_claimable:", after_claimable)

    assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
        before_claimable == after_claimable and not should_harvest
    )


# def test_get_current_rewards_price(harvester):
#     test_price = harvester.get_current_rewards_price()

#     r = requests.get(
#         f"https://api.coingecko.com/api/v3/simple/price?ids=xsushi&vs_currencies=eth"
#     )
#     data = r.json()
#     coin_gecko_price = data["xsushi"]["eth"]

#     assert round(float(test_price), 3) == round(coin_gecko_price, 3)
