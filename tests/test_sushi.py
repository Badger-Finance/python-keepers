import re
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import json

from src.eth.sushi_harvester import SushiHarvester
from src.eth.sushi_tender import SushiTender
from src.strategies import eth_strategies


test_address = "0xD88a9aF149366d57aEbc32D2eABAdf93EdA41A84"
test_key = "0f0bdc830bde4be43c3a54c369c6f6a94ac9071911dc3913e35ce5ed8fe955b9"


def get_abi(contract_id: str):
    with open(f"./abi/eth/{contract_id}.json") as f:
        return json.load(f)


def get_strategy(strategy_address):
    strategy = Contract.from_abi(
        "Strategy",
        strategy_address,
        get_abi("strategy"),
    )
    gov = strategy.governance()
    strategy.setKeeper(test_address, {"from": gov})
    return strategy


@pytest.fixture
def badger_wbtc_strategy():
    strategy_address = "0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1"
    return ("0x3a494D79AA78118795daad8AeFF5825C6c8dF7F1", "BADGER WBTC LP", get_strategy(strategy_address))


@pytest.fixture
def harvester():
    return SushiHarvester(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


@pytest.fixture
def tender():
    return SushiTender(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=Web3(Web3.HTTPProvider("http://127.0.0.1:8545")),
    )


def test_harvest(harvester, badger_wbtc_strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    (strategy_address, strategy_name, strategy) = badger_wbtc_strategy

    before_claimable = harvester.get_harvestable_rewards_amount(
        pool_id=strategy.pid(), strategy_address=strategy_address
    )
    current_price_eth = harvester.get_current_rewards_price()
    gas_fee = harvester.estimate_gas_fee(
        harvester.web3.eth.contract(
            address=strategy_address,
            abi=get_abi("strategy"),
        )
    )
    should_harvest = harvester.is_profitable(
        before_claimable, current_price_eth, gas_fee
    )

    harvester.harvest(strategy_name, strategy_address)
    after_claimable = harvester.get_harvestable_rewards_amount(
        pool_id=strategy.pid(), strategy_address=strategy_address
    )

    assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
        before_claimable == after_claimable and not should_harvest
    )


def test_tend(tender, badger_wbtc_strategy):
    """
    Check if the contract should be tendable, then call the tend function

    If the strategy should be tended then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling tend
    """
    (strategy_address, strategy_name, strategy) = badger_wbtc_strategy

    before_claimable = tender.get_tendable_rewards_amount(
        pool_id=strategy.pid(), strategy_address=strategy_address
    )
    current_price_eth = tender.get_current_rewards_price()
    gas_fee = tender.estimate_gas_fee(
        tender.web3.eth.contract(
            address=strategy_address,
            abi=get_abi("strategy"),
        )
    )
    should_tend = tender.is_profitable(
        before_claimable, current_price_eth, gas_fee
    )

    tender.tend(strategy_name, strategy_address)
    after_claimable = tender.get_tendable_rewards_amount(
        pool_id=strategy.pid(), strategy_address=strategy_address
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
    res = harvester.is_profitable(Decimal(100), Decimal(2), Decimal(1))
    assert res

    res = harvester.is_profitable(Decimal(100), Decimal(1), Decimal(1))
    assert res

    res = harvester.is_profitable(Decimal(100), Decimal(1), Decimal(1.01))
    assert not res
