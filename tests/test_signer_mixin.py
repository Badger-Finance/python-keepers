import os

from hexbytes import HexBytes
import pytest
from web3 import Web3

from src.signer_mixin import SignerMixin
from tests.utils import test_key, test_address


@pytest.fixture
def keeper_key() -> str:
    return test_key


@pytest.fixture
def keeper_address() -> str:
    return test_address


@pytest.fixture
def web3() -> Web3:
    return Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))


def test_hot_wallet_signer(keeper_key, keeper_address, web3):
    signer = SignerMixin(
        keeper_key=keeper_key,
        keeper_address=keeper_address,
        signing_method="pk",
        web3=web3,
    )

    # breakpoint()

    tx = signer.sign_transaction(
        {
            "nonce": 0,
            "to": keeper_address,
            "value": web3.toWei(0.1, "ether"),
            "gas": 2000000,
            "gasPrice": web3.toWei("50", "gwei"),
        }
    )

    assert tx.hash == HexBytes(
        "0x9144e550d119aa711645bd68c828e3f2d320fa8ffbcccc253dfac29c9c5499a3"
    )
    assert tx.rawTransaction == HexBytes(
        "0xf86d80850ba43b7400831e848094d88a9af149366d57aebc32d2eabadf93eda41a8488016345785d8a0000801ba09ca31dd5e58c1f63457dfb065db27e6a54a5bad856a1eddfe8e4ef71dd641097a017a6638afc999d14907edb66a56fb6cd809f033d70f5216fb1dad5fe33d8c249"
    )
