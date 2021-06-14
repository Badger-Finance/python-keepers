import json
from brownie import *

test_address = "0xD88a9aF149366d57aEbc32D2eABAdf93EdA41A84"
test_key = "0f0bdc830bde4be43c3a54c369c6f6a94ac9071911dc3913e35ce5ed8fe955b9"


def get_abi(contract_id: str) -> dict:
    with open(f"./abi/eth/{contract_id}.json") as f:
        return json.load(f)


def get_strategy(strategy_address: str) -> Contract:
    strategy = Contract.from_abi(
        "Strategy",
        strategy_address,
        get_abi("strategy"),
    )
    gov = strategy.governance()
    strategy.setKeeper(test_address, {"from": gov})
    return strategy
