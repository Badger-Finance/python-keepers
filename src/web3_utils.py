import logging
import requests

from hexbytes import HexBytes
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from web3 import Web3
from web3 import contract
from web3 import exceptions

from config.constants import MULTICHAIN_CONFIG
from config.enums import Network, VaultVersion
from src.registry_utils import get_production_vaults
from src.utils import get_abi
from src.aws import get_secret

logger = logging.getLogger(__name__)


def get_strategies_from_registry(node: Web3, chain: str) -> list:
    strategies = []

    registry = node.eth.contract(
        address=node.toChecksumAddress(MULTICHAIN_CONFIG[chain]["registry"]),
        abi=get_abi(chain, "registry"),
    )

    for vault_owner in MULTICHAIN_CONFIG[chain]["vault_owner"]:
        vault_owner = node.toChecksumAddress(vault_owner)

        for vault_address in registry.functions.getVaults("v1", vault_owner).call():
            strategy, _ = get_strategy_from_vault(node, chain, vault_address)
            strategies.append(strategy)

    return strategies


def get_strategy_from_vault(
    node: Web3, chain: str, vault_address: str, version: VaultVersion = VaultVersion.v1
) -> (contract, contract):
    if version == VaultVersion.v1_5:
        vault_contract = node.eth.contract(
            address=vault_address, abi=get_abi(chain, "vault_v1_5")
        )
        strategy_address = vault_contract.functions.strategy().call()
    else:
        vault_contract = node.eth.contract(
            address=vault_address, abi=get_abi(chain, "vault")
        )
        token_address = vault_contract.functions.token().call()
        controller_address = vault_contract.functions.controller().call()

        controller_contract = node.eth.contract(
            address=controller_address, abi=get_abi(chain, "controller")
        )

        strategy_address = controller_contract.functions.strategies(
            token_address
        ).call()

    # TODO: handle v1 vs v2 strategy abi
    strategy_contract = node.eth.contract(
        address=strategy_address, abi=get_abi(chain, "strategy")
    )

    return strategy_contract, vault_contract


def get_strategies_and_vaults(node: Web3, chain: str) -> Tuple[List[Dict], List[Dict]]:
    strategies = []
    vaults = []

    vaults_by_version = get_production_vaults(node, chain)

    for version in vaults_by_version.keys():
        for vault_address in vaults_by_version[version].keys():
            strategy, vault = get_strategy_from_vault(
                node, chain, vault_address, version=version
            )

            vault_data = {
                "address": vault_address,
                "contract": vault,
                "name": vaults_by_version[version][vault_address]["name"],
            }
            vaults.append(vault_data)

            strategy_data = {
                "address": strategy.address,
                "contract": strategy,
                "name": vaults_by_version[version][vault_address]["name"],
            }
            strategies.append(strategy_data)

    return strategies, vaults


def confirm_transaction(
    web3: Web3, tx_hash: HexBytes, timeout: int = 120, max_block: int = None
) -> Tuple[bool, str]:
    """Waits for transaction to appear within
        a given timeframe or before a given block (if specified), and then times out.

    Args:
        web3 (Web3): Web3 instance
        tx_hash (HexBytes): Transaction hash to identify transaction to wait on.
        timeout (int, optional): Timeout in seconds. Defaults to 60.
        max_block (int, optional): Max block number to wait until. Defaults to None.

    Returns:
        bool: True if transaction was confirmed, False otherwise.
        msg: Log message.
    """
    logger.info(f"tx_hash before confirm: {tx_hash.hex()}")

    while True:
        try:
            web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            msg = f"Transaction {tx_hash.hex()} succeeded!"
            logger.info(msg)
            return True, msg
        except exceptions.TimeExhausted:
            if max_block is None or web3.eth.block_number > max_block:
                if max_block is None:
                    msg = f"Transaction {tx_hash.hex()} timed out, not included in block yet."
                else:
                    msg = f"Transaction {tx_hash.hex()} was not included in the block."
                logger.error(msg)
                return False, msg
            else:
                continue
        except Exception as e:
            msg = f"Error waiting for {tx_hash.hex()}. Error: {e}."
            logger.error(msg)
            return False, msg


def get_last_harvest_times(
    web3: Web3,
    keeper_acl: contract.Contract,
    start_block: int = 0,
    chain: Optional[Network] = Network.Ethereum,
) -> Optional[Dict]:
    """Fetches the latest harvest timestamps
        of strategies from Etherscan API which occur after `start_block`.
    NOTE: Temporary function until Harvested events are emitted from all strategies.

    Args:
        web3 (Web3): Web3 node instance.
        keeper_acl (contract): Keeper ACL web3 contract instance.
        start_block (int, optional):
            Minimum block number to start fetching harvest timestamps from. Defaults to 0.
        chain (Network)

    Returns:
        dict: Dictionary of strategy addresses and their latest harvest timestamps.
    """
    if chain == Network.Ethereum:
        api_key = get_secret("keepers/etherscan", "ETHERSCAN_TOKEN")
        url = "https://api.etherscan.io/api"
    elif chain == Network.Fantom:
        api_key = get_secret("keepers/ftmscan", "FTMSCAN_TOKEN")
        url = "https://api.ftmscan.com/api"
    else:
        logger.warning(f"Unknown chain {chain}. Can't fetch harvest times")
        return

    payload = {
        "module": "account",
        "action": "txlist",
        "address": keeper_acl.address,
        "startblock": start_block,
        "endblock": web3.eth.block_number,
        "sort": "desc",
        "apikey": api_key,
    }
    try:
        response = requests.get(url, params=payload)
        response.raise_for_status()  # Raise HTTP errors

        data = response.json()
        times = {}
        for tx in data["result"]:
            if (
                tx["to"] == ""
                or web3.toChecksumAddress(tx["to"]) != keeper_acl.address
                or "input" not in tx
            ):
                continue
            fn, args = keeper_acl.decode_function_input(tx["input"])
            if (
                str(fn)
                in [
                    "<Function harvest(address)>",
                    "<Function harvestNoReturn(address)>",
                ]
                and args["strategy"] not in times
            ):
                times[args["strategy"]] = int(tx["timeStamp"])
            elif (
                str(fn) == "<Function harvestMta(address)>"
                and args["voterProxy"] not in times
            ):
                times[args["voterProxy"]] = int(tx["timeStamp"])
        return times
    except (KeyError, requests.HTTPError):
        raise ValueError("Last harvest time couldn't be fetched")
