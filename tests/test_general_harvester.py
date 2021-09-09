import os
import pytest
from brownie import accounts, Contract, web3
from decimal import Decimal
from hexbytes import HexBytes
from web3 import contract

from src.general_harvester import GeneralHarvester
from src.utils import get_abi, get_last_harvest_times, hours, get_secret
from tests.utils import test_address, test_key

ETH_USD_CHAINLINK = web3.toChecksumAddress("0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419")
KEEPER_ACL = web3.toChecksumAddress("0x711A339c002386f9db409cA55b6A35a604aB6cF6")
CVX_HELPER_STRATEGY = web3.toChecksumAddress(
    "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
)
CVX_CRV_HELPER_STRATEGY = web3.toChecksumAddress(
    "0x826048381d65a65DAa51342C51d464428d301896"
)
HBTC_STRATEGY = web3.toChecksumAddress("0xf4146A176b09C664978e03d28d07Db4431525dAd")


def mock_get_last_harvest_times(web3, keeper_acl, start_block):
    return get_last_harvest_times(
        web3, keeper_acl, start_block, etherscan_key=os.getenv("ETHERSCAN_TOKEN")
    )


def mock_send_discord(
    tx_hash: HexBytes,
    tx_type: str,
    gas_cost: Decimal = None,
    amt: Decimal = None,
    sett_name: str = None,
    chain: str = "ETH",
):
    print("sent")


@pytest.fixture(autouse=True)
def mock_fns(monkeypatch):
    # TODO: Ideally should find a way to mock get_secret
    monkeypatch.setattr(
        "src.general_harvester.send_success_to_discord", mock_send_discord
    )
    monkeypatch.setattr(
        "src.general_harvester.get_last_harvest_times", mock_get_last_harvest_times
    )
    monkeypatch.setattr(
        GeneralHarvester, "send_success_to_discord", lambda *args, **kwargs: print("none")
    )


@pytest.fixture
def keeper_key() -> str:
    return test_key


@pytest.fixture
def keeper_address() -> str:
    return test_address


@pytest.fixture(autouse=True)
def setup_keeper_acl(keeper_address):
    keeper_acl = Contract.from_abi(
        "KeeperAccessControl",
        KEEPER_ACL,
        get_abi("eth", "keeper_acl"),
    )
    harvester_key = keeper_acl.HARVESTER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(harvester_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(harvester_key, keeper_address, {"from": admin})
    return keeper_acl


@pytest.fixture
def strategy() -> contract:
    return web3.eth.contract(
        address=CVX_CRV_HELPER_STRATEGY,
        abi=get_abi("eth", "strategy"),
    )


@pytest.fixture
def btc_strategy() -> contract:
    return web3.eth.contract(address=HBTC_STRATEGY, abi=get_abi("eth", "strategy"))


@pytest.fixture
def harvester(keeper_address, keeper_key) -> GeneralHarvester:
    return GeneralHarvester(
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
        use_flashbots=False,
    )


@pytest.mark.require_network("hardhat-fork")
def test_harvest(keeper_address, harvester, strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(keeper_address, "1 ether")

    strategy_name = strategy.functions.getName().call()

    # Hack: For some reason, harvest call() fails without first calling estimateGas()
    harvester.estimate_gas_fee(strategy.address)

    before_claimable = harvester.estimate_harvest_amount(strategy)
    print(f"{strategy_name} before_claimable: {before_claimable}")

    # current_price_eth = harvester.get_current_rewards_price()
    # gas_fee = harvester.estimate_gas_fee(strategy.address)

    should_harvest = harvester.is_profitable()
    print(strategy_name, "should_harvest:", should_harvest)

    harvester.harvest(strategy)

    after_claimable = harvester.estimate_harvest_amount(strategy)
    print(f"{strategy_name} after_claimable: {after_claimable}")

    assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
        before_claimable == after_claimable and not should_harvest
    )


def test_btc_profit_est(harvester, btc_strategy):
    want = web3.eth.contract(
        address=btc_strategy.functions.want().call(), abi=get_abi("eth", "erc20")
    )
    # assert harvester.estimate_harvest_amount(btc_strategy) == 10


@pytest.mark.require_network("hardhat-fork")
def test_is_time_to_harvest(web3, chain, keeper_address, harvester, strategy):
    strategy_name = strategy.functions.getName().call()
    accounts[0].transfer(keeper_address, "10 ether")

    # Strategy should be harvestable at this point
    chain.sleep(hours(72))
    chain.mine(1)
    assert harvester.is_time_to_harvest(strategy) == True
    harvester.harvest(strategy)

    # Strategy shouldn't be harvestable
    assert harvester.is_time_to_harvest(strategy) == False

    # Strategy should be harvestable again after 72 hours
    chain.sleep(hours(72))
    chain.mine(1)
    assert harvester.is_time_to_harvest(strategy) == True
    harvester.harvest(strategy)
