from decimal import Decimal

import pytest
from brownie import Contract
from brownie import accounts
from brownie import web3
from hexbytes import HexBytes
from web3 import contract

from config.constants import ETH_IBMBTC_STRATEGY
from config.constants import ETH_MBTC_HBTC_STRATEGY
from config.constants import MSTABLE_VOTER_PROXY
from config.constants import MTA
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.general_harvester import GeneralHarvester
from src.misc_utils import hours
from src.utils import get_abi
from src.web3_utils import get_last_harvest_times

ETH_USD_CHAINLINK = web3.toChecksumAddress(
    MULTICHAIN_CONFIG[Network.Ethereum]["gas_oracle"]
)
KEEPER_ACL = web3.toChecksumAddress(MULTICHAIN_CONFIG[Network.Ethereum]["keeper_acl"])


MSTABLE_STRATEGIES = [ETH_MBTC_HBTC_STRATEGY, ETH_IBMBTC_STRATEGY]


def mock_get_last_harvest_times(web3, keeper_acl, start_block):
    return get_last_harvest_times(web3, keeper_acl, start_block)


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


def get_mstable_strategies():
    strategies = []
    for strategy_address in MSTABLE_STRATEGIES:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi(Network.Ethereum, "strategy"),
        )
        strategies.append(
            {
                "name": strategy.functions.getName().call(),
                "contract": strategy,
            }
        )
    return strategies


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


@pytest.fixture()
def voter_proxy() -> contract:
    return web3.eth.contract(
        address=web3.toChecksumAddress(MSTABLE_VOTER_PROXY),
        abi=get_abi(Network.Ethereum, "mstable_voter_proxy"),
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


@pytest.fixture()
def mta() -> contract:
    return web3.eth.contract(
        address=web3.toChecksumAddress(MTA),
        abi=get_abi(Network.Ethereum, "erc20"),
    )


@pytest.mark.require_network("hardhat-fork")
def test_mstable_harvest(keeper_address, harvester, voter_proxy, mta):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(keeper_address, "10 ether")

    strategies = get_mstable_strategies()

    before_mta = {
        strategy["name"]: mta.functions.balanceOf(strategy["contract"].address).call()
        for strategy in strategies
    }

    for strategy in strategies:
        strategy_name = strategy["name"]
        harvester.logger.info(
            f"{strategy_name} before_mta: {before_mta[strategy_name]}"
        )

    # Hack: For some reason, harvest call() fails without first calling estimateGas()
    harvester.estimate_gas_fee(voter_proxy.address, function="harvestMta")
    # Run harvestMta
    harvester.harvest_mta(voter_proxy)

    after_mta = {
        strategy["name"]: mta.functions.balanceOf(strategy["contract"].address).call()
        for strategy in strategies
    }

    for strategy in strategies:
        strategy_name = strategy["name"]
        harvester.logger.info(f"{strategy_name} after_mta: {after_mta[strategy_name]}")

    assert all(
        [
            after_mta[strategy["name"]] > before_mta[strategy["name"]]
            for strategy in strategies
        ]
    )

    for strategy in strategies:
        strategy_name = strategy["name"]

        # Hack: For some reason, harvest call() fails without first calling estimateGas()
        harvester.estimate_gas_fee(strategy["contract"].address)

        before_claimable = harvester.estimate_harvest_amount(strategy["contract"])
        harvester.logger.info(f"{strategy_name} before_claimable: {before_claimable}")

        # current_price_eth = harvester.get_current_rewards_price()
        # gas_fee = harvester.estimate_gas_fee(strategy.address)

        should_harvest = harvester.is_profitable()
        harvester.logger.info(f"{strategy_name} should_harvest: {should_harvest}")

        harvester.harvest(strategy["contract"])

        after_claimable = harvester.estimate_harvest_amount(strategy["contract"])
        harvester.logger.info(f"{strategy_name} after_claimable: {after_claimable}")

        assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
            before_claimable == after_claimable and not should_harvest
        )


@pytest.mark.require_network("hardhat-fork")
def test_conditional_mstable_harvest(
    chain, keeper_address, harvester, voter_proxy, mta
):
    strategies = get_mstable_strategies()
    accounts[0].transfer(keeper_address, "10 ether")

    chain.sleep(hours(121))
    chain.mine(1)
    # Strategy should be harvestable at this point
    assert harvester.is_time_to_harvest(voter_proxy) is True
    for strategy in strategies:
        assert harvester.is_time_to_harvest(strategy["contract"]) is True

    harvester.harvest_mta(voter_proxy)
    for strategy in strategies:
        harvester.harvest(strategy["contract"])

    # Strategy shouldn't be harvestable
    assert harvester.is_time_to_harvest(voter_proxy) is False
    for strategy in strategies:
        assert harvester.is_time_to_harvest(strategy["contract"]) is False

    chain.sleep(hours(72))
    chain.mine(1)
    assert harvester.is_time_to_harvest(voter_proxy) is False
    for strategy in strategies:
        assert harvester.is_time_to_harvest(strategy["contract"]) is False
    # Strategy should be harvestable again after 120 hours
    chain.sleep(hours(49))
    chain.mine(1)
    assert harvester.is_time_to_harvest(voter_proxy) is True
    for strategy in strategies:
        assert harvester.is_time_to_harvest(strategy["contract"]) is True

    harvester.harvest_mta(voter_proxy)
    for strategy in strategies:
        harvester.harvest(strategy["contract"])
