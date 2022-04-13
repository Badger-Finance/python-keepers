import logging
import pytest

from brownie import Contract
from brownie import accounts
from brownie import web3
from decimal import Decimal
from hexbytes import HexBytes
from web3 import contract

from config.constants import FTM_GAS_ORACLE
from config.constants import FTM_KEEPER_ACL
from config.constants import FTM_OXD_BVEOXD_STRATEGY
from config.constants import FTM_OXD_BVEOXD_VAULT
from config.constants import EARN_OVERRIDE_THRESHOLD
from config.enums import Network
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.earner import Earner
from src.utils import get_abi

logger = logging.getLogger(__name__)


def mock_send_discord(
    tx_hash: HexBytes,
    tx_type: str,
    gas_cost: Decimal = None,
    amt: Decimal = None,
    sett_name: str = None,
    chain: str = Network.Ethereum,
    url: str = None,
):
    logger.info("sent")


@pytest.fixture(autouse=True)
def mock_fns(monkeypatch):
    # TODO: Ideally should find a way to mock get_secret
    monkeypatch.setattr("src.earner.send_success_to_discord", mock_send_discord)


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
        FTM_KEEPER_ACL,
        get_abi(Network.Fantom, "keeper_acl"),
    )
    earner_key = keeper_acl.EARNER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(earner_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(earner_key, keeper_address, {"from": admin})
    return keeper_acl


@pytest.fixture
def strategy(request) -> contract:
    return web3.eth.contract(
        address=request.param,
        abi=get_abi(Network.Fantom, "strategy"),
    )


@pytest.fixture
def vault(request) -> contract:
    return web3.eth.contract(
        address=request.param,
        abi=get_abi(Network.Fantom, "vault_v1_5"),
    )


@pytest.fixture
def earner(keeper_address, keeper_key) -> Earner:
    return Earner(
        chain=Network.Fantom,
        web3=web3,
        keeper_acl=FTM_KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=FTM_GAS_ORACLE,
    )


@pytest.mark.parametrize(
    "strategy,vault",
    [
        (FTM_OXD_BVEOXD_STRATEGY, FTM_OXD_BVEOXD_VAULT),
    ],
    indirect=True,
)
@pytest.mark.require_network("ftm-main-fork")
def test_earn(keeper_address, earner, strategy, vault):
    """
    Check if the contract should be earnable, then call the earn function

    If the strategy should be earned then the vault balance before should be in the strat
    and 0 after.
    """
    accounts[0].transfer(keeper_address, "10 ether")

    strategy_name = strategy.functions.getName().call()

    override_threshold = earner.web3.toWei(EARN_OVERRIDE_THRESHOLD, "ether")

    want = earner.web3.eth.contract(
        address=vault.functions.token().call(), abi=get_abi(Network.Fantom, "erc20")
    )

    vault_before, strategy_before = earner.get_balances(vault, strategy, want)

    logger.info(f"{strategy_name} vault_before: {vault_before}")
    logger.info(f"{strategy_name} strategy_before: {strategy_before}")

    should_earn = earner.should_earn(override_threshold, vault_before, strategy_before)
    logger.info(f"{strategy_name} should_earn: {should_earn}")

    earner.earn(vault, strategy)

    vault_after, strategy_after = earner.get_balances(vault, strategy, want)
    logger.info(f"{strategy_name} vault_after: {vault_after}")
    logger.info(f"{strategy_name} strategy_after: {strategy_after}")

    if should_earn:
        assert vault_after < vault_before
        assert strategy_after > strategy_before
    else:
        assert vault_before == vault_after
        assert strategy_before == strategy_after


@pytest.mark.parametrize(
    "strategy,vault",
    [
        (FTM_OXD_BVEOXD_STRATEGY, FTM_OXD_BVEOXD_VAULT),
    ],
    indirect=True,
)
@pytest.mark.require_network("ftm-main-fork")
def test_bveoxd_vote(keeper_address, earner, strategy, vault):
    earner.bveoxd_vote()
