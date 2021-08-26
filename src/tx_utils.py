from decimal import Decimal
from hexbytes import HexBytes
import logging
from web3 import Web3, contract, exceptions

logger = logging.getLogger("tx-utils")


def get_gas_price_of_tx(
    web3: Web3, gas_oracle: contract, tx_hash: HexBytes, chain: str = "eth"
) -> Decimal:
    """Gets the actual amount of gas used by the transaction and converts
    it from gwei to USD value for monitoring.

    Args:
        web3 (Web3): web3 node instance
        gas_oracle (contract): web3 contract for chainlink gas unit / usd oracle
        tx_hash (HexBytes): tx id of target transaction
        chain (str): chain of tx (valid: eth, poly)

    Returns:
        Decimal: USD value of gas used in tx
    """
    try:
        tx_receipt = web3.eth.get_transaction_receipt(tx_hash)
    except exceptions.TransactionNotFound:
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    logger.info(f"tx: {tx_receipt}")
    total_gas_used = Decimal(tx_receipt.get("gasUsed", 0))
    logger.info(f"gas used: {total_gas_used}")
    if chain == "eth":
        gas_price_base = Decimal(tx_receipt.get("effectiveGasPrice", 0) / 10 ** 18)
    else:
        tx = web3.eth.get_transaction(tx_hash)
        gas_price_base = Decimal(tx.get("gasPrice", 0) / 10 ** 18)

    gas_usd = Decimal(
        gas_oracle.functions.latestAnswer().call()
        / 10 ** gas_oracle.functions.decimals().call()
    )

    gas_price_of_tx = total_gas_used * gas_price_base * gas_usd
    logger.info(f"gas price of tx: {gas_price_of_tx}")

    return gas_price_of_tx


def get_latest_base_fee(web3: Web3, default=int(100e9)):  # default to 100 gwei
    latest = web3.eth.get_block("latest")
    raw_base_fee = latest.get("baseFeePerGas", hex(default))
    if type(raw_base_fee) == str and raw_base_fee.startswith("0x"):
        base_fee = int(raw_base_fee, 0)
    else:
        base_fee = int(raw_base_fee)
    return base_fee


def get_effective_gas_price(web3: Web3) -> int:
    # TODO: Currently using max fee (per gas) that can be used for this tx. Maybe use base + priority (for average).
    base_fee = get_latest_base_fee(web3)
    logger.info(f"latest base fee: {base_fee}")

    priority_fee = get_priority_fee(web3)
    logger.info(f"avg priority fee: {priority_fee}")
    # max fee aka gas price enough to get included in next 6 blocks
    gas_price = 2 * base_fee + priority_fee
    return gas_price


def get_priority_fee(
    web3: Web3,
    num_blocks: str = "0x4",
    percentile: int = 70,
    default_reward: int = 10e9,
) -> int:
    """Calculates priority fee looking at current block - num_blocks historic
    priority fees at the given percentile and taking the average.

    Args:
        web3 (Web3): Web3 object
        num_blocks (str, optional): Number of historic blocks to look at in hex form (no leading 0s). Defaults to "0x4".
        percentiles (list, optional): Percentile of transactions in blocks to use to analyze fees. Defaults to [70].
        default_reward (int, optional): If call fails, what default reward to use in gwei. Defaults to 10e9.

    Returns:
        int: [description]
    """
    gas_data = web3.eth.fee_history(num_blocks, "latest", [percentile])
    rewards = gas_data.get("reward", [[default_reward]])
    priority_fee = int(sum([r[0] for r in rewards]) / len(rewards))

    logger.info(f"piority fee: {priority_fee}")
    return priority_fee
