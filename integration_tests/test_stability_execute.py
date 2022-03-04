from decimal import Decimal
from hexbytes import HexBytes
import logging
import pytest
from brownie import accounts, Contract, web3
from web3 import contract

from config.constants import (
    ETH_ETH_USD_CHAINLINK,
    ETH_KEEPER_ACL,
    ETH_STABILIZE_STRATEGY,
)
from src.utils import get_abi
from integration_tests.utils import test_address, test_key
from src.eth.stability_executor import StabilityExecutor
from config.enums import Network

logger = logging.getLogger("test_rebalance")


def mock_send_discord(
    tx_hash: HexBytes,
    tx_type: str,
    gas_cost: Decimal = None,
    amt: Decimal = None,
    sett_name: str = None,
    chain: str = Network.Ethereum,
):
    print("sent")


def mock_fee_history(num_blocks: int, block: str, range: list) -> dict:
    return {
        "baseFeePerGas": [70794069162, 70928497842, 67155593128],
        "gasUsedRatio": [0.5075954601059917, 0.2872277011952031],
        "oldestBlock": 13090575,
        "reward": [[8849258646], [2820000000]],
    }


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
def patch_stability_executor(monkeypatch):
    monkeypatch.setattr(
        "src.eth.stability_executor.send_success_to_discord", mock_send_discord
    )
    monkeypatch.setattr(
        "tests.test_stability_execute.web3.eth.fee_history", mock_fee_history
    )


@pytest.fixture(autouse=True)
def setup_keeper_acl(keeper_address):
    keeper_acl = Contract.from_abi(
        "KeeperAccessControl",
        ETH_KEEPER_ACL,
        get_abi(Network.Ethereum, "keeper_acl"),
    )
    harvester_key = keeper_acl.HARVESTER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(harvester_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(harvester_key, keeper_address, {"from": admin})
    return keeper_acl


@pytest.fixture(autouse=True)
def setup_stability_vault(keeper_address):
    stability_strategy = Contract.from_abi(
        "StabilizeStrategyDiggV1",
        ETH_STABILIZE_STRATEGY,
        get_abi(Network.Ethereum, "stability_strat"),
    )
    governance = stability_strategy.governance()
    stability_strategy.setKeeper(keeper_address, {"from": governance})
    return stability_strategy


@pytest.fixture
def strategy() -> contract:
    return web3.eth.contract(
        address=ETH_STABILIZE_STRATEGY, abi=get_abi(Network.Ethereum, "stability_strat")
    )


@pytest.fixture
def stability_executor(keeper_address, keeper_key) -> StabilityExecutor:
    return StabilityExecutor(
        web3=web3,
        keeper_acl=ETH_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_ETH_USD_CHAINLINK,
        use_flashbots=False,
    )


def test_execute(keeper_address, stability_executor, strategy):
    """
    Call the rebalance function
    """
    accounts[0].transfer(keeper_address, "10 ether")

    digg_price_bf = strategy.functions.lastDiggPrice().call() / 10 ** 18
    logger.info(f"digg price before: {digg_price_bf}")

    stability_executor.execute_batch(strategy)

    digg_price_aft = strategy.functions.lastDiggPrice().call() / 10 ** 18
    logger.info(f"digg price after: {digg_price_aft}")

    trade_amt = strategy.functions.tradeAmountLeft().call()
    logger.info(f"trade amount: {trade_amt}")

    # TODO: figure out how to mock trade amount and check calls
