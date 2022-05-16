import logging

import pytest
from brownie import *

from config.constants import DIGG_CENTRALIZED_ORACLE
from config.constants import DIGG_CHAINLINK_FORWARDER
from config.constants import ETH_DIGG_BTC_CHAINLINK
from config.enums import Network
from integration_tests.utils import mock_send_discord
from integration_tests.utils import test_address
from integration_tests.utils import test_key
from src.oracle import Oracle
from src.utils import get_abi
from src.utils import get_healthy_node

logger = logging.getLogger(__name__)


def mock_send_error(tx_type: str, error: Exception):
    logger.error(error)


@pytest.mark.require_network("hardhat-fork")
def test_correct_network():
    pass


@pytest.fixture
def keeper_address() -> str:
    return test_address


@pytest.fixture(autouse=True)
def setup_centralized_oracle(keeper_address):
    centralized_oracle = Contract.from_abi(
        "CentralizedOracle",
        DIGG_CENTRALIZED_ORACLE,
        get_abi(Network.Ethereum, "digg_centralized_oracle"),
    )
    oracle_role = centralized_oracle.ORACLE_ROLE()
    admin_role = centralized_oracle.getRoleAdmin(oracle_role)
    admin = centralized_oracle.getRoleMember(admin_role, 0)
    centralized_oracle.grantRole(oracle_role, keeper_address, {"from": admin})
    return centralized_oracle


@pytest.fixture(autouse=True)
def setup_chainlink_oracle(keeper_address):
    chainlink_oracle = Contract.from_abi(
        "ChainlinkOracle",
        DIGG_CHAINLINK_FORWARDER,
        get_abi(Network.Ethereum, "chainlink_forwarder"),
    )
    owner = chainlink_oracle.owner()
    chainlink_oracle.transferOwnership(keeper_address, {"from": owner})
    return chainlink_oracle


@pytest.fixture
def oracle() -> Oracle:
    oracle = Oracle(
        keeper_address=test_address,
        keeper_key=test_key,
        web3=get_healthy_node(Network.Ethereum)
    )
    oracle.web3 = web3
    return oracle


@pytest.fixture(autouse=True)
def mock_fns(monkeypatch):
    # TODO: Ideally should find a way to mock get_secret
    monkeypatch.setattr("src.oracle.send_success_to_discord", mock_send_discord)
    monkeypatch.setattr("src.oracle.send_oracle_error_to_discord", mock_send_error)


def test_digg_twap(oracle):
    accounts[0].transfer(test_address, "1 ether")
    oracle.get_digg_twap_centralized() / 10 ** 18 >= 0.1


@pytest.mark.require_network("hardhat-fork")
def test_propose_report_centralized(oracle):
    accounts[0].transfer(test_address, "1 ether")
    oracle.propose_centralized_report_push()


@pytest.mark.require_network("hardhat-fork")
def test_chainlink_forwarder(oracle):
    accounts[0].transfer(test_address, "1 ether")
    oracle.publish_chainlink_report()


@pytest.mark.require_network("hardhat-fork")
def test_is_negative_rebase(oracle):
    digg_btc_oracle = Contract.from_abi(
        "DiggBtcOracle",
        ETH_DIGG_BTC_CHAINLINK,
        get_abi(Network.Ethereum, "oracle"),
    )
    price = digg_btc_oracle.latestAnswer()
    if price < 95000000:
        assert oracle.is_negative_rebase() is True
    else:
        assert oracle.is_negative_rebase() is False
