from dataclasses import dataclass
from web3 import contract as web3_contract


@dataclass
class Contract:
    """Represents smart contract."""

    name: str
    contract: web3_contract
    address: str
