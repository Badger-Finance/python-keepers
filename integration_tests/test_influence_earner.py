import logging
from decimal import Decimal

import pytest
from brownie import Contract
from brownie import accounts
from brownie import chain
from brownie import web3
from hexbytes import HexBytes

from config.constants import ETH_BVECVX_STRATEGY
from config.constants import ETH_BVECVX_VAULT
from config.constants import ETH_GRAVIAURA_STRATEGY
from config.constants import ETH_GRAVIAURA_VAULT
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.earner import Earner
from src.utils import get_abi

logger = logging.getLogger(__name__)

SECONDS_IN_WEEK = 604800
MAX_SLEEP_WEEKS = 18


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
    monkeypatch.setattr("src.earner.send_success_to_discord", mock_send_discord)
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
        MULTICHAIN_CONFIG[Network.Ethereum]["keeper_acl"],
        get_abi(Network.Ethereum, "keeper_acl"),
    )
    earner_key = keeper_acl.EARNER_ROLE()
    admin_role = keeper_acl.getRoleAdmin(earner_key)
    admin = keeper_acl.getRoleMember(admin_role, 0)
    keeper_acl.grantRole(earner_key, keeper_address, {"from": admin})
    return keeper_acl


@pytest.fixture
def earner(keeper_address, keeper_key) -> Earner:
    return Earner(
        chain=Network.Ethereum,
        web3=web3,
        keeper_acl=MULTICHAIN_CONFIG[Network.Ethereum]["keeper_acl"],
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=MULTICHAIN_CONFIG[Network.Ethereum]["gas_oracle"],
    )


@pytest.mark.require_network("hardhat-fork")
def test_graviaura_earn_strat_unlocked(keeper_address, earner):
    accounts[1].transfer(keeper_address, "10 ether")

    unlocker = Contract.from_explorer(ETH_GRAVIAURA_STRATEGY)
    locker = Contract.from_explorer(unlocker.LOCKER())
    want = Contract.from_explorer(unlocker.want())

    should_unlock = unlocker.checkUpkeep(HexBytes(0))[0]
    num_weeks_slept = 0

    # sleep until locks expire and we can unlock aura to strat
    while not should_unlock and num_weeks_slept <= MAX_SLEEP_WEEKS:
        num_weeks_slept += 1
        chain.sleep(SECONDS_IN_WEEK)
        chain.mine()
        should_unlock = unlocker.checkUpkeep(HexBytes(0))[0]
        logger.info(f"num weeks slept: {num_weeks_slept}")
        logger.info(f"should unlock: {should_unlock}")

    # store unlocked balances in strat and vault and locked balance of strat
    locked_bal_before = locker.lockedBalances(unlocker.address)[2]
    strat_bal_before = want.balanceOf(ETH_GRAVIAURA_STRATEGY)
    vault_bal_before = want.balanceOf(ETH_GRAVIAURA_VAULT)

    # process unlocks
    unlocker.performUpkeep(HexBytes(0), {"from": keeper_address})

    locked_bal_after = locker.lockedBalances(unlocker.address)[2]
    strat_bal_after = want.balanceOf(ETH_GRAVIAURA_STRATEGY)
    vault_bal_after = want.balanceOf(ETH_GRAVIAURA_VAULT)
    logger.info(f"strategy AURA before earn: {strat_bal_after}")
    logger.info(f"vault AURA before earn: {vault_bal_after}")

    # assert vault state is same, unlocked tokens in strat only increased
    assert vault_bal_before == vault_bal_after
    assert strat_bal_after > strat_bal_before

    strategy_contract = earner.web3.eth.contract(
        address=ETH_GRAVIAURA_STRATEGY,
        abi=get_abi(Network.Ethereum, "bvecvx_unlock_upkeep"),
    )

    vault_contract = earner.web3.eth.contract(
        address=ETH_GRAVIAURA_VAULT,
        abi=get_abi(Network.Ethereum, "vault_v1_5"),
    )

    # test earning will lock (includes unlocked in strat as part of outstanding calc)
    earner.earn(vault_contract, strategy_contract, sett_name="graviAURA")
    locked_bal_after = locker.lockedBalances(unlocker.address)[2]
    assert locked_bal_after > locked_bal_before


@pytest.mark.require_network("hardhat-fork")
def test_bvecvx_earn_strat_unlocked(keeper_address, earner):
    accounts[1].transfer(keeper_address, "10 ether")

    unlocker = Contract.from_explorer(ETH_BVECVX_STRATEGY)
    locker = Contract.from_explorer(unlocker.LOCKER())
    want = Contract.from_explorer(unlocker.want())

    should_unlock = unlocker.checkUpkeep(HexBytes(0))[0]
    num_weeks_slept = 0

    # sleep until locks expire and we can unlock cvx to strat
    while not should_unlock and num_weeks_slept <= MAX_SLEEP_WEEKS:
        num_weeks_slept += 1
        chain.sleep(SECONDS_IN_WEEK)
        chain.mine()
        should_unlock = unlocker.checkUpkeep(HexBytes(0))[0]
        logger.info(f"num weeks slept: {num_weeks_slept}")
        logger.info(f"should unlock: {should_unlock}")

    # store unlocked balances in strat and vault and locked balance of strat
    locked_bal_before = locker.lockedBalanceOf(unlocker.address)
    strat_bal_before = want.balanceOf(ETH_BVECVX_STRATEGY)
    vault_bal_before = want.balanceOf(ETH_BVECVX_VAULT)

    # process unlocks
    unlocker.performUpkeep(HexBytes(0), {"from": keeper_address})

    locked_bal_after = locker.lockedBalanceOf(unlocker.address)
    strat_bal_after = want.balanceOf(ETH_BVECVX_STRATEGY)
    vault_bal_after = want.balanceOf(ETH_BVECVX_VAULT)
    logger.info(f"strategy CVX before earn: {strat_bal_after}")
    logger.info(f"vault CVX before earn: {vault_bal_after}")

    # assert vault state is same, unlocked tokens in strat only increased
    assert vault_bal_before == vault_bal_after
    assert strat_bal_after > strat_bal_before

    strategy_contract = earner.web3.eth.contract(
        address=ETH_BVECVX_STRATEGY,
        abi=get_abi(Network.Ethereum, "bvecvx_unlock_upkeep"),
    )

    vault_contract = earner.web3.eth.contract(
        address=ETH_BVECVX_VAULT,
        abi=get_abi(Network.Ethereum, "vault_v1_5"),
    )

    # test earning will lock (includes unlocked in strat as part of outstanding calc)
    earner.earn(vault_contract, strategy_contract, sett_name="bveCVX")
    locked_bal_after = locker.lockedBalanceOf(unlocker.address)
    assert locked_bal_after > locked_bal_before
