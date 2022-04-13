# TODO: Move this module as a shared functionality to badger utils lib
import logging
import requests
import traceback

from decimal import Decimal
from hexbytes import HexBytes
from typing import Dict
from web3 import contract
from web3 import exceptions

from config.constants import GAS_LIMITS
from config.enums import Network

logger = logging.getLogger(__name__)


def get_gas_price_of_tx(
    web3: Web3, gas_oracle: contract, tx_hash: HexBytes, chain: str = Network.Ethereum
) -> Decimal:
    """Gets the actual amount of gas used by the transaction and converts
    it from gwei to USD value for monitoring.

    Args:
        web3 (Web3): web3 node instance
        gas_oracle (contract): web3 contract for chainlink gas unit / usd oracle
        tx_hash (HexBytes): tx id of target transaction
        chain (str): chain of tx (valid: eth, poly, arbitrum)

    Returns:
        Decimal: USD value of gas used in tx
    """
    try:
        tx_receipt = web3.eth.get_transaction_receipt(tx_hash)
    except exceptions.TransactionNotFound:
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    total_gas_used = Decimal(tx_receipt.get("gasUsed", 0))
    logger.info(f"gas used: {total_gas_used}")

    if chain == Network.Arbitrum:
        gas_prices = tx_receipt.get("feeStats", {}).get("paid", {})
        gas_cost_base = Decimal(sum([int(x, 16) for x in gas_prices.values()]) / 1e18)
    else:
        # ETH/Poly
        gas_price_base = Decimal(tx_receipt.get("effectiveGasPrice", 0) / 1e18)
        gas_cost_base = total_gas_used * gas_price_base

    gas_usd = Decimal(
        gas_oracle.functions.latestAnswer().call()
        / 10 ** gas_oracle.functions.decimals().call()
    )

    gas_price_of_tx = gas_cost_base * gas_usd
    logger.info(f"gas price of tx: {gas_price_of_tx}")

    return gas_price_of_tx


def get_latest_base_fee(
    web3: Web3, default: int = int(100e9)
) -> int:  # default to 100 gwei
    latest = web3.eth.get_block("latest")
    raw_base_fee = latest.get("baseFeePerGas", hex(default))
    if type(raw_base_fee) == str and raw_base_fee.startswith("0x"):
        base_fee = int(raw_base_fee, 0)
    else:
        base_fee = int(raw_base_fee)
    return base_fee


def get_effective_gas_price(web3: Web3) -> int:
    # TODO: Currently using max fee (per gas) that can be used for this tx.
    # TODO: Maybe use base + priority (for average).
    base_fee = get_latest_base_fee(web3)
    logger.info(f"latest base fee: {base_fee}")

    priority_fee = get_priority_fee(web3)
    logger.info(f"avg priority fee: {priority_fee}")
    # max fee aka gas price enough to get included in next 6 blocks
    gas_price = 2 * base_fee + priority_fee
    return gas_price


def get_priority_fee(
    web3: Web3,
    num_blocks: int = 4,
    percentile: int = 70,
    default_reward: int = int(10e9),
) -> int:
    """Calculates priority fee looking at current block - num_blocks historic
    priority fees at the given percentile and taking the average.

    Args:
        web3 (Web3): Web3 object
        num_blocks (int, optional): Number of historic blocks to look at. Defaults to 4.
        percentiles (int, optional): Percentile of transactions
            in blocks to use to analyze fees. Defaults to 70.
        default_reward (int, optional): If call fails,
            what default reward to use in gwei. Defaults to 10e9.

    Returns:
        int: [description]
    """
    try:
        gas_data = web3.eth.fee_history(num_blocks, "latest", [percentile])
    except ValueError:
        # Sometimes times out on hardhat-fork
        logger.warning(
            f"Couldn't fetch fee history, using default priority fee of {default_reward}"
        )
        gas_data = {}
    rewards = gas_data.get("reward", [[default_reward]])
    priority_fee = int(sum([r[0] for r in rewards]) / len(rewards))

    logger.info(f"priority fee: {priority_fee}")
    return priority_fee


def get_gas_price(web3: Web3, chain: Network) -> int:
    if chain == Network.Polygon:
        response = requests.get("https://gasstation-mainnet.matic.network").json()
        gas_price = web3.toWei(int(response.get("fast") * 1.1), "gwei")
    elif chain == Network.Ethereum:
        gas_price = get_effective_gas_price(web3)
    elif chain in [Network.Arbitrum, Network.Fantom]:
        gas_price = int(1.1 * web3.eth.gas_price)

    return gas_price


def get_tx_options(web3: Web3, chain: Network, address: str) -> Dict:
    options = {
        "nonce": web3.eth.get_transaction_count(address),
        "from": address,
        "gas": GAS_LIMITS[chain],
    }
    if chain == Network.Ethereum:
        options["maxPriorityFeePerGas"] = get_priority_fee(web3)
        options["maxFeePerGas"] = get_gas_price(web3, chain)
    else:
        options["gasPrice"] = get_gas_price(web3, chain)

    return options


def sign_and_send_tx(web3: Web3, tx: contract.TxParams, signer_key: str) -> HexBytes:
    try:
        signed_tx = web3.eth.account.sign_transaction(tx, private_key=signer_key)
        tx_hash = signed_tx.hash
        logger.info(f"attempted tx_hash: {tx_hash}")
        web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    except Exception:
        logger.error(f"Error in sending vote tx: {traceback.format_exc()}")
        tx_hash = HexBytes(0)

    return tx_hash
