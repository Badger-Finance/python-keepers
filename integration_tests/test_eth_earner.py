import logging
from decimal import Decimal
from typing import List

import pytest
from brownie import Contract
from brownie import accounts
from brownie import web3
from hexbytes import HexBytes

from config.constants import EARN_OVERRIDE_THRESHOLD
from config.constants import ETH_BVECVX_STRATEGY
from config.constants import ETH_BVECVX_VAULT
from config.constants import ETH_GRAVIAURA_STRATEGY
from config.constants import ETH_GRAVIAURA_VAULT
from config.constants import MULTICHAIN_CONFIG
from config.enums import Network
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.data_classes.contract import Contract as BadgerContract
from src.earner import Earner
from src.settings.earn_settings import ETH_EARN_SETTINGS
from src.utils import get_abi
from src.web3_utils import get_strategies_and_vaults

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
def test_earn(keeper_address, earner):
    """
    Check if the contract should be earnable, then call the earn function

    If the strategy should be earned then the vault balance before should be in the strat
    and 0 after.
    """
    accounts[0].transfer(keeper_address, "10 ether")
    strategies, vaults = get_strategies_and_vaults(web3, Network.Ethereum)

    vaults_to_earn: List[BadgerContract] = []
    strats_to_earn: List[BadgerContract] = []

    for strategy, vault in zip(strategies, vaults):
        if vault.address not in ETH_EARN_SETTINGS.influence_vaults:
            vaults_to_earn.append(vault)
            strats_to_earn.append(strategy)

    assert ETH_BVECVX_VAULT not in vaults_to_earn
    assert ETH_GRAVIAURA_VAULT not in vaults_to_earn
    assert ETH_BVECVX_STRATEGY not in strats_to_earn
    assert ETH_GRAVIAURA_STRATEGY not in strats_to_earn

    for strategy, vault in zip(strats_to_earn, vaults_to_earn):

        override_threshold = EARN_OVERRIDE_THRESHOLD

        want = earner.web3.eth.contract(
            address=vault.contract.functions.token().call(),
            abi=get_abi(Network.Ethereum, "erc20"),
        )

        vault_before, strategy_before = earner.get_balances(
            vault.contract, strategy.contract, want
        )

        logger.info(f"{strategy.name} vault_before: {vault_before}")
        logger.info(f"{strategy.name} strategy_before: {strategy_before}")

        should_earn = earner.should_earn(
            override_threshold, vault_before, strategy_before
        )
        logger.info(f"{strategy.name} should_earn: {should_earn}")

        earner.earn(vault.contract, strategy.contract, sett_name=strategy.name)

        vault_after, strategy_after = earner.get_balances(
            vault.contract, strategy.contract, want
        )
        logger.info(f"{strategy.name} vault_after: {vault_after}")
        logger.info(f"{strategy.name} strategy_after: {strategy_after}")

        if should_earn:
            assert vault_after < vault_before
            assert strategy_after > strategy_before
        else:
            assert vault_before == vault_after
            assert strategy_before == strategy_after


@pytest.mark.require_network("hardhat-fork")
def test_bvecvx_unlock(keeper_address, earner):
    accounts[1].transfer(keeper_address, "10 ether")

    unlocker = Contract.from_explorer(ETH_BVECVX_STRATEGY)
    locker = Contract.from_explorer("0x72a19342e8F1838460eBFCCEf09F6585e32db86E")

    should_unlock = unlocker.checkUpkeep(HexBytes(0))[0]

    locked_bal_before = locker.lockedBalanceOf(unlocker.address)

    earner.bvecvx_unlock()

    locked_bal_after = locker.lockedBalanceOf(unlocker.address)

    if should_unlock:
        assert locked_bal_after < locked_bal_before
        # run again since we should have no expired locks
        locked_bal_before = locker.lockedBalanceOf(unlocker.address)
        earner.bvecvx_unlock()
        locked_bal_after = locker.lockedBalanceOf(unlocker.address)

    assert locked_bal_before == locked_bal_after
