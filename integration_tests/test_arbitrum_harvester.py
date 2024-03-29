from decimal import Decimal

import pytest
from brownie import Contract
from brownie import accounts
from brownie import web3
from hexbytes import HexBytes
from web3 import contract

from config.constants import ARB_ETH_USD_CHAINLINK
from config.constants import ARB_KEEPER_ACL
from config.enums import Network
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.general_harvester import GeneralHarvester
from src.utils import get_abi
from src.web3_utils import get_strategies_and_vaults


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
        ARB_KEEPER_ACL,
        get_abi(Network.Ethereum, "keeper_acl"),
    )
    harvester_key = keeper_acl.HARVESTER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(harvester_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(harvester_key, keeper_address, {"from": admin})
    return keeper_acl


@pytest.fixture
def strategy(request) -> contract:
    return web3.eth.contract(
        address=request.param,
        abi=get_abi(Network.Ethereum, "strategy"),
    )


@pytest.fixture
def harvester(keeper_address, keeper_key) -> GeneralHarvester:
    return GeneralHarvester(
        chain=Network.Arbitrum,
        web3=web3,
        keeper_acl=ARB_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ARB_ETH_USD_CHAINLINK,
    )


@pytest.mark.require_network("hardhat-arbitrum-fork")
def test_harvest(keeper_address, harvester):
    """
    Check if the contract should be harvestable, then call the harvest function

    If the strategy should be harvested then claimable rewards should be positive before
    and 0 after. If not then claimable rewards should be the same before and after
    calling harvest
    """
    accounts[0].transfer(keeper_address, "10 ether")

    strategies, _ = get_strategies_and_vaults(web3, Network.Arbitrum)

    for strategy in strategies:

        # Hack: For some reason, harvest call() fails without first calling estimateGas()
        harvester.estimate_gas_fee(strategy.address)

        before_claimable = harvester.estimate_harvest_amount(strategy.contract)
        print(f"{strategy.name} before_claimable: {before_claimable}")

        should_harvest = harvester.is_profitable()
        print(strategy.name, "should_harvest:", should_harvest)

        harvester.harvest(strategy.contract)

        after_claimable = harvester.estimate_harvest_amount(strategy.contract)
        print(f"{strategy.name} after_claimable: {after_claimable}")

        if should_harvest and before_claimable > 0:
            assert after_claimable / before_claimable < 0.01
        else:
            assert before_claimable == after_claimable
