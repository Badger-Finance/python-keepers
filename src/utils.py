import json
import logging
import os
from typing import Optional
from typing import Tuple

from hexbytes import HexBytes
from web3 import Web3

from config.constants import ABI_DIRS
from config.constants import NODE_URL_SECRET_NAMES
from config.enums import Network
from src.aws import get_secret

logger = logging.getLogger(__name__)


class NoHealthyNode(Exception):
    pass


def get_healthy_node(chain: Network) -> Web3:
    node_credentials = NODE_URL_SECRET_NAMES[chain]
    for node_credential in node_credentials:
        secret_name = node_credential["name"]
        secret_key = node_credential["key"]
        url = get_secret(secret_name, secret_key)
        if not url:
            continue
        node = Web3(Web3.HTTPProvider(url))
        try:
            node.eth.get_block_number()
            return node
        except Exception as e:
            logger.error(e)
    raise NoHealthyNode(f"No healthy nodes for chain: {chain}")


# TODO: Don't duplicate common abis for all chains
def get_abi(chain: str, contract_id: str):
    project_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(f"{project_root_dir}/abi/{ABI_DIRS[chain]}/{contract_id}.json") as f:
        return json.load(f)


def get_explorer(chain: Network, tx_hash: HexBytes) -> Optional[Tuple[str, str]]:
    if chain == Network.Ethereum:
        explorer_name = "Etherscan"
        explorer_url = f"https://etherscan.io/tx/{tx_hash.hex()}"
    elif chain == Network.Polygon:
        explorer_name = "Polygonscan"
        explorer_url = f"https://polygonscan.com/tx/{tx_hash.hex()}"
    elif chain == Network.Arbitrum:
        explorer_name = "Arbiscan"
        explorer_url = f"https://arbiscan.io/tx/{tx_hash.hex()}"
    elif chain == Network.Fantom:
        explorer_name = "Ftmscan"
        explorer_url = f"https://ftmscan.com/tx/{tx_hash.hex()}"
    else:
        return None

    return explorer_name, explorer_url
