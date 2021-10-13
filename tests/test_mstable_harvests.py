import os
import pytest
from brownie import accounts, interface, Contract, web3
from decimal import Decimal
from hexbytes import HexBytes
from web3 import contract

from config.constants import MULTICHAIN_CONFIG
from src.general_harvester import GeneralHarvester
from src.utils import get_abi, get_last_harvest_times
from tests.utils import test_address, test_key

ETH_USD_CHAINLINK = web3.toChecksumAddress(MULTICHAIN_CONFIG["eth"]["gas_oracle"])
KEEPER_ACL = web3.toChecksumAddress(MULTICHAIN_CONFIG["eth"]["keeper_acl"])

MSTABLE_VOTER_PROXY = "0x10D96b1Fd46Ce7cE092aA905274B8eD9d4585A6E"
MSTABLE_STRATEGIES = [
    "0x54D06A0E1cE55a7a60Ee175AbCeaC7e363f603f3",  # mBTC/hBTC mstable
    "0xd409C506742b7f76f164909025Ab29A47e06d30A",  # ibmBTC mstable
]
MTA = "0xa3bed4e1c75d00fa6f4e5e6922db7261b5e9acd2"


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
        get_abi("eth", "keeper_acl"),
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
        abi=get_abi("eth", "mstable_voter_proxy"),
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
        abi=get_abi("eth", "erc20"),
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

    strategies = []
    for strategy_address in MSTABLE_STRATEGIES:
        strategy = web3.eth.contract(
            address=web3.toChecksumAddress(strategy_address),
            abi=get_abi("eth", "strategy"),
        )
        strategies.append(
            {
                "name": strategy.functions.getName().call(),
                "contract": strategy,
            }
        )

    before_mta = {
        strategy["name"]: mta.functions.balanceOf(strategy["contract"].address).call()
        for strategy in strategies
    }

    for strategy in strategies:
        strategy_name = strategy["name"]
        print(f"{strategy_name} before_mta: {before_mta[strategy_name]}")

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
        print(f"{strategy_name} after_mta: {after_mta[strategy_name]}")

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
        print(f"{strategy_name} before_claimable: {before_claimable}")

        # current_price_eth = harvester.get_current_rewards_price()
        # gas_fee = harvester.estimate_gas_fee(strategy.address)

        should_harvest = harvester.is_profitable()
        print(strategy_name, "should_harvest:", should_harvest)

        harvester.harvest(strategy["contract"])

        after_claimable = harvester.estimate_harvest_amount(strategy["contract"])
        print(f"{strategy_name} after_claimable: {after_claimable}")

        assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
            before_claimable == after_claimable and not should_harvest
        )
