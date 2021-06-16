from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import os

from src.bsc.cake_harvester import CakeHarvester
from tests.utils import *

os.environ["DISCORD_WEBHOOK_URL"] = os.getenv("TEST_DISCORD_WEBHOOK_URL")


@pytest.mark.require_network("bsc-fork")
def test_correct_network():
    pass


@pytest.fixture
def bbadger_btcb_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0x2A842e01724F10d093aE8a46A01e66DbCf3C7373"
    return (strategy_address, "BBADGER BTCB LP", get_strategy(strategy_address, "bsc"))


@pytest.fixture
def bdigg_btcb_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0xC8C53A293edca5a0146d713b9b95b0cd0a2e5ca4"
    return (strategy_address, "BDIGG BTCB LP", get_strategy(strategy_address, "bsc"))


@pytest.fixture
def bnb_btcb_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0x120BB9F87bAB3C49b89c7745eDC07FED50786534"
    return (strategy_address, "BNB BTCB LP", get_strategy(strategy_address, "bsc"))


@pytest.fixture
def harvester() -> CakeHarvester:
    return CakeHarvester(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


def test_harvest(
    harvester, bbadger_btcb_strategy, bdigg_btcb_strategy, bnb_btcb_strategy
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
            pool_id=strategy.wantPid(), strategy_address=strategy_address
        )
        current_price_bnb = harvester.get_current_rewards_price()
        should_harvest = harvester.is_profitable(before_claimable, current_price_bnb)

        print(strategy_name, "should_harvest:", should_harvest)

        harvester.harvest(strategy_name, strategy_address)
        after_claimable = harvester.get_harvestable_rewards_amount(
            pool_id=strategy.wantPid(), strategy_address=strategy_address
        )
        return (before_claimable, after_claimable, should_harvest)

    for (strategy_address, strategy_name, strategy) in [
        bbadger_btcb_strategy,
        bdigg_btcb_strategy,
        bnb_btcb_strategy,
    ]:
        (before_claimable, after_claimable, should_harvest) = run_harvest(
            strategy_address, strategy_name, strategy
        )

        assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
            before_claimable == after_claimable and not should_harvest
        )


def test_get_current_rewards_price(harvester):
    test_price = harvester.get_current_rewards_price()

    r = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=pancakeswap-token&vs_currencies=bnb"
    )
    data = r.json()
    coin_gecko_price = data["pancakeswap-token"]["bnb"]

    assert round(float(test_price), 3) == round(coin_gecko_price, 3)


def test_is_profitable(harvester):
    res = harvester.is_profitable(Decimal(100), Decimal(2))
    assert res

    res = harvester.is_profitable(Decimal(1), Decimal(2))
    assert res

    res = harvester.is_profitable(Decimal(0.9), Decimal(2))
    assert not res
