import os
from decimal import Decimal

import pytest
from brownie import Contract
from brownie import accounts
from brownie import web3
from hexbytes import HexBytes
from web3 import contract

from config.constants import ETH_CVX_CRV_HELPER_STRATEGY
from config.constants import ETH_HBTC_CRV_STRATEGY
from config.constants import ETH_SLP_DIGG_WBTC_STRATEGY
from config.constants import MULTICHAIN_CONFIG
from config.constants import XSUSHI
from config.enums import Network
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.general_harvester import GeneralHarvester
from src.utils import get_abi
from src.utils import get_last_harvest_times
from src.utils import hours
from src.utils import seconds_to_blocks

ETH_USD_CHAINLINK = web3.toChecksumAddress(
    MULTICHAIN_CONFIG[Network.Ethereum]["gas_oracle"]
)
KEEPER_ACL = web3.toChecksumAddress(MULTICHAIN_CONFIG[Network.Ethereum]["keeper_acl"])
REWARDS_MANAGER = web3.toChecksumAddress(
    MULTICHAIN_CONFIG[Network.Ethereum]["rewards_manager"]
)


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
    chain: str = Network.Ethereum,
    url: str = None,
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
        get_abi(Network.Ethereum, "keeper_acl"),
    )
    harvester_key = keeper_acl.HARVESTER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(harvester_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(harvester_key, keeper_address, {"from": admin})
    return keeper_acl


@pytest.fixture(autouse=True)
def setup_rewards_manager(keeper_address):
    rewards_manager = Contract.from_abi(
        "BadgerRewardsManager",
        REWARDS_MANAGER,
        get_abi(Network.Ethereum, "rewards_manager"),
    )
    keeper_role = rewards_manager.KEEPER_ROLE()
    admin_role = rewards_manager.getRoleAdmin(keeper_role)
    admin = rewards_manager.getRoleMember(admin_role, 0)
    rewards_manager.grantRole(keeper_role, keeper_address, {"from": admin})
    return rewards_manager


@pytest.fixture
def strategy() -> contract:
    return web3.eth.contract(
        address=ETH_CVX_CRV_HELPER_STRATEGY,
        abi=get_abi(Network.Ethereum, "strategy"),
    )


@pytest.fixture
def rewards_manager_strategy() -> contract:
    return web3.eth.contract(
        address=ETH_SLP_DIGG_WBTC_STRATEGY,
        abi=get_abi(Network.Ethereum, "strategy"),
    )


@pytest.fixture
def btc_strategy() -> contract:
    return web3.eth.contract(
        address=ETH_HBTC_CRV_STRATEGY, abi=get_abi(Network.Ethereum, "strategy")
    )


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
def test_harvest_rewards_manager(keeper_address, harvester, rewards_manager_strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(keeper_address, "10 ether")

    harvester.keeper_acl = harvester.web3.eth.contract(
        address=harvester.web3.toChecksumAddress(
            MULTICHAIN_CONFIG[Network.Ethereum]["rewards_manager"]
        ),
        abi=get_abi(Network.Ethereum, "rewards_manager"),
    )

    xsushi = Contract.from_abi(
        "ERC20", web3.toChecksumAddress(XSUSHI), get_abi(Network.Ethereum, "erc20")
    )

    strategy_name = rewards_manager_strategy.functions.getName().call()

    # Hack: For some reason, harvest call() fails without first calling estimateGas()
    harvester.estimate_gas_fee(rewards_manager_strategy.address)

    before_claimable = xsushi.balanceOf(rewards_manager_strategy.address)
    harvester.logger.info(f"{strategy_name} before_claimable: {before_claimable}")

    harvester.harvest_rewards_manager(rewards_manager_strategy)

    after_claimable = xsushi.balanceOf(rewards_manager_strategy.address)
    harvester.logger.info(f"{strategy_name} after_claimable: {after_claimable}")

    assert (before_claimable != 0 and after_claimable == 0) or (
        before_claimable == after_claimable
    )


@pytest.mark.require_network("hardhat-fork")
def test_harvest(keeper_address, harvester, strategy):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(keeper_address, "10 ether")

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
        address=btc_strategy.functions.want().call(),
        abi=get_abi(Network.Ethereum, "erc20"),
    )
    # assert harvester.estimate_harvest_amount(btc_strategy) == 10


@pytest.mark.require_network("hardhat-fork")
def test_is_time_to_harvest(web3, chain, keeper_address, harvester, strategy):
    strategy_name = strategy.functions.getName().call()
    accounts[0].transfer(keeper_address, "10 ether")

    # Strategy should be harvestable at this point
    chain.sleep(hours(121))
    chain.mine(1)
    assert harvester.is_time_to_harvest(strategy) is True
    harvester.harvest(strategy)

    # Strategy shouldn't be harvestable
    assert harvester.is_time_to_harvest(strategy) is False

    # Should only be able to harvest after 120 hours
    chain.sleep(hours(72))
    chain.mine(1)
    assert harvester.is_time_to_harvest(strategy) is False
    chain.sleep(hours(49))
    chain.mine(1)
    assert harvester.is_time_to_harvest(strategy) is True
    harvester.harvest(strategy)


@pytest.mark.require_network("hardhat-fork")
def test_is_time_to_harvest_rewards_manager(
    web3,
    chain,
    keeper_address,
    harvester,
    rewards_manager_strategy,
    setup_rewards_manager,
):
    harvester.keeper_acl = harvester.web3.eth.contract(
        address=harvester.web3.toChecksumAddress(
            MULTICHAIN_CONFIG[Network.Ethereum]["rewards_manager"]
        ),
        abi=get_abi(Network.Ethereum, "rewards_manager"),
    )
    harvester.last_harvest_times = get_last_harvest_times(
        harvester.web3,
        harvester.keeper_acl,
        start_block=harvester.web3.eth.block_number - seconds_to_blocks(hours(120)),
        etherscan_key=os.getenv("ETHERSCAN_TOKEN"),
    )
    strategy_name = rewards_manager_strategy.functions.getName().call()
    accounts[0].transfer(keeper_address, "10 ether")

    # Strategy should be harvestable at this point
    chain.sleep(hours(121))
    chain.mine(1)
    assert harvester.is_time_to_harvest(rewards_manager_strategy) is True
    harvester.harvest_rewards_manager(rewards_manager_strategy)

    assert harvester.last_harvest_times[rewards_manager_strategy.address]

    # Strategy shouldn't be harvestable
    assert harvester.is_time_to_harvest(rewards_manager_strategy) is False

    # Should only be able to harvest after 120 hours
    chain.sleep(hours(72))
    chain.mine(1)
    assert harvester.is_time_to_harvest(rewards_manager_strategy) is False
    chain.sleep(hours(49))
    chain.mine(1)
    assert harvester.is_time_to_harvest(rewards_manager_strategy) is True
    harvester.harvest_rewards_manager(rewards_manager_strategy)
