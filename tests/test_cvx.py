import pytest
from brownie import accounts, Contract, web3
from web3 import contract

from src.general_harvester import GeneralHarvester
from src.utils import get_abi
from tests.utils import test_address, test_key

ETH_USD_CHAINLINK = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
KEEPER_ACL = "0x711A339c002386f9db409cA55b6A35a604aB6cF6"
CVX_HELPER_STRATEGY = "0xBCee2c6CfA7A4e29892c3665f464Be5536F16D95"
CVX_CRV_HELPER_STRATEGY = "0x826048381d65a65DAa51342C51d464428d301896"
HBTC_STRATEGY = "0xf4146A176b09C664978e03d28d07Db4431525dAd"


# Uses EIP-1559 txs which ganache-cli doesn't support
@pytest.mark.require_network("hardhat-fork")
def test_correct_network():
    pass


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
        address=CVX_CRV_HELPER_STRATEGY, abi=get_abi("eth", "strategy")
    )


@pytest.fixture
def btc_strategy() -> contract:
    return web3.eth.contract(
        address=web3.toChecksumAddress(HBTC_STRATEGY), abi=get_abi("eth", "strategy")
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

    before_claimable = harvester.estimate_harvest_amount(strategy.address)
    print(f"{strategy_name} before_claimable: {before_claimable}")

    # current_price_eth = harvester.get_current_rewards_price()
    # gas_fee = harvester.estimate_gas_fee(strategy.address)

    should_harvest = harvester.is_profitable()
    print(strategy_name, "should_harvest:", should_harvest)

    harvester.harvest(strategy)

    after_claimable = harvester.estimate_harvest_amount(strategy.address)
    print(f"{strategy_name} after_claimable: {after_claimable}")

    assert (should_harvest and before_claimable != 0 and after_claimable == 0) or (
        before_claimable == after_claimable and not should_harvest
    )


def test_btc_profit_est(harvester, btc_strategy):
    want = web3.eth.contract(
        address=btc_strategy.functions.want().call(), abi=get_abi("eth", "erc20")
    )
    assert harvester.estimate_harvest_amount(btc_strategy, want) == 10
