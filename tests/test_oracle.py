from typing import Tuple
import pytest
from decimal import Decimal
from brownie import *
from web3 import Web3
import requests
import os

from src.oracle import Oracle
from tests.utils import *

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


@pytest.mark.require_network("mainnet-fork")
def test_correct_network():
    pass


@pytest.fixture
def oracle() -> Oracle:
    return Oracle(
        keeper_address=test_address,
        keeper_key=test_key,
        web3="http://127.0.0.1:8545",
    )


def test_digg_twap(oracle):
    assert oracle.get_digg_twap_centralized() / 10 ** 18 >= 0.1


def test_propose_report_centralized(oracle):
    assert oracle.propose_centralized_report_push()


# def test_rebase(rebaser):
#     """
#     Check if the contract should be harvestable, then call the harvest function

#     If the strategy should be harvested then claimable rewards should be positive before
#     and 0 after. If not then claimable rewards should be the same before and after
#     calling harvest
#     """
#     accounts[0].transfer(test_address, "1 ether")

#     assert rebaser.rebase() == {}


# def test_send_rebase_tx(rebaser):
#     accounts[0].transfer(test_address, "10 ether")

#     # TODO: mock send discord functions
#     rebaser._Rebaser__process_rebase() == {}
