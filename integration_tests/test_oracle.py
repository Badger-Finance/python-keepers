from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import logging
import requests
import os

from src.oracle import Oracle
from src.utils import get_abi
from integration_tests.utils import test_address, test_key, mock_send_discord
from config.enums import Network

logger = logging.getLogger("test-oracle")

os.environ[
    "DISCORD_WEBHOOK_URL"
] = "https://discord.com/api/webhooks/838956838636093491/OXDBt7dz6nn_AghoD5W8yhVjw7udBO6noHU8JNzbyAZMDgszvWAIJm9gAUikAdxTd03c"  # os.getenv("TEST_DISCORD_WEBHOOK_URL")
os.environ["ETH_USD_CHAINLINK"] = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
os.environ["GAS_LIMIT"] = "1000000"
os.environ[
    "UNI_SUBGRAPH"
] = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
os.environ["UNI_PAIR"] = "0xe86204c4eddd2f70ee00ead6805f917671f56c52"
os.environ[
    "SUSHI_SUBGRAPH"
] = "https://api.thegraph.com/subgraphs/name/sushiswap/exchange"
os.environ["SUSHI_PAIR"] = "0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3"
os.environ["CENTRALIZED_ORACLE"] = "0x73083058e0f61D3fc7814eEEDc39F9608B4546d7"
os.environ["CHAINLINK_FORWARDER"] = "0xB572f69edbfC946af11a1b3ef8D5c2f41D38a642"
os.environ["DIGG_BTC_CHAINLINK"] = "0x418a6c98cd5b8275955f08f0b8c1c6838c8b1685"


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
        os.getenv("CENTRALIZED_ORACLE"),
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
        os.getenv("CHAINLINK_FORWARDER"),
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
        os.getenv("DIGG_BTC_CHAINLINK"),
        get_abi(Network.Ethereum, "oracle"),
    )
    price = digg_btc_oracle.latestAnswer()
    if price < 95000000:
        assert oracle.is_negative_rebase() == True
    else:
        assert oracle.is_negative_rebase() == False
