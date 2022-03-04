from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import os

from src.eth.sushi_harvester import SushiHarvester
from src.eth.sushi_tender import SushiTender
from src.utils import get_abi
from integration_tests.utils import *
from config.enums import Network

os.environ["DISCORD_WEBHOOK_URL"] = os.getenv("TEST_DISCORD_WEBHOOK_URL")


@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def badger_wbtc_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
    return (
        strategy_address,
        "BADGER WBTC LP",
        get_strategy(strategy_address, Network.Ethereum),
    )


@pytest.fixture
def digg_wbtc_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0xaa8dddfe7DFA3C3269f1910d89E4413dD006D08a"
    return (
        strategy_address,
        "DIGG WBTC LP",
        get_strategy(strategy_address, Network.Ethereum),
    )


@pytest.fixture
def eth_wbtc_strategy() -> Tuple[str, str, Contract]:
    strategy_address = "0x7A56d65254705B4Def63c68488C0182968C452ce"
    return (
        strategy_address,
        "ETH WBTC LP",
        get_strategy(strategy_address, Network.Ethereum),
    )


@pytest.fixture
def harvester() -> SushiHarvester:
    return SushiHarvester(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


@pytest.fixture
def tender() -> SushiTender:
    return SushiTender(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


def test_harvest(
    harvester, badger_wbtc_strategy, digg_wbtc_strategy, eth_wbtc_strategy
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
            pool_id=strategy.pid(), strategy_address=strategy_address
        )
        current_price_eth = harvester.get_current_rewards_price()
        gas_fee = harvester.estimate_gas_fee(
            harvester.web3.eth.contract(
                address=strategy_address,
                abi=get_abi(Network.Ethereum, "strategy"),
            )
        )
        should_harvest = harvester.is_profitable(
            before_claimable, current_price_eth, gas_fee
        )

        print(strategy_name, "should_harvest:", should_harvest)

        harvester.harvest(strategy_name, strategy_address)
        after_claimable = harvester.get_harvestable_rewards_amount(
            pool_id=strategy.pid(), strategy_address=strategy_address
        )
        return (before_claimable, after_claimable, should_harvest)

    for (strategy_address, strategy_name, strategy) in [
        badger_wbtc_strategy,
        digg_wbtc_strategy,
        eth_wbtc_strategy,
    ]:
        (before_claimable, after_claimable, should_harvest) = run_harvest(
            strategy_address, strategy_name, strategy
        )

        assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
            before_claimable == after_claimable and not should_harvest
        )


def test_tend(tender, badger_wbtc_strategy, digg_wbtc_strategy, eth_wbtc_strategy):
    """
    Check if the contract should be tendable, then call the tend function

    If the strategy should be tended then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling tend
    """
    accounts[0].transfer(test_address, "1 ether")

    def run_tend(strategy_address, strategy_name, strategy):
        before_claimable = tender.get_tendable_rewards_amount(
            pool_id=strategy.pid(), strategy_address=strategy_address
        )
        current_price_eth = tender.get_current_rewards_price()
        gas_fee = tender.estimate_gas_fee(
            tender.web3.eth.contract(
                address=strategy_address,
                abi=get_abi(Network.Ethereum, "strategy"),
            )
        )
        should_tend = tender.is_profitable(before_claimable, current_price_eth, gas_fee)

        print(strategy_name, "should_tend:", should_tend)

        tender.tend(strategy_name, strategy_address)
        after_claimable = tender.get_tendable_rewards_amount(
            pool_id=strategy.pid(), strategy_address=strategy_address
        )
        return (before_claimable, after_claimable, should_tend)

    for (strategy_address, strategy_name, strategy) in [
        badger_wbtc_strategy,
        digg_wbtc_strategy,
        eth_wbtc_strategy,
    ]:
        (before_claimable, after_claimable, should_tend) = run_tend(
            strategy_address, strategy_name, strategy
        )

        assert (should_tend and before_claimable != 0 and after_claimable == 0) or (
            before_claimable == after_claimable and not should_tend
        )


def test_get_current_rewards_price(harvester):
    test_price = harvester.get_current_rewards_price()

    r = requests.get(
        f"https://api.coingecko.com/api/v3/simple/price?ids=xsushi&vs_currencies=eth"
    )
    data = r.json()
    coin_gecko_price = data["xsushi"]["eth"]

    assert round(float(test_price), 3) == round(coin_gecko_price, 3)


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
