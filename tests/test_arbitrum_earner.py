import logging
import os
import pytest
from brownie import accounts, Contract, web3
from decimal import Decimal
from hexbytes import HexBytes
from web3 import contract

from src.earner import Earner
from src.utils import get_abi, get_last_harvest_times, hours, get_secret
from tests.utils import test_address, test_key
from config.constants import EARN_OVERRIDE_THRESHOLD, EARN_PCT_THRESHOLD
from config.enums import Network

logger = logging.getLogger("test-eth-earner")

ETH_USD_CHAINLINK = web3.toChecksumAddress("0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612")
KEEPER_ACL = web3.toChecksumAddress("0x265820F3779f652f2a9857133fDEAf115b87db4B")

WBTC_WETH_SLP_STRATEGY = web3.toChecksumAddress(
    "0xA6827f0f14D0B83dB925B616d820434697328c22"
)  # WBTC-WETH-SLP
WETH_SUSHI_SLP_STRATEGY = web3.toChecksumAddress(
    "0x86f772C82914f5bFD168f99e208d0FC2C371e9C2"
)  # WETH-SUSHI-SLP
WBTC_WETH_SLP_VAULT = web3.toChecksumAddress(
    "0xFc13209cAfE8fb3bb5fbD929eC9F11a39e8Ac041"
)
WETH_SUSHI_SLP_VAULT = web3.toChecksumAddress(
    "0xe774d1fb3133b037aa17d39165b8f45f444f632d"
)


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
    logger.info("sent")


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
        KEEPER_ACL,
        get_abi(Network.Ethereum, "keeper_acl"),
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
        abi=get_abi(Network.Arbitrum, "strategy"),
    )


@pytest.fixture
def vault(request) -> contract:
    return web3.eth.contract(
        address=request.param,
        abi=get_abi(Network.Arbitrum, "vault"),
    )


@pytest.fixture
def earner(keeper_address, keeper_key) -> Earner:
    return Earner(
        chain=Network.Arbitrum,
        web3=web3,
        keeper_acl=KEEPER_ACL,
        keeper_address=keeper_address,
        keeper_key=keeper_key,
        base_oracle_address=ETH_USD_CHAINLINK,
    )


@pytest.mark.parametrize(
    "strategy,vault",
    [
        (WBTC_WETH_SLP_STRATEGY, WBTC_WETH_SLP_VAULT),
        (WETH_SUSHI_SLP_STRATEGY, WETH_SUSHI_SLP_VAULT),
    ],
    indirect=True,
)
@pytest.mark.require_network("hardhat-arbitrum-fork")
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
        address=vault.functions.token().call(), abi=get_abi(Network.Arbitrum, "erc20")
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
