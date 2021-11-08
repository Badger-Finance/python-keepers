import os
import pytest
from brownie import accounts, Contract, web3
from decimal import Decimal
from hexbytes import HexBytes
from web3 import contract

from src.general_harvester import GeneralHarvester
from src.utils import get_abi, get_last_harvest_times, hours, get_secret
from tests.utils import test_address, test_key
from config.enums import Network

ETH_USD_CHAINLINK = web3.toChecksumAddress("0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612")
KEEPER_ACL = web3.toChecksumAddress("0x265820F3779f652f2a9857133fDEAf115b87db4B")

WBTC_WETH_SLP_STRATEGY = "0xA6827f0f14D0B83dB925B616d820434697328c22"  # WBTC-WETH-SLP
WETH_SUSHI_SLP_STRATEGY = "0x86f772C82914f5bFD168f99e208d0FC2C371e9C2"  # WETH-SUSHI-SLP


# def mock_get_last_harvest_times(web3, keeper_acl, start_block):
#     return get_last_harvest_times(
#         web3, keeper_acl, start_block, etherscan_key=os.getenv("ETHERSCAN_TOKEN")
#     )


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
    # monkeypatch.setattr(
    #     "src.general_harvester.get_last_harvest_times", mock_get_last_harvest_times
    # )


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


@pytest.fixture
def strategy(request) -> contract:
    return web3.eth.contract(
        address=request.param,
        abi=get_abi(Network.Ethereum, "strategy"),
    )


@pytest.fixture
def harvester(keeper_address, keeper_key) -> GeneralHarvester:
    return GeneralHarvester(
        chain="arbitrum",
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
    )


@pytest.mark.parametrize(
    "strategy", [WBTC_WETH_SLP_STRATEGY, WETH_SUSHI_SLP_STRATEGY], indirect=True
)
@pytest.mark.require_network("hardhat-arbitrum-fork")
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

    should_harvest = harvester.is_profitable()
    print(strategy_name, "should_harvest:", should_harvest)

    harvester.harvest(strategy)

    after_claimable = harvester.estimate_harvest_amount(strategy)
    print(f"{strategy_name} after_claimable: {after_claimable}")

    if should_harvest and before_claimable > 0:
        assert after_claimable / before_claimable < 0.01
    else:
        assert before_claimable == after_claimable
