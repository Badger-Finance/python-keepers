import logging
import os
import pytest
from brownie import accounts, Contract, web3
from decimal import Decimal
from hexbytes import HexBytes
from web3 import contract

from src.earner import Earner
from src.utils import (
    get_abi,
    get_last_harvest_times,
    hours,
    get_secret,
    get_strategies_and_vaults,
)
from tests.utils import test_address, test_key
from config.constants import (
    EARN_OVERRIDE_THRESHOLD,
    EARN_PCT_THRESHOLD,
    MULTICHAIN_CONFIG,
)
from config.enums import Network

logger = logging.getLogger("test-eth-earner")


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
    STRATEGIES, VAULTS = get_strategies_and_vaults(web3, Network.Ethereum)

    for strategy, vault in zip(STRATEGIES, VAULTS):

        strategy_name = strategy.functions.getName().call()

        override_threshold = EARN_OVERRIDE_THRESHOLD

        want = earner.web3.eth.contract(
            address=vault.functions.token().call(),
            abi=get_abi(Network.Ethereum, "erc20"),
        )

        vault_before, strategy_before = earner.get_balances(vault, strategy, want)

        logger.info(f"{strategy_name} vault_before: {vault_before}")
        logger.info(f"{strategy_name} strategy_before: {strategy_before}")

        should_earn = earner.should_earn(
            override_threshold, vault_before, strategy_before
        )
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
