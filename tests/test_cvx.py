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
        get_strategy(strategy_address, "eth", "cvx_helper_strategy"),
    )


@pytest.fixture
def harvester() -> CvxHarvester:
    return CvxHarvester(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


def test_harvest(harvester, cvx_helper_strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(test_address, "1 ether")

    # Process token approvals required for harvest() call
    # TODO: Format this
    crvToken = Contract.from_explorer("0xD533a949740bb3306d119CC777fa900bA034cd52")
    crvToken.approve(
        "0x8014595F2AB54cD7c604B00E9fb932176fDc86Ae",
        MaxUint256,
        {"from": "0xCF50b810E57Ac33B91dCF525C6ddd9881B139332"},
    )

    cvxCrvToken = Contract.from_explorer("0x62B9c7356A2Dc64a1969e19C23e4f579F9810Aa7")
    cvxCrvToken.approve(
        "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        MaxUint256,
        {"from": "0x0172B8110b47448E32Ea9e4f291dB461Ee82D1d9"},
    )

    strategy_address, strategy_name, strategy = cvx_helper_strategy

    # Hack: For some reason, strategy harvest() returns 0 without first calling estimate_gas
    harvester.estimate_gas_fee(
        harvester.web3.eth.contract(
            address=strategy_address,
            abi=get_abi("cvx_helper_strategy", "eth"),
        )
    )

    before_claimable = harvester.get_harvestable_rewards_amount(
        strategy_address=strategy_address
    )
    current_price_eth = harvester.get_current_rewards_price()
    gas_fee = harvester.estimate_gas_fee(
        harvester.web3.eth.contract(
            address=strategy_address,
            abi=get_abi("cvx_helper_strategy", "eth"),
        )
    )
    should_harvest = harvester.is_profitable(
        before_claimable, current_price_eth, gas_fee
    )

    print(strategy_name, "should_harvest:", should_harvest)

    harvester.harvest(strategy_name, strategy_address)
    after_claimable = harvester.get_harvestable_rewards_amount(
        strategy_address=strategy_address
    )

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
