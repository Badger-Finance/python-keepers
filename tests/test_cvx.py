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


@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def cvx_helper_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
    return (strategy_address, "CVX Helper", get_strategy(strategy_address, "eth"))


@pytest.fixture
def harvester() -> CvxHarvester:
    return CvxHarvester(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


def test_harvest(
    harvester, cvx_helper_strategy
):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(test_address, "1 ether")

    def run_harvest(strategy_address, strategy_name, strategy):
        before_claimable = harvester.get_harvestable_rewards_amount(
            strategy_address=strategy_address
        )
        current_price_eth = harvester.get_current_rewards_price()
        gas_fee = harvester.estimate_gas_fee(
            harvester.web3.eth.contract(
                address=strategy_address,
                abi=get_abi("strategy", "eth"),
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
        return (before_claimable, after_claimable, should_harvest)

    strategy_address, strategy_name, strategy = cvx_helper_strategy

    (before_claimable, after_claimable, should_harvest) = run_harvest(
        strategy_address, strategy_name, strategy
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


def test_is_profitable(harvester):
    res = harvester.is_profitable(
        Decimal(1), Decimal(2), Decimal(web3.toWei(10000000, "gwei"))
    )
    assert res

    res = harvester.is_profitable(
        Decimal(1), Decimal(1), Decimal(web3.toWei(10000000, "gwei"))
    )
    assert res

    res = harvester.is_profitable(
        Decimal(1), Decimal(1), Decimal(web3.toWei(11000000, "gwei"))
    )
    assert not res

